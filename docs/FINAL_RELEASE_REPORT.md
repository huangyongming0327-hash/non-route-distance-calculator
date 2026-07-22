# 非线路运距计算工具 V1.0 正式发布报告

发布日期：2026-07-23
正式分支：`release/v1.0`

TASK-007A 清理后提交：`a35b7a7e0b8958758e07f689d30ccb6f2448311a`
V1.0 正式发布提交：`4075063ff8c0425715bbedbf70b6ffc10dd4ca9e`
注释标签：`v1.0`（非线路运距计算工具V1.0正式版（GitHub首次发布安全清理版））

> 首次 GitHub 推送前已执行历史安全清理。清理前提交号和旧包哈希已失效；本报告记录清理后的正式提交与重建包哈希。

## 1. 发布结论

用户已在实际电脑和实际业务文件中完成性能优化版本验收：选择输出目录不再卡顿，表头和字段自动检测不再长时间无响应，同一文件第二次检测明显更快；Microsoft Excel 与 WPS 保存和结果检查正常；普通驾车距离、可信地址库、缓存和结果口径未发现异常。因此批准把同一业务代码正式定版为 V1.0。

本次未修改已经验收的业务逻辑。正式提交相对 TASK-007A 提交的源码差异只有 `src/__init__.py`、`src/main.py` 和 `src/ui/main_window.py` 中的版本常量、应用名称与窗口标题；其余差异为正式构建路径、发布校验脚本、文档、PDF 和性能证据。报价类型筛选、高德 API、普通驾车参数、地址清洗、多目的地、城市冲突、可信地址库、地址 ID/状态、路线缓存键及失效、结果列、Excel/WPS 安全保存、宏禁用/VBA 保留、原文件和非目标行保护均未改变。

## 2. Git 定版

- TASK-007A 按指定说明 `perf: eliminate workbook detection UI blocking` 提交。
- V1.0 按指定说明 `release: publish non-route distance calculator V1.0` 提交。
- `release/v1.0` 为现有历史分支的顺向演进，没有强制覆盖分支历史。
- 原 `v1.0` 标签目标 `8aac1f78f6f4aeae7584ee4a7912678038a22448` 已以注释标签 `v1.0-pre-task008` 保留；正式 `v1.0` 指向本次发布提交。
- `task-005a-baseline`、`release/v1.0-rc1`、`v1.0-rc1`、历史发布目录、ZIP、报告和构建文件均保留。
- 未配置远程仓库，未推送。

## 3. 自动测试

- 命令：`.\.venv\Scripts\python.exe -m pytest -q`
- 结果：`200 passed, 4 skipped, 0 failed in 15.52s`。
- 4 个跳过项均为默认关闭的真实 Office 项，已在下一阶段显式启用并通过。
- 离线套件未调用真实高德 API，覆盖目标行筛选、地址规则、可信地址库、缓存键与失效、结果列、非目标行保护、Office 接口、三页签 UI 和性能交互。

## 4. Office 实机测试

显式启用 Office pytest：`4 passed in 46.02s`。

- Excel 与 WPS COM 注册检测均通过。
- Excel/WPS 的 `.xlsx → .xlsm` 和已有 `.xlsm` 再次保存共 4 组 `compatible_pass=true`，关键失败 0。
- 每组保留 245 个公式、5 个 DISPIMG、2 个媒体资源、筛选范围、206 个隐藏行和条件格式语义；目标行正确写入，非目标行语义未改变。
- 合成宏夹具在 Excel/WPS 均通过：AutomationSecurity=3、EnableEvents=false，原宏未自动运行，VBA 源码、按钮、形状和普通公式保留。
- 原输入文件 SHA-256 前后均为 `52011587F8F12A87749087ABEA0ADCE2557874D1B268A55F348E86F8DFA7A951`。
- 本工具专属 Office 进程安全退出，用户既有进程不变；WPS 既有可见窗口不变。
- Excel 保存仍存在已披露的非关键样式规范化差异，不影响原值、公式、图片、筛选、条件格式语义或业务结果。
- 冻结正式 EXE 的 Excel/WPS Office worker 均通过 FileFormat 52、VBA、安全设置和进程隔离检查。

