# TASK-GITHUB-002 变更文件

- 任务名称：建立自动上传与在线审核流程（审核修复阶段）
- 任务分支：`task/TASK-GITHUB-002-review-workflow`

## 新增文件

- `.github/ISSUE_TEMPLATE/bug_report.yml`
- `.github/ISSUE_TEMPLATE/feature_request.yml`
- `.github/pull_request_template.md`
- `.github/workflows/pr-validation.yml`
- `AGENTS.md`
- `docs/CODEX_TASK_TEMPLATE.md`
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
- `scripts/finalize_task.ps1`
- `scripts/scan_repository_safety.ps1`
- `scripts/start_task.ps1`
- `scripts/validate_review_package.py`
- `tests/test_review_workflow.py`

## 修改文件

- `CURRENT_STATUS.md`
- `docs/CURRENT_STATUS.md`
- `docs/TASK-GITHUB-001A_RESULT.md`
- `docs/TASK-GITHUB-001B_RESULT.md`
- `README.md`
- `tests/conftest.py`
- `tests/test_task007a_performance.py`
- `tests/test_ui_smoke.py`

## 删除文件

- 无

## 代码增删行统计

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

## 范围与核心业务

- 所有变更是否属于任务范围：是；实际范围以本报告中的 Git diff 文件列表为准。
- 是否修改核心业务文件：否；本修复不修改 src 下的运距计算业务实现。
