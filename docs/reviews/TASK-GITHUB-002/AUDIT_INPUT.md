# TASK-GITHUB-002 独立审核输入

- 任务名称：建立自动上传与在线审核流程（审核修复阶段）
- 任务分支：`task/TASK-GITHUB-002-review-workflow`
- 修改前 Commit：`290153e240f059f7e3ffda34476446d77da409b8`
- 修改后实现 Commit：`63fd9c2113854bd218fa5207e72595b82756df42`
- 审核目标：Pull Request 当前 HEAD
- Pull Request：https://github.com/huangyongming0327-hash/non-route-distance-calculator/pull/1

## 用户需求原文摘要

总指挥要求 TASK-GITHUB-002 暂不合并并进入修复阶段：增强当前与历史敏感信息扫描，移除测试文件豁免，通用化 finalize_task.ps1，并同步真实 PR HEAD 与审核材料。

## 验收标准

- 带有测试或合成文字的文件只要包含手机号、完整地址或经纬度形态就会被拦截。
- 敏感内容先提交再删除时，扫描分支提交历史仍会阻止推送。
- finalize_task.ps1 的任务结论来自 REVIEW_CONTEXT.json 或实际命令证据。
- 非 GitHub 流程任务模拟能够生成对应内容，不出现 TASK-GITHUB-002 专用结论。
- LATEST_REVIEW.md、AUDIT_INPUT.md 和 CHANGED_FILES.md 与当前 PR 审核范围一致。
- 本地门禁与 GitHub Actions 全部通过。

## git diff 统计

```text
 .github/ISSUE_TEMPLATE/bug_report.yml            |   81 ++
 .github/ISSUE_TEMPLATE/feature_request.yml       |   71 ++
 .github/pull_request_template.md                 |   45 +
 .github/workflows/pr-validation.yml              |   89 ++
 AGENTS.md                                        |   78 ++
 CURRENT_STATUS.md                                |   59 +-
 README.md                                        |    5 +-
 docs/CODEX_TASK_TEMPLATE.md                      |   77 ++
 docs/CURRENT_STATUS.md                           |    2 +
 docs/GITHUB_BRANCH_PROTECTION_GUIDE.md           |   25 +
 docs/TASK-GITHUB-001A_RESULT.md                  |    6 +-
 docs/TASK-GITHUB-001B_RESULT.md                  |    4 +-
 docs/reviews/LATEST_REVIEW.md                    |   44 +
 docs/reviews/README.md                           |   24 +
 docs/reviews/TASK-GITHUB-002/AUDIT_INPUT.md      |  165 ++++
 docs/reviews/TASK-GITHUB-002/CHANGED_FILES.md    |  101 +++
 docs/reviews/TASK-GITHUB-002/KNOWN_ISSUES.md     |   25 +
 docs/reviews/TASK-GITHUB-002/REVIEW_CONTEXT.json |   78 ++
 docs/reviews/TASK-GITHUB-002/REVIEW_INDEX.md     |   88 ++
 docs/reviews/TASK-GITHUB-002/SECURITY_REPORT.md  |   17 +
 docs/reviews/TASK-GITHUB-002/TASK_RESULT.md      |   36 +
 docs/reviews/TASK-GITHUB-002/TEST_REPORT.md      |   32 +
 docs/reviews/TASK_TEMPLATE/AUDIT_INPUT.md        |   41 +
 docs/reviews/TASK_TEMPLATE/CHANGED_FILES.md      |   25 +
 docs/reviews/TASK_TEMPLATE/KNOWN_ISSUES.md       |   24 +
 docs/reviews/TASK_TEMPLATE/REVIEW_CONTEXT.json   |   54 ++
 docs/reviews/TASK_TEMPLATE/REVIEW_INDEX.md       |   42 +
 docs/reviews/TASK_TEMPLATE/SECURITY_REPORT.md    |   20 +
 docs/reviews/TASK_TEMPLATE/TASK_RESULT.md        |   28 +
 docs/reviews/TASK_TEMPLATE/TEST_REPORT.md        |   26 +
 scripts/finalize_task.ps1                        | 1026 ++++++++++++++++++++++
 scripts/scan_repository_safety.ps1               |  284 ++++++
 scripts/start_task.ps1                           |  126 +++
 scripts/validate_review_package.py               |  238 +++++
 tests/conftest.py                                |    3 +-
 tests/test_review_workflow.py                    |  508 +++++++++++
 tests/test_task007a_performance.py               |   18 +-
 tests/test_ui_smoke.py                           |    2 +-
 38 files changed, 3562 insertions(+), 55 deletions(-)
```

## 核心改动位置