## 5. 性能回归

TASK-007A 专项测试：`11 passed in 7.39s`。

| 场景 | 首次检测 | 缓存检测 | 结果 |
|---|---:|---:|---|
| 当前 281 行验收样表 | 58.77 ms | 17.85 ms | 通过 |
| 2,000 行合成表 | 230.10 ms | 87.62 ms | 通过 |
| 10,000 行合成表 | 887.12 ms | 484.44 ms | 通过 |

专项测试覆盖选择输出目录后主线程立即恢复、表头检测后台执行、检测中切换页签、连续点击、检测中更换文件、取消、旧结果隔离、缓存命中和文件变化后失效。正式回归和用户实机验收均未重新引入卡顿。

## 6. 正式发布包

- EXE：`D:\AI project\非线路运距计算\release\非线路运距计算工具_V1.0\非线路运距计算工具.exe`
- ZIP：`D:\AI project\非线路运距计算\release\非线路运距计算工具_V1.0_便携版.zip`
- EXE SHA-256：`F5ADE01A2415AECA7CA2FF60D9F7063EB3FC9794686C7DA65F7CAF1C9AEC8A91`。
- ZIP SHA-256：`8A33F080F6BF040B122EE6C35335577E3BB0F8D6B9EFE30F58F664BF159F9ED1`。
- ZIP 大小：55,208,960 字节。
- 构建：PyInstaller 6.21.0，`onedir + windowed`；PE Subsystem=2，无黑色控制台窗口。
- 目录、另一中文路径、带空格路径启动均通过；主窗口最慢 1.563 秒出现，三处均不含 Python 源码或 `.venv`。
- 目录内 `VERSION.txt` 记录正式提交 Hash 和 `clean` 工作区状态。

## 7. 安全扫描

正式目录与 ZIP 各 191 个文件，0 命中。扫描覆盖 Key、token、password、secret、credential、`.env`、DPAPI 凭据、SQLite、业务 Excel/结果、地址确认清单、真实地址库、路线缓存、带凭据请求 URL、日志中的手机号/业务数据、`src` 和 `.venv`。`config/cache/logs/outputs/temp` 均为空。

安全证据：

- `docs/evidence/task008/security_scan_v1.json`
- `docs/evidence/task008/portable_verification_v1.json`
- `docs/evidence/task008/frozen_office_worker_v1.json`
- `docs/evidence/task008/test_summary_v1.json`

## 8. 新电脑部署与持久化

1. 便携版不需要安装 Python；把整个 ZIP 复制到目标电脑后先“全部解压”。
2. 不能在 ZIP 内运行，不能只复制 EXE，不能删除 `_internal`；可以给 EXE 创建桌面快捷方式。
3. 目标电脑至少安装 Microsoft Excel 或 WPS 表格中的一种。
4. 每台新电脑由当前 Windows 用户重新输入并保存高德 Key。
5. 可信地址库和缓存通常只需首次导入一次，关闭程序或电脑不会丢失。
6. 重新解压到全新目录或删除 `cache` 后才需重新导入；未导入缓存时程序会按需调用 API，并在本机重新积累。
7. 可信地址库和缓存 JSON 可能包含业务地址，必须内部受控保存。

## 9. 已知限制

普通驾车参考距离不代表货车实际可通行路线，也不考虑货车限高、限宽、限重、禁行和车牌政策。多目的地必须拆分，程序不自动排序。WPS 依赖目标机 COM 注册。高德 Key 绑定当前 Windows 用户。Windows 10 尚未完成专项实机验证，首次使用必须先用业务文件副本测试；不宣称覆盖所有 Excel、WPS 或 Windows 版本。

V1.0 正式发布完成，到此暂停，不继续 V1.1 或其他新功能。
