# V1.0 便携版打包报告

打包日期：2026-07-21  
V1.0 发布源码提交：`8aac1f78f6f4aeae7584ee4a7912678038a22448`

## 1. 打包方案

- PyInstaller 6.21.0，Python 3.12.10，PySide6 6.9.1。
- `onedir` + `windowed`，未改为 onefile，启动不出现控制台黑框。
- 构建脚本：`scripts/build_release.ps1`。
- 便携验证：`scripts/verify_portable_release.ps1`。
- 冻结 Office 验证：`scripts/verify_frozen_office_worker.py`。
- 清理与 ZIP：`scripts/finalize_release.ps1`。
- 安全扫描：`scripts/scan_release.ps1`。

## 2. 正式输出

- 目录：`D:\AI project\非线路运距计算\release\非线路运距计算工具_V1.0`
- EXE：`D:\AI project\非线路运距计算\release\非线路运距计算工具_V1.0\非线路运距计算工具.exe`
- ZIP：`D:\AI project\非线路运距计算\release\非线路运距计算工具_V1.0_便携版.zip`
- ZIP 大小：55,178,135 字节。
- ZIP SHA-256：`62CAC7C60A81EB7D466EEC6D6098838B00E95987520FB91F016EFA3AA308F9E9`。

RC1 目录 `release\非线路运距计算工具_V1.0_RC1` 和 RC1 ZIP 原样保留，未覆盖、未删除。

## 3. 发布目录内容

- `非线路运距计算工具.exe`
- `_internal`
- 空目录 `config`、`cache`、`logs`、`outputs`、`temp`
- `USER_GUIDE.md`
- `使用说明.pdf`
- `VERSION.txt`
- `CHANGELOG.md`
- `KNOWN_ISSUES.md`

不包含真实 Key、DPAPI 凭据、业务 Excel/结果、可信地址业务数据库、历史路线缓存、真实地址清单、源码或 `.venv`。

## 4. 验证结果

- 正式目录、另一中文目录、带空格目录启动均通过；最慢主窗口出现时间 1.737 秒。
- 三处均不依赖源码或 `.venv`，运行数据写入各自便携目录。
- 冻结 EXE 的 Excel/WPS Office worker 均通过 FileFormat、VBA、安全设置和进程隔离检查。
- 正式目录与 ZIP 安全扫描各 191 个文件，0 命中；五个运行目录为空。

## 5. 已知打包限制

- WPS 依赖目标机 COM 注册。
- Key 与当前 Windows 用户绑定，新电脑必须重新输入。
- 已在 Windows 11 验收；Windows 10 未完成专项实机验证，首次使用应先用业务文件副本测试。
- 不宣称覆盖所有 Excel、WPS 和 Windows 版本。
