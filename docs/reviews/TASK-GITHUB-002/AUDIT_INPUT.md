# TASK-GITHUB-002 独立审核输入

- 任务名称：建立自动上传与在线审核流程
- 任务分支：`task/TASK-GITHUB-002-review-workflow`
- 修改前 Commit：`290153e240f059f7e3ffda34476446d77da409b8`
- 修改后实现 Commit：`68c25096357a863cb8770195c9d8215165b5598a`
- Pull Request：https://github.com/huangyongming0327-hash/non-route-distance-calculator/pull/1

## 用户需求原文摘要

建立 Codex 自动上传与 GitHub 在线审核流程；每个任务从最新 master 建分支，完成测试、安全扫描、审核材料、提交、推送和 PR，禁止自动合并、发布、移动标签或上传业务数据。

## 验收标准

- 分支、模板、脚本、GitHub 模板和离线 Actions 齐全。
- 完整离线测试、专项测试、编译检查、差异检查、安全扫描和审核材料检查实际通过。
- 任务分支已推送，PR 地址回写，PR 未合并。

## git diff 统计

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

## 核心改动位置

- `.github/ISSUE_TEMPLATE/bug_report.yml`：属于本任务范围。
- `.github/ISSUE_TEMPLATE/feature_request.yml`：属于本任务范围。
- `.github/pull_request_template.md`：属于本任务范围。
- `.github/workflows/pr-validation.yml`：属于本任务范围。
- `AGENTS.md`：属于本任务范围。
- `CURRENT_STATUS.md`：属于本任务范围。
- `docs/CODEX_TASK_TEMPLATE.md`：属于本任务范围。
- `docs/CURRENT_STATUS.md`：属于本任务范围。
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
- `docs/TASK-GITHUB-001A_RESULT.md`：属于本任务范围。
- `docs/TASK-GITHUB-001B_RESULT.md`：属于本任务范围。
- `README.md`：属于本任务范围。
- `scripts/finalize_task.ps1`：属于本任务范围。
- `scripts/scan_repository_safety.ps1`：属于本任务范围。
- `scripts/start_task.ps1`：属于本任务范围。
- `scripts/validate_review_package.py`：属于本任务范围。
- `tests/test_review_workflow.py`：属于本任务范围。

## 测试命令和原始结果摘要

- `.\.venv\Scripts\python.exe -m pytest -q`：206 passed, 4 skipped in 15.91s
- `.\.venv\Scripts\python.exe -m compileall -q src scripts tests`：通过。
- `git diff --check`：通过。
- 安全扫描：0 命中。
- 真实 API 调用次数：0。

## 已知风险

- PowerShell 脚本主要面向 Windows、Git 和 GitHub CLI 环境。
- GitHub Actions 检查名称应在首次运行成功后再用于分支保护。

## 重点检查路径

- `scripts/start_task.ps1`
- `scripts/finalize_task.ps1`
- `scripts/scan_repository_safety.ps1`
- `scripts/validate_review_package.py`
- `.github/workflows/pr-validation.yml`

## Codex 最不确定的地方

- 不同 GitHub 账号或企业策略下，草稿 PR 和分支保护设置的网页选项可能略有差异。

本文件只提供独立审核证据，不声明审核结论；最终是否通过由总指挥判断。
