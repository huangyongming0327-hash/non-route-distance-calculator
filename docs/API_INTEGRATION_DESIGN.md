# TASK-004 高德真实 API 接入设计

> **终止说明（2026-07-20）**：专业货车API因最低采购成本过高，于2026-07-20终止，项目改用普通驾车参考距离。本文仅作为历史技术记录，不代表当前实现。

文档日期：2026-07-20  
实现版本：0.4.0  
当前状态：适配器与安全门已实现；本机未配置 Key，未调用真实接口

## 1. 官方合同核对

编码前重新核对了以下高德官方资料：

- [货车路径规划基础版](https://lbs.amap.com/api/logistic-service/guide/wagon_path/truck-route-plan-basis)，页面最后更新时间 2026-06-08；目标为 `GET https://restapi.amap.com/v4/direction/truck`。
- [地理/逆地理编码](https://lbs.amap.com/api/webservice/guide/api/georegeo)，页面最后更新时间 2026-02-02；地理编码为 `GET https://restapi.amap.com/v3/geocode/geo`。
- [错误码说明](https://lbs.amap.com/api/webservice/guide/tools/info/)，用于区分无效 Key、权限、日配额、QPS 和服务端错误。
- [流量限制说明](https://lbs.amap.com/api/webservice/guide/tools/flowlevel)，实际日配额和 QPS 以高德控制台为准。
- [创建应用和 Key](https://lbs.amap.com/api/webservice/create-project-and-key)及[IP 白名单建议](https://lbs.amap.com/faq/webservice/webservice-api/basic-configuration/43238)。

正式货车请求固定使用 `strategy=13`，当前官方含义为“不考虑路况距离优先”；`size=2/3/4` 分别对应轻型/中型/重型。程序不调用普通驾车接口作降级，也不会在货车接口失败时返回小汽车距离。

## 2. 组件

| 组件 | 文件 | 职责 |
| --- | --- | --- |
| 安全 Key 存储 | `src/security/key_store.py` | Credential Manager → DPAPI 当前用户 → 仅内存 |
| HTTP 与审计 | `src/amap/http_client.py` | HTTPS、超时、最多 3 次有界重试、错误归类、脱敏审计 |
| 真实地理编码 | `src/amap/real_clients.py` | 详细地址优先、城市辅助重试、结构校验、低精度阻断 |
| 真实货车算路 | `src/amap/real_clients.py` | `/v4/direction/truck`、`strategy=13`、简化车辆等级 |
| 单位验证 | `src/amap/distance.py` | steps 汇总、容差判断、唯一米→公里换算入口 |
| 批量门 | `src/application/real_gate.py` | 七项条件全部满足才允许 74 行正式批量 |
| 缓存 | `src/cache/sqlite_cache.py` | `mode` 校验；真实和模拟使用不同数据库与不同键空间 |

## 3. Key 安全

- 界面只显示前三位和后两位；短值完全遮蔽。
- 不写源代码、`.env`、明文 JSON、工作簿、日志或 Markdown。
- 首选 Windows Credential Manager，目标名为固定应用标识；失败后使用当前用户 DPAPI 加密文件 `config/local_amap_key.credential`；两者均不可用才只保存在当前进程内存。
- DPAPI 文件和本机批量门文件均由 `.gitignore` 排除。
- HTTP 审计在序列化前递归删除 `key`/`sig` 字段，日志只存无查询串的端点；地址中的手机和座机模式会脱敏。

## 4. 地理编码规则

1. 缓存键在发请求前计算，命中 `mode=real` 缓存时不消耗额度。
2. 详细地址含明确省市时，首次全国检索，不传城市列；仅在无结果后用城市列重试。
3. 详细地址缺少行政信息时，允许首请求带城市列辅助。
4. 保存规范地址、省、市、区、街道、门牌、adcode、level、经纬度、接口版本、查询时间、清洗版本和脱敏摘要。
5. 经纬度校验范围并最多保留 6 位小数。
6. `level` 为国家、省或市时标记低精度，不进入货车算路。
7. 城市冲突仍按详细地址结果计算，并在工作簿中标红；多目的地在地理编码前阻断。

## 5. 货车请求与车辆模式

基础参数为 `origin`、`destination`、`size`、`strategy=13`、`intelligent_sorting=0`、`cartype=0`、`showpolyline=0`。单位验证使用 `nosteps=0`，正式批量使用 `nosteps=1`。

默认模式 `size_only` 不主动发送 `height`、`width`、`load`、`weight`、`axis`、`province` 或 `number`。验证模式 `explicit_document_defaults` 才显式发送文档默认值，用于同线路对照。缓存键包含车辆参数模式，不能交叉复用。

## 6. 距离和缓存

`paths.distance` 先保存为原始整数；未通过单位门时 `distance_km` 必须为空。唯一换算函数为 `meters_to_kilometers()`，只有 `unit_confirmed=True` 才允许按米除以 1000 并用 ROUND_HALF_UP 保留 1 位小数。

正式路线缓存键包含起终点坐标、两端标准地址哈希、size、strategy、车辆参数模式、车型映射版本、API 合同版本、距离单位版本、算法版本和 `nosteps` 响应形态。正式数据库为 `cache/task_004_real.sqlite`，模拟数据库继续为 `cache/task_003b.sqlite`。

## 7. 错误和重试

统一中文状态覆盖：Key 为空/无效、地理编码权限、货车权限、一般权限、日配额、QPS、DNS、连接/读取超时、网络、5xx、地址无结果、低精度、路线无结果、响应结构变化和单位未确认。

无效 Key、权限、地址无结果等业务错误不重试。网络错误、HTTP 429、HTTP 5xx，以及官方 QPS/服务器繁忙码最多尝试 3 次并指数退避。技术审计保留脱敏错误码，工作簿只写中文状态和说明。

## 8. 正式批量门

本机 `config/local_real_api_gate.json` 必须证明以下七项均为真：Key 有效、专业货车权限、地理编码可用、三条线路单位验证通过、车辆参数结论可接受、错误处理已验证、real/mock 缓存隔离已验证。缺任一项时，界面和运行器均拒绝 74 行批量。

当前该门未创建，符合“无 Key 时暂停”的任务要求。
