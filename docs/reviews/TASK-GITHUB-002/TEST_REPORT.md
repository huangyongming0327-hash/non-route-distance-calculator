# TASK-GITHUB-002 测试报告

- 任务名称：建立自动上传与在线审核流程
- 任务分支：`task/TASK-GITHUB-002-review-workflow`

## 实际执行命令

`powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall -q src scripts tests
git diff --check
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/scan_repository_safety.ps1
.\.venv\Scripts\python.exe scripts/validate_review_package.py --task-id "TASK-GITHUB-002" --branch "task/TASK-GITHUB-002-review-workflow"
`

## 结果摘要

- 通过：206
- 失败：0
- 跳过：4
- 完整离线 pytest：206 passed, 4 skipped in 15.35s
- 专项测试：随完整离线 pytest 一并执行审核流程专项测试。
- Excel 测试：离线单元测试执行；未运行真实 Excel COM。
- WPS 测试：离线单元测试执行；未运行真实 WPS COM。
- 真实 API 调用次数：0

## 未执行测试及原因

- 未执行真实 Excel/WPS COM：本任务只建立开发与审核流程，且 GitHub Actions 禁止运行真实 Office COM。
- 未执行真实高德 API：任务明确要求离线验证。

## 失败或警告

- 自动化命令失败数为 0。
- GitHub Actions 首次运行 `30103804316` 失败：干净运行器没有禁止上传的业务 Excel，也没有项目 `.venv`。
- 修复方式：Actions 创建隔离 `.venv`；仅依赖本机私有样表的测试在样表缺失时明确跳过；未上传业务数据。
- GitHub Actions 第二次运行 `30104220026`：完整 pytest、编译和差异检查已通过；安全扫描因 Git 转义中文路径而发生兼容错误，没有敏感内容命中。
- 修复方式：扫描器固定读取 Git 的未转义路径，并新增中文文件名回归测试。
- GitHub Actions 第三次运行 `30104491404`：pytest、编译、差异和安全扫描全部通过；审核验证已完成，但输出中文成功提示时遇到 runner CP1252 编码错误。
- 修复方式：工作流固定 Python UTF-8，并让制品检查只检查 Git 会上传的文件，排除 CI 自身的 `.venv`。
- GitHub Actions 第四次运行 `30105078932`：199 passed，11 skipped；编译、差异、安全扫描、审核材料和禁止发布制品检查全部通过。
- CI 比本机多跳过 7 项依赖私有业务样表的测试；样表按安全规则未上传。
- GitHub Actions 第五次运行 `30105329617`：共享运行器调度抖动触发既有 `0.15` 秒墙钟断言，1 项失败；业务代码与第四次绿色提交相同。
- 修复方式：用事件同步直接验证慢探针仍阻塞时 worker 返回 `timeout`，不再依赖 CI 机器瞬时速度。
- 当前结果：测试稳定性修复已完成，等待最终复跑。
- 运行地址：https://github.com/huangyongming0327-hash/non-route-distance-calculator/actions/runs/30105078932
