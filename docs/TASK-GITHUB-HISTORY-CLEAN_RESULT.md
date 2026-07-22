# TASK-GITHUB-HISTORY-CLEAN：首次 GitHub 推送前历史安全清理报告

报告日期：2026-07-23  
项目范围：`D:\AI project\非线路运距计算`  
状态：历史清理与复测完成；正式包重建和最终哈希记录待完成  

## 1. 触发原因

首次 GitHub 推送前的全历史扫描发现，原 Git 历史包含完整业务地址、一个非合成手机号形态字符串、经纬度、客户或仓库信息、业务界面截图、运距结果截图及业务工作簿验收元数据。即使目标仓库为 Private，这些内容也不允许上传，因此在尚未配置远程、认证或推送的前提下执行本地历史重写。

报告不记录任何完整地址、手机号、Key 或凭据值。

## 2. 清理工具与备份

- 工具：`git-filter-repo 2.47.0`
- 模式：`--sensitive-data-removal --invert-paths`
- 首个受影响的清理前提交：`4e0e6eaeefea9cbf8e7d4b212856434a2896a1ee`
- Bundle：`D:\AI project\Git本地备份\非线路运距计算_before_history_clean_20260723_仅本机应急恢复_严禁上传GitHub或网盘.bundle`
- Bundle SHA-256：`B6335245388D86B629A507C361E0C2C05CE0BCD8B59733829AB6BF6FB3D3F5FA`
- Bundle 验证：包含清理前全部 4 个本地分支、4 个注释标签和完整历史，`git bundle verify` 通过。

> 警告：该 Bundle 含清理前敏感历史，只允许本机应急恢复，严禁上传 GitHub、网盘、聊天或其他外部系统。

## 3. 从全部历史删除的路径

### 原始地址、路线和业务元数据

- `docs/evidence/TASK005A_ADDRESS_ANALYSIS.json`
- `docs/evidence/TASK004R_SMALL_ROUTES.json`
- `docs/evidence/TASK004R_EXCEL_VALIDATION.json`
- `docs/evidence/TASK004R_FINAL_AUDIT.json`
- `docs/evidence/TASK004R_WPS_VALIDATION.json`
- `docs/evidence/TASK005A_EXCEL_VALIDATION.json`
- `docs/evidence/TASK005A_FINAL_AUDIT.json`
- `docs/evidence/TASK005A_WPS_VALIDATION.json`
- `docs/ADDRESS_PRECISION_ANALYSIS.md`
- `docs/MANUAL_ROUTE_CHECKLIST.md`
- `docs/SAMPLE_ANALYSIS.md`

### 地址、业务工作簿和凭据界面截图

- `docs/evidence/ui_fix/1366x768_address_confirmation.png`
- `docs/evidence/ui_fix/1920x1080_address_confirmation.png`
- `docs/evidence/ui_fix/1366x768_calculation.png`
- `docs/evidence/ui_fix/1920x1080_calculation.png`
- `docs/evidence/ui_fix/1366x768_api_settings.png`
- `docs/evidence/ui_fix/1920x1080_api_settings.png`

### 业务运距结果测试截图

- `docs/evidence/visuals/excel_via_wps/conflict.png`
- `docs/evidence/visuals/excel_via_wps/multi_destination.png`
- `docs/evidence/visuals/excel_via_wps/top.png`
- `docs/evidence/visuals/wps/conflict.png`
- `docs/evidence/visuals/wps/multi_destination.png`
- `docs/evidence/visuals/wps/top.png`
- `docs/evidence/visuals/wps_native/conflict.png`
- `docs/evidence/visuals/wps_native/multi_destination.png`
- `docs/evidence/visuals/wps_native/top.png`

上述路径已从所有本地分支、标签和提交树清除。原始地址类文件从清理前首个基线提交起存在；UI 证据截图从清理前 UI 修复提交起存在。未发现改名或旧路径。

## 4. 历史引用与对象清理

- `refs/original`：不存在。
- reflog：不存在清理前提交引用。
- 不可达对象：`git fsck --full --no-reflogs --unreachable` 无输出。
- 清理前 11 个提交对象：已无法从当前仓库读取。
- 原污染标签：均已由 `git-filter-repo` 重写到安全历史；最终 `v1.0` 将在正式包验证后重新创建。
- 清理前历史的唯一保留位置：第 2 节所列本地敏感 Bundle。

## 5. 清理前后提交映射

