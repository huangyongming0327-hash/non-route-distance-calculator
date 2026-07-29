# 非线路运距计算工具 V1.0

Windows 本地桌面工具，使用高德地理编码和路径规划 2.0 普通驾车接口，为 Excel/WPS 中精确等于“非线路报价”的行生成参考公路距离，并通过本地可信地址库实现“唯一地址一次确认、以后自动复用”。

> 普通驾车参考距离，不代表货车实际可通行路线。本工具不考虑货车限高、限宽、限重、禁行及车牌限制。

当前状态：**V1.0 已通过用户实机验收；首次 GitHub 推送前已执行历史安全清理；GitHub 仓库当前为 Public。**

> Public 仓库禁止上传任何业务数据、完整地址、业务工作簿、可信地址库、缓存、日志、Key、Token 或其他凭据。

## 快速启动

环境：Windows 11、Python 3.12，以及 Microsoft Excel 或已验证的 WPS 表格。

```powershell
cd "D:\AI project\非线路运距计算"
.\.venv\Scripts\python.exe -m src.main
```

也可双击 `scripts/run_prototype.bat`。脚本不需要管理员权限，会自动进入项目根目录并检查 `.venv`；仅在启动失败时暂停显示错误。

## 便携版部署

正式便携版不需要安装 Python。把整个 ZIP 复制到目标电脑后先“全部解压”，不能在压缩包内部运行，也不能只复制 EXE 或删除 `_internal`；可以给 EXE 创建桌面快捷方式。目标电脑至少安装 Microsoft Excel 或 WPS 表格中的一种。

每台新电脑需要由当前 Windows 用户重新输入并保存高德 Key。可信地址库和缓存通常只需首次导入一次，关闭程序或电脑不会丢失；重新解压到全新目录或删除 `cache` 后才需重新导入。未导入缓存时程序会按需重新调用 API，并在本机逐步积累。可信地址库和缓存 JSON 可能包含业务地址，必须内部受控保存。

## 三页签界面

- **运距计算**：工作簿、字段映射、运行设置、前 10 行预览、处理进度和任务/结果按钮。小屏幕下使用页内纵向滚动。
- **地址确认**：自动显示当前可信地址库。无选中行时单条操作按钮禁用；导入确认结果不需选中行。
- **API与设置**：Key 安全存储、删除、连接测试、接口状态、开发/测试模式和低频缓存清理。

Qt 6 使用 Windows 原生高 DPI 行为，支持 100%/125%/150% 缩放，不要为本工具永久修改 Windows 缩放比例。

## 正式口径

- 地理编码：`GET https://restapi.amap.com/v3/geocode/geo`
- 路径规划：`GET https://restapi.amap.com/v5/direction/driving`
- 参数：`strategy=32`、`cartype=0`、`ferry=1`、`alternative_route=1`、`output=json`
- 距离：读取第一条 `route.paths` 的 `distance` 米数，Decimal `ROUND_HALF_UP` 换算为一位小数公里
- 正式缓存：`cache/driving_real.sqlite`
- 可信地址：`confirmed_addresses`，地址/坐标确认后跨行、跨角色、跨工作簿复用
- 车型：可选只读，不参与请求、缓存键、距离或状态

## 使用流程

1. 在“API与设置”中安全保存高德 Web 服务 Key；不要把 Key 写入聊天、配置、Excel 或文档。
2. 选择工作簿并确认工作表、表头和字段映射。
3. 进入“地址确认”页处理唯一地址。先处理“待进一步核实”和真正有风险的“未确认”地址，不需要逐行确认订单。
4. 可使用原始地址、高德标准地址或只用于查询的修正地址重新解析；原 Excel 城市和详细地址不会修改。
5. 点击“确认定位正确”后，同地址以后直接复用；也可导出 Excel 待确认清单，线下填写后按地址ID导回。
6. 选择 Excel/WPS 和普通驾车正式计算，确认风险后开始。程序只写工作副本和新结果文件，不覆盖输入。

