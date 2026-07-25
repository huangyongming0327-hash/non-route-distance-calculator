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
5. 审核文件推送完成后，脚本核对 PR 当前 HEAD，并等待该 HEAD 对应的 GitHub Actions 完成。
6. 脚本从 GitHub、Git、pytest 和安全扫描结果生成完整的
   `【可直接复制给总指挥审核】` 通知；Codex 必须把整段通知放在最终回复最末尾。
7. 用户只需复制通知给总指挥，由总指挥通过 `LATEST_REVIEW.md`、任务审核目录与 Pull Request 独立审核。

脚本不会自动合并 Pull Request、移动标签、创建 Release 或发布正式版本。

## 固定总指挥通知

通知自动填写项目和任务信息、GitHub 仓库、PR 地址和编号、当前分支、PR 当前 HEAD、
Actions 最终状态和运行地址、固定审核入口、任务审核目录、pytest 和安全扫描结果，
以及 Draft、合并、master、Release 和正式标签状态。

- 通知不得含尖括号占位符。
- PR 地址、当前 HEAD 或 Actions 信息缺失时，脚本停止且不输出完成通知。
- Actions 未完成时继续等待；Actions 失败时明确输出失败。
- 通知只能在审核文件已推送后生成。
- 通知的结束分隔线必须是 Codex 最终回复的最后内容，方便一次复制。
