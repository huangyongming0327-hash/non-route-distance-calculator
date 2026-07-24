# TASK-GITHUB-002 审核首页

- 任务名称：建立自动上传与在线审核流程
- 任务分支：`task/TASK-GITHUB-002-review-workflow`
- 基础分支：`master`
- 基础 Commit：`290153e240f059f7e3ffda34476446d77da409b8`
- 实现 Commit：`290153e240f059f7e3ffda34476446d77da409b8`
- Pull Request：首次实现提交后由脚本创建并回写

## 任务目标

完成 建立自动上传与在线审核流程，并建立可重复执行的分支、测试、安全扫描、审核材料、推送和 Pull Request 流程。

## 实际完成范围

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

## 未完成范围

- 未自动合并 Pull Request。
- 未创建或移动标签。
- 未创建 GitHub Release 或新正式版本。

## 审核材料入口

- [任务结果](TASK_RESULT.md)
- [测试报告](TEST_REPORT.md)
- [变更文件](CHANGED_FILES.md)
- [安全报告](SECURITY_REPORT.md)
- [已知问题](KNOWN_ISSUES.md)
- [独立审核输入](AUDIT_INPUT.md)

## 重点风险

- 请重点确认自动化脚本的失败即停止、分支保护和显式暂存边界。
- 请确认 GitHub Actions 只执行离线验证。

## 推荐审核顺序

1. `TASK_RESULT.md`
2. `CHANGED_FILES.md`
3. `TEST_REPORT.md`
4. `SECURITY_REPORT.md`
5. `KNOWN_ISSUES.md`
6. `AUDIT_INPUT.md`