完整步骤见 `docs/USER_GUIDE.md`。源码仅用于开发、测试和审计；普通使用者后续应从 GitHub Releases 下载 V1.0 便携版 ZIP，不应从源码目录直接运行生产任务。

## 地址精度状态

- 系统高可信：门牌号/门址、名称匹配兴趣点、名称匹配道路或明确园区，不标黄。
- 查询成功—定位待复核：允许生成参考距离，但乡镇/村庄、名称不足或其他证据值得人工复核，标黄。
- 查询成功—地址冲突待确认：按详细地址坐标计算，必须人工确认；确认后可信库复用，不再重复标红。
- 地址风险过高—未计算：仅到区县、行政区错位、坐标异常或无法解析，距离留空并标红。
- 地址无效 / 多目的地待确认：阻止自动算路。

详细规则见 `docs/CONFIRMED_ADDRESS_DESIGN.md`；仓库只保留合成测试或不含完整地址、电话的脱敏统计。

## V1.0 验收摘要

- 地址确认、距离缓存、多目的地和城市冲突流程已完成脱敏验收。
- Excel/WPS 输出均未发现异常，距离结果经用户人工检查无明显问题。
- V1.0 离线回归：200 passed、4 skipped、0 failed；显式启用的真实 Office 测试：4 passed。

## 验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest -q
$env:RUN_OFFICE_TESTS = "1"
.\.venv\Scripts\python.exe -m pytest -q tests\test_office_integration.py tests\test_office_release.py
.\scripts\build_release.ps1
.\scripts\verify_portable_release.ps1
.\.venv\Scripts\python.exe scripts\verify_frozen_office_worker.py
.\scripts\finalize_release.ps1
.\scripts\scan_release.ps1
```

Excel/WPS 阶段会启动本工具专属隐藏 Office 进程并执行安全保存和重开验证。不要手工结束这些进程。

## 安全边界

- GitHub 仓库当前为 Public；任何提交、Issue、PR 和 Actions 日志都不得包含业务数据或凭据。
- Key 优先保存到 Windows Credential Manager，回退到当前用户 DPAPI；所有 HTTP 审计删除 Key/sig 并脱敏电话号码。
- 禁止向 Git、GitHub Issue、聊天或文档上传高德 Key、Token、凭据、业务 Excel、客户/仓库地址、电话、可信地址库、路线缓存或运距结果。
- 输入文件先指纹校验再复制；禁止覆盖输入或写入 `samples/input`。
- 原 Excel 地址只读；修正查询地址只保存到本地 SQLite。
- 禁止宏、事件、更新链接和刷新；拒绝 XLM 宏表。
- 不调用 `/v4/direction/truck`，不在普通驾车失败时伪造距离，也不把 mock 写入正式缓存。
- 不删除或修改原车型列；旧货车距离列属于不同口径，原样保留。

## 当前交付

- `CURRENT_STATUS.md`
- `docs/FINAL_RELEASE_REPORT.md`
- `docs/TASK-008_RESULT.md`
- `docs/FINAL_PRODUCT_TEST_REPORT.md`
- `docs/PACKAGING_REPORT.md`
- `release/非线路运距计算工具_V1.0/`
- `release/非线路运距计算工具_V1.0_便携版.zip`
- `docs/PERFORMANCE_OPTIMIZATION_REPORT.md`
- `docs/TASK-007A_RESULT.md`
- `docs/CONFIRMED_ADDRESS_DESIGN.md`
- `docs/ADDRESS_CONFIRMATION_TEST_REPORT.md`
- `docs/TASK-005A_RESULT.md`
- `docs/UI_RESPONSIVE_FIX_REPORT.md`
- `docs/TASK-005A-UI-FIX-001_RESULT.md`

正式 EXE 与便携版 ZIP 不进入 Git 历史；GitHub Release 创建前会另行验证并上传发布资产。

专业货车方案因最低采购成本过高已终止；历史文档保留并标记，不代表当前实现。
