from __future__ import annotations

from enum import StrEnum


class AmapErrorKind(StrEnum):
    EMPTY_KEY = "empty_key"
    INVALID_KEY = "invalid_key"
    GEOCODE_PERMISSION = "geocode_permission"
    PERMISSION = "permission"
    DAILY_QUOTA = "daily_quota"
    QPS_LIMIT = "qps_limit"
    NETWORK = "network"
    DNS = "dns"
    CONNECT_TIMEOUT = "connect_timeout"
    READ_TIMEOUT = "read_timeout"
    SERVER = "server"
    NO_GEOCODE_RESULT = "no_geocode_result"
    LOW_GEOCODE_PRECISION = "low_geocode_precision"
    NO_ROUTE_RESULT = "no_route_result"
    RESPONSE_SCHEMA = "response_schema"


_STATUS = {
    AmapErrorKind.EMPTY_KEY: ("Key未配置", "请在本机“API 设置”中输入并安全保存 Key。"),
    AmapErrorKind.INVALID_KEY: ("Key无效", "Key 不正确、已过期、被删除或平台类型不匹配。"),
    AmapErrorKind.GEOCODE_PERMISSION: ("权限不足", "当前 Key 无权调用高德地理编码服务。"),
    AmapErrorKind.PERMISSION: ("权限不足", "请求被高德拒绝，请检查服务权限、IP 白名单或数字签名。"),
    AmapErrorKind.DAILY_QUOTA: ("额度不足", "当前 Key 的日调用量已用尽，请在高德控制台核对配额。"),
    AmapErrorKind.QPS_LIMIT: ("QPS超限", "请求超过 QPS 或分钟级限制，请稍后重试。"),
    AmapErrorKind.NETWORK: ("网络连接失败", "无法连接高德服务，请检查网络和代理设置。"),
    AmapErrorKind.DNS: ("网络连接失败", "无法解析高德服务域名，请检查 DNS 和网络。"),
    AmapErrorKind.CONNECT_TIMEOUT: ("查询超时", "连接高德服务超时，请稍后重试。"),
    AmapErrorKind.READ_TIMEOUT: ("查询超时", "等待高德响应超时，请稍后重试。"),
    AmapErrorKind.SERVER: ("查询失败", "高德服务暂时不可用，请稍后重试。"),
    AmapErrorKind.NO_GEOCODE_RESULT: ("地址无结果", "高德未返回可用的地理编码结果，请核对详细地址。"),
    AmapErrorKind.LOW_GEOCODE_PRECISION: ("详细地址定位失败", "地址只能定位到城市或更粗粒度，未进入驾车算路。"),
    AmapErrorKind.NO_ROUTE_RESULT: ("查询失败", "高德普通驾车接口未返回可用路线。"),
    AmapErrorKind.RESPONSE_SCHEMA: ("查询失败", "响应缺少必需字段，已停止使用该响应。"),
}


class AmapApiError(RuntimeError):
    def __init__(
        self,
        kind: AmapErrorKind,
        *,
        technical_code: str = "",
        detail: str = "",
        retryable: bool = False,
    ) -> None:
        self.kind = kind
        self.status, base = _STATUS[kind]
        self.technical_code = str(technical_code or "")
        self.detail = str(detail or "")
        self.retryable = retryable
        super().__init__(base)

    @property
    def user_message(self) -> str:
        return str(self)


INVALID_KEY_CODES = {"10001", "10009", "10013"}
PERMISSION_CODES = {"10002", "10005", "10006", "10007", "10008", "10012"}
DAILY_QUOTA_CODES = {"10003"}
QPS_CODES = {"10004", "10010", "10014", "10015", "10019", "10020", "10021"}
SERVER_CODES = {"10016", "10017"}


def error_from_amap(code: str, detail: str, operation: str) -> AmapApiError:
    normalized = str(code or "").strip()
    if normalized in INVALID_KEY_CODES:
        kind = AmapErrorKind.INVALID_KEY
    elif normalized in DAILY_QUOTA_CODES:
        kind = AmapErrorKind.DAILY_QUOTA
    elif normalized in QPS_CODES:
        kind = AmapErrorKind.QPS_LIMIT
    elif normalized in SERVER_CODES:
        kind = AmapErrorKind.SERVER
    elif normalized in PERMISSION_CODES:
        kind = AmapErrorKind.GEOCODE_PERMISSION if operation == "geocode" else AmapErrorKind.PERMISSION
    else:
        kind = AmapErrorKind.PERMISSION
    return AmapApiError(
        kind,
        technical_code=normalized,
        detail=detail,
        retryable=kind in {AmapErrorKind.QPS_LIMIT, AmapErrorKind.SERVER},
    )
