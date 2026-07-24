# TASK-GITHUB-002 审核首页

- 任务名称：建立自动上传与在线审核流程（审核修复阶段）
- 任务分支：`task/TASK-GITHUB-002-review-workflow`
- 基础分支：`master`
- 基础 Commit：`290153e240f059f7e3ffda34476446d77da409b8`
- 审核目标：Pull Request 当前 HEAD
- 生成证据 Commit：`63fd9c2113854bd218fa5207e72595b82756df42`
- Pull Request：https://github.com/huangyongming0327-hash/non-route-distance-calculator/pull/1

## 任务目标

- 移除安全扫描对测试、合成或模拟文件的个人数据豁免。
- 扫描任务分支提交历史，敏感内容即使随后删除也必须阻止推送。
- 让 finalize_task.ps1 从任务上下文与实际证据生成审核材料，不自行推断业务结论。
- 让最新审核入口、独立审核输入和变更清单与当前 Pull Request 一致。

## 实际完成范围

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

## 未完成范围

- 不合并 Pull Request。
- 不修改 master。
- 不创建 Release，不移动 v1.0 标签。
- 分支保护设置继续由用户在 GitHub 网页决定。

## 审核材料入口

- [任务结果](TASK_RESULT.md)
- [测试报告](TEST_REPORT.md)
- [变更文件](CHANGED_FILES.md)
- [安全报告](SECURITY_REPORT.md)
- [已知问题](KNOWN_ISSUES.md)
- [独立审核输入](AUDIT_INPUT.md)

## 重点风险

- 安全扫描必须覆盖当前差异和分支中已经删除的历史内容，同时不得输出完整敏感值。
- 审核报告中的业务影响、风险和合并建议只能来自本上下文，不能由脚本猜测。
- 修复必须继续兼容 Windows PowerShell 5.1 和 GitHub Actions。

## 推荐审核顺序

1. `TASK_RESULT.md`
2. `CHANGED_FILES.md`
3. `TEST_REPORT.md`
4. `SECURITY_REPORT.md`
5. `KNOWN_ISSUES.md`
6. `AUDIT_INPUT.md`
