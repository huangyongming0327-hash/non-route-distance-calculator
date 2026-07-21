# V1.0 最终产品测试报告

测试日期：2026-07-21  
测试环境：Windows 11 10.0.26200，Python 3.12.10，PySide6 6.9.1，PyInstaller 6.21.0

RC1 基线提交：`0847c38e30c52283bed0a319f4b9ecab19f77df0`

V1.0 发布源码提交：`8aac1f78f6f4aeae7584ee4a7912678038a22448`

## 1. 结论

正式 V1.0 的离线回归、Excel/WPS Office 发布测试、冻结 EXE Office worker、三种便携路径启动、PDF 渲染和发布安全扫描全部通过。用户已完成 74 条实际业务记录验收，批准从 V1.0 RC1 定版为 V1.0。

## 2. 用户实机验收

- 便携 EXE 正常启动。
- Excel 与 WPS 输出均未发现异常。
- 74 条非线路报价全部处理：73 条正常距离复用缓存，1 条多目的地警告符合预期。
- 距离结果已经用户人工检查，无明显问题。

## 3. Git 与变更边界

- 开始分支：`release/v1.0-rc1`；开始 HEAD：`0847c38e30c52283bed0a319f4b9ecab19f77df0`。
- `task-005a-baseline`、`v1.0-rc1` 标签和 RC1 分支/发布文件均保留。
- 开始时没有未提交源码或文档；仅有 `备份/` 下两份未跟踪业务地址/缓存 JSON，已保留在本机、加入忽略规则，未纳入 Git 或发布包。
- Git 未跟踪真实 Key、DPAPI 凭据、SQLite 缓存、业务日志或业务 Excel；测试夹具 `.xlsm` 为合成宏夹具。
- 与 RC1 相比没有业务规则变化。源码仅将 `__version__` 更新为 `1.0.0` 并设置 Qt 应用版本；窗口标题原本已符合正式标题。其余变化为发布脚本、版本文档、PDF 和报告。

## 4. 离线自动测试

命令：`.\.venv\Scripts\python.exe -m pytest -q`

结果：`189 passed, 4 skipped in 89.88s`。4 个跳过项均为要求 `RUN_OFFICE_TESTS=1` 的真实 Office 项，已在下一阶段单独执行并通过。离线套件使用传输替身/模拟客户端，没有发出真实高德请求。

覆盖业务行筛选、地址清洗与精度、多目的地、可信地址库、缓存键、地址确认清单、结果列、非目标行保护、Key 安全、Office 保存接口、三页签 UI 与便携路径。

## 5. Excel/WPS 实机测试

真实 Office pytest：`4 passed in 43.41s`。

- Excel/WPS COM 注册检测通过。
- 两种引擎均将含 VBA 的 `.xlsm` 保存为有效 FileFormat 52。
- VBA 模块与源码逐模块一致，AutomationSecurity=3，EnableEvents=false，宏未自动运行。
- 本工具专属进程退出；既有 Office 进程不受影响；WPS 既有可见窗口不受影响。

现有 Office 兼容性脚本另行验证 Excel/WPS 的 `.xlsx → .xlsm` 和 `.xlsm` 二次保存，共 4 组 `compatible_pass=true`、关键失败 0。原业务样表 SHA-256 仍为 `52011587F8F12A87749087ABEA0ADCE2557874D1B268A55F348E86F8DFA7A951`。Excel 的已知非关键样式规范化已披露；原值、公式、筛选、图片、目标行和非目标行语义保持。

## 6. 冻结 EXE 与便携验证

冻结 EXE Office worker 的 Excel/WPS 均通过：退出码 0、响应成功、FileFormat 52、VBA 保留、宏/事件禁用、专属进程释放和既有进程保护全部为 true。

| 场景 | 主窗口出现 | 进程总时长 | 结果 |
|---|---:|---:|---|
| 正式发布目录 | 1.737 秒 | 3.277 秒 | 通过 |
| 另一中文目录 | 1.657 秒 | 3.234 秒 | 通过 |
| 带空格目录 | 1.736 秒 | 3.235 秒 | 通过 |

三处均无 `src` 和 `.venv`。离线 UI 回归确认主窗口与“运距计算 / 地址确认 / API与设置”三个页签正常；空地址库可启动；空 Key 显示“未保存 / 未配置”，正式计算时给出清晰提示；Excel/WPS 检测文案正常。程序为 windowed 构建，无控制台黑框。

## 7. PDF 与安全扫描

《使用说明.pdf》为 5 页 A4。用 Poppler 以 110 DPI 渲染逐页检查，标题、页眉页脚、分页和中文正文清晰，无截断、重叠、乱码或黑块。

正式目录和 ZIP 各扫描 191 个文件，0 命中。检查覆盖 Key/token/password/secret/credential 赋值、`.env`、SQLite、Excel、地址清单、业务日志、历史缓存、手机号码、携带凭据的真实请求 URL、源码、`.venv`、缺失发布项和非空运行目录。`config/cache/logs/outputs/temp` 均为空。

## 8. 已知限制

1. 普通驾车参考距离不代表货车实际可通行路线。
2. 不考虑货车限高、限宽、限重、禁行和车牌政策。
3. 多目的地必须拆分，程序不自动排序。
4. WPS 依赖目标机 COM 注册。
5. 高德 Key 绑定当前 Windows 用户，每台电脑需重新保存。
6. 缓存和可信地址库备份可能包含业务地址，应受控保存。
7. 已在 Windows 11 完成实机验收，但不宣称覆盖所有 Excel、WPS 和 Windows 版本。
8. Windows 10 尚未完成专项实机验证，首次使用应先用业务文件副本测试。