| 清理前提交 | 清理后安全提交 |
|---|---|
| `4e0e6eaeefea9cbf8e7d4b212856434a2896a1ee` | `d178c23914041f9a96ebd1210fac251c7d0181c5` |
| `3ad7987efed66cacfaaa85d929f75e82a682e402` | `0780c4a3b8e434ac4f9352007f4d33d12ab25295` |
| `492822cb4be9ac214c3a818ad6aba6f977114334` | `bf6ba99b354445fb0ca05739a4182e6b83921780` |
| `f554fd4b1552bc34eea6f32b1e2efdeae1339287` | `9f8f293e523c72d2d4ec4b97e5da9a2227da2100` |
| `62ad85b65cddc8873fe3067f61eec7f7489d3606` | `c189d2334fd06ee9eb0cb767b70f56bc385b4202` |
| `0847c38e30c52283bed0a319f4b9ecab19f77df0` | `96dc005c9e9681f017d602c432dca847ddb7f251` |
| `8aac1f78f6f4aeae7584ee4a7912678038a22448` | `9e15d21a9b9368a1092cb806f7e45baffc641420` |
| `4f2eb603a08ae0a7a9c1ccf9461b83facac126d7` | `9f41a4576369dc68934df8929a0068c6c638009c` |
| `8de836634b8ffb26b18c764b31526ce07f808bfb` | `a35b7a7e0b8958758e07f689d30ccb6f2448311a` |
| `95877adb3748d034b158766a55b0e1f78fc9afc4` | `35cffa38dd5ef1543f7b2fcd89f247eacc96b47e` |
| `803b967e4a353cf0ee383fb41743bae9ad61e8e4` | `49210a78bee09d7c914caeabc90243c872ea420d` |

后续新增的 GitHub 首发安全清理提交不属于一对一历史重写映射，将在最终版报告中单独记录。

## 6. 全历史安全复扫

- 指定敏感路径：0 命中。
- 高德 Key、GitHub Token、password、secret、credential 明文赋值：0 命中。
- 非合成手机号形态字符串：0 命中。
- 真实业务地址、客户/仓库名称和业务坐标：0 命中。
- `.env`、SQLite、业务 Excel、地址清单、可信地址库、路线缓存、日志、EXE、ZIP、`release/` 构建目录：0 个被 Git 跟踪。
- Git 历史中超过 50 MiB / 100 MiB 的 blob：0 / 0。
- 源码连接探针和测试代码仍含固定合成地址、坐标及占位手机号；已逐项确认不来自业务数据。
- 两个宏兼容性 `.xlsm` 夹具经压缩内容扫描：无电话、地址、坐标或凭据命中，属于合成测试夹具。
- 正式使用说明 PDF 共 5 页，经文本提取和逐页渲染复核：无业务地址、电话、Key 或业务截图。
- 6 张保留的 Excel 视觉证据经像素检查为纯白内容，不含可见业务数据。

本机仍存在被 `.gitignore` 排除的 Key 凭据、业务 Excel、缓存、日志、输出、临时文件和正式构建产物；它们未被 Git 跟踪，不属于待上传内容。

## 7. 忽略规则与防复发

`.gitignore` 已覆盖 `.venv`、`__pycache__`、`build`、`dist`、`release`、`cache`、`logs`、`outputs`、`temp`、根目录 `config`、数据库、业务 Excel、EXE、ZIP、凭据、地址/缓存 JSON、已清理证据路径和证据截图目录。合成宏夹具继续通过精确例外规则保留。

后续地址证据只允许使用完全虚构的合成地址或不含完整地址、电话的脱敏统计；新地址证据必须明确标注 `is_synthetic=true`。

## 8. 重新测试结果

- 完整离线 pytest：`200 passed, 4 skipped, 0 failed in 15.52s`。
- TASK-007A 性能专项 pytest：`11 passed in 7.39s`。
- 性能测量：281 行首次/缓存约 `58.77/17.85 ms`；2,000 行约 `230.10/87.62 ms`；10,000 行约 `887.12/484.44 ms`。
- Excel/WPS 显式 Office 测试：`4 passed in 46.02s`；仅有第三方库弃用警告。
- 真实高德 API：未调用。

## 9. 正式包与最终 Git 状态

- 清理后的 `master`：待最终记录。
- 清理后的 `release/v1.0`：待最终记录。
- 清理后的 `v1.0` 标签目标：待正式包验证后记录。
- 新 EXE SHA-256：待重建。
- 新 ZIP SHA-256：待重建。
- 正式目录、中文路径和带空格路径启动验证：待重建后执行。
- 冻结 EXE Excel/WPS worker：待重建后执行。
- 正式目录和 ZIP 安全扫描：待重建后执行。
- 首次 GitHub 推送条件：尚未满足；完成重建、最终扫描和标签验证后再判定。

## 10. 外部操作状态

- GitHub 远程：未添加。
- GitHub 登录：未执行。
- GitHub 推送：未执行。
- GitHub Release：未创建。
- EXE、ZIP、PDF：未上传。