- `.github/ISSUE_TEMPLATE/bug_report.yml`
- `.github/ISSUE_TEMPLATE/feature_request.yml`
- `.github/pull_request_template.md`
- `.github/workflows/pr-validation.yml`
- `AGENTS.md`
- `CURRENT_STATUS.md`
- `docs/CODEX_TASK_TEMPLATE.md`
- `docs/CURRENT_STATUS.md`
- `docs/GITHUB_BRANCH_PROTECTION_GUIDE.md`
- `docs/reviews/LATEST_REVIEW.md`
- `docs/reviews/README.md`
- `docs/reviews/TASK_TEMPLATE/AUDIT_INPUT.md`
- `docs/reviews/TASK_TEMPLATE/CHANGED_FILES.md`
- `docs/reviews/TASK_TEMPLATE/KNOWN_ISSUES.md`
- `docs/reviews/TASK_TEMPLATE/REVIEW_CONTEXT.json`
- `docs/reviews/TASK_TEMPLATE/REVIEW_INDEX.md`
- `docs/reviews/TASK_TEMPLATE/SECURITY_REPORT.md`
- `docs/reviews/TASK_TEMPLATE/TASK_RESULT.md`
- `docs/reviews/TASK_TEMPLATE/TEST_REPORT.md`
- `docs/reviews/TASK-GITHUB-002/AUDIT_INPUT.md`
- `docs/reviews/TASK-GITHUB-002/CHANGED_FILES.md`
- `docs/reviews/TASK-GITHUB-002/KNOWN_ISSUES.md`
- `docs/reviews/TASK-GITHUB-002/REVIEW_CONTEXT.json`
- `docs/reviews/TASK-GITHUB-002/REVIEW_INDEX.md`
- `docs/reviews/TASK-GITHUB-002/SECURITY_REPORT.md`
- `docs/reviews/TASK-GITHUB-002/TASK_RESULT.md`
- `docs/reviews/TASK-GITHUB-002/TEST_REPORT.md`
- `docs/TASK-GITHUB-001A_RESULT.md`
- `docs/TASK-GITHUB-001B_RESULT.md`
- `README.md`
- `scripts/finalize_task.ps1`
- `scripts/scan_repository_safety.ps1`
- `scripts/start_task.ps1`
- `scripts/validate_review_package.py`
- `tests/conftest.py`
- `tests/test_review_workflow.py`
- `tests/test_task007a_performance.py`
- `tests/test_ui_smoke.py`

## 测试命令和原始结果摘要

- `.\.venv\Scripts\python.exe -m pytest -q`：210 passed, 4 skipped in 22.07s
- `.\.venv\Scripts\python.exe -m compileall -q src scripts tests`：通过。
- `git diff --check`：通过。
- 安全扫描：0 命中。

## 已知风险

- 提交历史扫描依赖 Git 和扩展正则表达式，需同时在 Windows 本地与 GitHub Actions 验证。
- 纯审核文档提交会再次触发 Actions，最终交付以 PR HEAD 对应检查为准。

## 重点检查路径

- `.github/ISSUE_TEMPLATE/bug_report.yml`
- `.github/ISSUE_TEMPLATE/feature_request.yml`
- `.github/pull_request_template.md`
- `.github/workflows/pr-validation.yml`
- `AGENTS.md`
- `CURRENT_STATUS.md`
- `docs/CODEX_TASK_TEMPLATE.md`
- `docs/CURRENT_STATUS.md`
- `docs/GITHUB_BRANCH_PROTECTION_GUIDE.md`
- `docs/reviews/LATEST_REVIEW.md`
- `docs/reviews/README.md`
- `docs/reviews/TASK_TEMPLATE/AUDIT_INPUT.md`
- `docs/reviews/TASK_TEMPLATE/CHANGED_FILES.md`
- `docs/reviews/TASK_TEMPLATE/KNOWN_ISSUES.md`
- `docs/reviews/TASK_TEMPLATE/REVIEW_CONTEXT.json`
- `docs/reviews/TASK_TEMPLATE/REVIEW_INDEX.md`
- `docs/reviews/TASK_TEMPLATE/SECURITY_REPORT.md`
- `docs/reviews/TASK_TEMPLATE/TASK_RESULT.md`
- `docs/reviews/TASK_TEMPLATE/TEST_REPORT.md`
- `docs/reviews/TASK-GITHUB-002/AUDIT_INPUT.md`
- `docs/reviews/TASK-GITHUB-002/CHANGED_FILES.md`
- `docs/reviews/TASK-GITHUB-002/KNOWN_ISSUES.md`
- `docs/reviews/TASK-GITHUB-002/REVIEW_CONTEXT.json`
- `docs/reviews/TASK-GITHUB-002/REVIEW_INDEX.md`
- `docs/reviews/TASK-GITHUB-002/SECURITY_REPORT.md`
- `docs/reviews/TASK-GITHUB-002/TASK_RESULT.md`
- `docs/reviews/TASK-GITHUB-002/TEST_REPORT.md`
- `docs/TASK-GITHUB-001A_RESULT.md`
- `docs/TASK-GITHUB-001B_RESULT.md`
- `README.md`
- `scripts/finalize_task.ps1`
- `scripts/scan_repository_safety.ps1`
- `scripts/start_task.ps1`
- `scripts/validate_review_package.py`
- `tests/conftest.py`
- `tests/test_review_workflow.py`
- `tests/test_task007a_performance.py`
- `tests/test_ui_smoke.py`

## Codex 最不确定的地方

- 无未验证的业务结论；最终是否允许合并仍由总指挥复审决定。

本文件只提供独立审核证据，不声明审核结论；最终是否通过由总指挥判断。
