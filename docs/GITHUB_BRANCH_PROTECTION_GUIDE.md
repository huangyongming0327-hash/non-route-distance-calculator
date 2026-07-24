# master 分支保护设置指南

本任务只提供说明，不自动修改 GitHub 仓库设置。请等本次 Pull Request 的 `Windows offline validation` 检查成功并确认名称稳定后，再决定是否启用。

## 推荐设置

1. 打开 GitHub 仓库网页。
2. 进入 **Settings → Branches**，创建针对 `master` 的 branch protection rule。
3. 开启 **Require a pull request before merging**，让新代码必须经过 Pull Request。
4. 开启 **Require status checks to pass before merging**，选择本仓库实际显示的 `Windows offline validation` 检查。
5. 开启禁止 force push 的设置。
6. 开启禁止删除 `master` 的设置。
7. 不开启自动合并。
8. 管理员保留紧急处理权限，但日常开发仍应遵守 Pull Request 流程。

## 为什么本任务不自动开启

首次 Actions 成功前，GitHub 可能还没有记录可选择的检查名称。过早设置会造成规则选错或无法保存。先确认本 PR 的真实检查名称，再由用户在网页端启用，风险最低。

## 启用后的正常影响

- 不影响已经发布的 V1.0 程序。
- 不删除分支、标签或历史。
- 后续变更不能直接推送到 `master`，必须通过 PR 和检查。
- 脚本仍不会自动合并、创建 Release 或移动标签。
