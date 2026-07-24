# 任务审核材料

`docs/reviews/LATEST_REVIEW.md` 是最新待审核任务的固定入口。每个任务在 `docs/reviews/<TaskId>/` 下保存一套独立、可追溯的审核材料。

每套材料必须包含：

- `REVIEW_CONTEXT.json`：任务提供的目标、影响、风险、验收标准和合并建议；不得保留模板占位。
- `REVIEW_INDEX.md`
- `TASK_RESULT.md`
- `TEST_REPORT.md`
- `CHANGED_FILES.md`
- `SECURITY_REPORT.md`
- `KNOWN_ISSUES.md`
- `AUDIT_INPUT.md`

## 标准流程

1. 在干净工作区运行 `scripts/start_task.ps1`，从最新 `origin/master` 创建任务分支和审核目录。
2. 完成任务范围内的修改，并填写 `REVIEW_CONTEXT.json`。
3. 运行离线测试、专项测试、编译检查、差异检查和安全扫描。
4. 运行 `scripts/finalize_task.ps1`。脚本只从任务上下文和实际 Git、测试、安全证据生成报告，然后显式暂存、提交、推送并创建或更新草稿 Pull Request。
5. 由用户和总指挥通过 `LATEST_REVIEW.md` 与 Pull Request 独立审核。

脚本不会自动合并 Pull Request、移动标签、创建 Release 或发布正式版本。
