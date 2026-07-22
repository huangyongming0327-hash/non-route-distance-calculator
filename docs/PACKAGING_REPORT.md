# V1.0 便携版打包报告

打包日期：2026-07-22
TASK-007A 提交：`8de836634b8ffb26b18c764b31526ce07f808bfb`
V1.0 发布源码提交：`95877adb3748d034b158766a55b0e1f78fc9afc4`

## 1. 打包方案

- PyInstaller 6.21.0，Python 3.12.10，PySide6 6.9.1。
- `onedir + windowed`，未改为 onefile；PE Subsystem=2，无黑色控制台窗口。
- 构建脚本要求 Git 工作区为 clean，并把实际提交 Hash 写入发布目录 `VERSION.txt`。
- 构建、便携验证、冻结 Office 验证、清理压缩和安全扫描均使用仓库内正式脚本。

## 2. 正式输出

- 目录：`D:\AI project\非线路运距计算\release\非线路运距计算工具_V1.0`
- EXE：`D:\AI project\非线路运距计算\release\非线路运距计算工具_V1.0\非线路运距计算工具.exe`
- ZIP：`D:\AI project\非线路运距计算\release\非线路运距计算工具_V1.0_便携版.zip`
- EXE 大小：3,695,562 字节。
- EXE SHA-256：`99819A5E75212E06B4043AB7EAB8147289EA8060F2F9D5F756E7C2FF189E0949`。
- ZIP 大小：55,209,288 字节。
- ZIP SHA-256：`02814C1A8AF222424123F519BFF51CA8EEE0E368CE4E73E80D194B265FF5ABA3`。

历史 RC1、RC2 目录和 ZIP 的 EXE/ZIP 哈希在构建前后完全一致，未覆盖、未删除。

## 3. 发布目录内容

- `非线路运距计算工具.exe`
- `_internal`
- 空目录 `config`、`cache`、`logs`、`outputs`、`temp`
- `USER_GUIDE.md`
- `使用说明.pdf`
- `VERSION.txt`
- `CHANGELOG.md`
- `KNOWN_ISSUES.md`

## 4. 便携与 Office 验证

- 正式目录、另一中文目录、带空格目录均启动通过；最慢主窗口出现 1.530 秒。
- 三处均不依赖源码或 `.venv`；日志写入各自便携目录。
- 正式 EXE 的 Excel/WPS worker 均通过有效 `.xlsm`、VBA 保留、宏/事件禁用和进程隔离检查。
- 自动测试和用户实机确认输出目录选择、工作簿检测与检测缓存未重新引入卡顿。
- 离线自动测试为 200 passed、4 skipped、0 failed；性能专项为 11 passed，281 行首次检测 49.50 ms、缓存 12.99 ms。

## 5. 安全扫描

正式目录与 ZIP 各 191 个文件，0 命中。五个运行目录为空；不包含真实 Key、DPAPI 凭据、`.env`、SQLite、业务 Excel/结果、地址确认清单、真实地址库、路线缓存、请求 URL、业务日志、源码或 `.venv`。

## 6. 部署边界

必须完整解压整个 ZIP，不能在压缩包内运行，不能只复制 EXE 或删除 `_internal`。目标电脑至少安装 Excel 或 WPS；每台新电脑重新保存 Key。可信地址库和缓存通常只需首次导入一次，关闭程序或电脑不会丢失；重新解压到全新目录或删除 `cache` 后需要重新导入。Windows 10 尚未专项实测。
