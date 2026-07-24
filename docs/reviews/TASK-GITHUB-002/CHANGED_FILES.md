# TASK-GITHUB-002 变更文件

- 任务名称：建立自动上传与在线审核流程
- 任务分支：`task/TASK-GITHUB-002-review-workflow`

## 新增文件

- `.github/ISSUE_TEMPLATE/bug_report.yml`：属于本任务范围。
- `.github/ISSUE_TEMPLATE/feature_request.yml`：属于本任务范围。
- `.github/pull_request_template.md`：属于本任务范围。
- `.github/workflows/pr-validation.yml`：属于本任务范围。
- `AGENTS.md`：属于本任务范围。
- `docs/CODEX_TASK_TEMPLATE.md`：属于本任务范围。
- `docs/GITHUB_BRANCH_PROTECTION_GUIDE.md`：属于本任务范围。
- `docs/reviews/LATEST_REVIEW.md`：属于本任务范围。
- `docs/reviews/README.md`：属于本任务范围。
- `docs/reviews/TASK_TEMPLATE/AUDIT_INPUT.md`：属于本任务范围。
- `docs/reviews/TASK_TEMPLATE/CHANGED_FILES.md`：属于本任务范围。
- `docs/reviews/TASK_TEMPLATE/KNOWN_ISSUES.md`：属于本任务范围。
- `docs/reviews/TASK_TEMPLATE/REVIEW_INDEX.md`：属于本任务范围。
- `docs/reviews/TASK_TEMPLATE/SECURITY_REPORT.md`：属于本任务范围。
- `docs/reviews/TASK_TEMPLATE/TASK_RESULT.md`：属于本任务范围。
- `docs/reviews/TASK_TEMPLATE/TEST_REPORT.md`：属于本任务范围。
- `docs/reviews/TASK-GITHUB-002/AUDIT_INPUT.md`：属于本任务范围。
- `docs/reviews/TASK-GITHUB-002/CHANGED_FILES.md`：属于本任务范围。
- `docs/reviews/TASK-GITHUB-002/KNOWN_ISSUES.md`：属于本任务范围。
- `docs/reviews/TASK-GITHUB-002/REVIEW_INDEX.md`：属于本任务范围。
- `docs/reviews/TASK-GITHUB-002/SECURITY_REPORT.md`：属于本任务范围。
- `docs/reviews/TASK-GITHUB-002/TASK_RESULT.md`：属于本任务范围。
- `docs/reviews/TASK-GITHUB-002/TEST_REPORT.md`：属于本任务范围。
- `scripts/finalize_task.ps1`：属于本任务范围。
- `scripts/scan_repository_safety.ps1`：属于本任务范围。
- `scripts/start_task.ps1`：属于本任务范围。
- `scripts/validate_review_package.py`：属于本任务范围。
- `tests/test_review_workflow.py`：属于本任务范围。

## 修改文件

- `CURRENT_STATUS.md`：属于本任务范围。
- `docs/CURRENT_STATUS.md`：属于本任务范围。
- `docs/TASK-GITHUB-001A_RESULT.md`：属于本任务范围。
- `docs/TASK-GITHUB-001B_RESULT.md`：属于本任务范围。
- `README.md`：属于本任务范围。

## 删除文件

- 无

## 代码增删行统计

```text
 .github/ISSUE_TEMPLATE/bug_report.yml           |  81 +++
 .github/ISSUE_TEMPLATE/feature_request.yml      |  71 ++
 .github/pull_request_template.md                |  45 ++
 .github/workflows/pr-validation.yml             |  81 +++
 AGENTS.md                                       |  78 +++
 CURRENT_STATUS.md                               |  61 +-
 README.md                                       |   5 +-
 docs/CODEX_TASK_TEMPLATE.md                     |  76 +++
 docs/CURRENT_STATUS.md                          |   2 +
 docs/GITHUB_BRANCH_PROTECTION_GUIDE.md          |  25 +
 docs/TASK-GITHUB-001A_RESULT.md                 |   6 +-
 docs/TASK-GITHUB-001B_RESULT.md                 |   4 +-
 docs/reviews/LATEST_REVIEW.md                   |  47 ++
 docs/reviews/README.md                          |  23 +
 docs/reviews/TASK-GITHUB-002/AUDIT_INPUT.md     |  91 +++
 docs/reviews/TASK-GITHUB-002/CHANGED_FILES.md   |  63 ++
 docs/reviews/TASK-GITHUB-002/KNOWN_ISSUES.md    |  24 +
 docs/reviews/TASK-GITHUB-002/REVIEW_INDEX.md    |  77 +++
 docs/reviews/TASK-GITHUB-002/SECURITY_REPORT.md |  20 +
 docs/reviews/TASK-GITHUB-002/TASK_RESULT.md     |  41 ++
 docs/reviews/TASK-GITHUB-002/TEST_REPORT.md     |  35 +
 docs/reviews/TASK_TEMPLATE/AUDIT_INPUT.md       |  41 ++
 docs/reviews/TASK_TEMPLATE/CHANGED_FILES.md     |  25 +
 docs/reviews/TASK_TEMPLATE/KNOWN_ISSUES.md      |  24 +
 docs/reviews/TASK_TEMPLATE/REVIEW_INDEX.md      |  42 ++
 docs/reviews/TASK_TEMPLATE/SECURITY_REPORT.md   |  20 +
 docs/reviews/TASK_TEMPLATE/TASK_RESULT.md       |  28 +
 docs/reviews/TASK_TEMPLATE/TEST_REPORT.md       |  26 +
 scripts/finalize_task.ps1                       | 837 ++++++++++++++++++++++++
 scripts/scan_repository_safety.ps1              | 217 ++++++
 scripts/start_task.ps1                          | 125 ++++
 scripts/validate_review_package.py              | 164 +++++
 tests/test_review_workflow.py                   | 242 +++++++
 33 files changed, 2700 insertions(+), 47 deletions(-)
```

## 范围与核心业务

- 所有变更是否属于任务范围：是。
- 是否修改核心业务文件：否；任务只涉及开发流程、测试、GitHub 配置和文档。
