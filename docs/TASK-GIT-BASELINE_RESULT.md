# TASK-005A Git 稳定基线结果

执行日期：2026-07-20（Asia/Shanghai）  
项目目录：`D:\AI project\非线路运距计算`  
基线结论：通过

## 基线标识

- 提交说明：`baseline: TASK-005A validated confirmed-address version`
- 标签：`task-005a-baseline`
- 分支：`master`
- 远程操作：未配置远程仓库，未执行推送

## 操作边界

- 未修改业务功能；本次仅完善 `.gitignore` 并新增本结果文档。
- 未调用真实高德 API。完整 pytest 在 HTTPS 连接闸门下运行，任何代码若尝试通过项目使用的 `http.client.HTTPSConnection.connect` 建立连接都会立即失败。
- 未访问或操作 `D:\AI project\直播智能切片`。
- 未继续 TASK-005A 之后的功能开发。

## `.gitignore` 核验

已确认以下内容不进入基线：

- `.venv`、Python/pytest 缓存；
- 根目录 `cache`、`logs`、`temp`、`build`、`release`、`outputs`；
- `samples/input`、`samples/working`、`samples/expected`；
- SQLite 数据库及其 WAL/SHM/journal 文件；
- Excel 原表、业务结果和 Office 临时文件；
- 本机配置、`.env`、Key、token、password、secret、credential、PEM 文件。

原 `cache/` 规则会误忽略正式源码目录 `src/cache/`，现已改为仅匹配根目录 `/cache/`。因此 `src/cache/__init__.py` 和 `src/cache/sqlite_cache.py` 已纳入基线。

测试套件所需的两份合成 `.xlsm` fixture 通过 `tests/fixtures/*.xlsm` 明确例外纳入版本控制；它们不是 Excel 业务原表或业务结果。

## 提交内容核验

基线包含正式源码、测试、测试 fixture、脚本、依赖清单、pytest 配置、设计与验收文档、文档证据、README、根目录及 docs 下的 CURRENT_STATUS，以及本结果文档。

按要求，`samples/input` 中的本地样表不提交。依赖该样表的回归测试在本次现有受控工作区中执行通过；干净检出后复测时需由操作者另行提供获准使用的本地样表。

## 明文凭据扫描

提交前对候选文本文件检查了以下类型：

- 常见云服务/provider token 格式；
- 私钥头；
- API Key、Amap Key、access/refresh/auth token、password、passwd、pwd、client secret、secret 的赋值；
- URL 查询参数中的 key、token、password、secret；
- 文件名中的 key、token、password、secret、credential 关键词。

结果：未发现真实明文 Key、token、password、secret 或私钥。关键词复核仅涉及安全存储实现、设计文档、等待 Key 的历史文档和显式测试占位值。`config/local_amap_key.credential` 已被忽略且不在提交候选中。

## 离线 pytest

- Python：3.12.10
- pytest：8.4.1
- `RUN_OFFICE_TESTS=0`
- 网络保护：测试进程内禁止 `http.client.HTTPSConnection.connect`
- 结果：`157 passed, 2 skipped, 0 failed`
- 耗时：114.88 秒
- 跳过项：2 项显式要求 `RUN_OFFICE_TESTS=1` 的真实 Excel/WPS 桌面集成测试；本次按离线基线要求不启动。

## 最终状态

基线提交和标签均只保留在本地仓库。完成后暂停，不推送、不继续开发。
