# TASK-GITHUB-001A：GitHub 首次安全推送结果

报告日期：2026-07-23

## 一句话结论

项目的清理后安全历史已经成功上传到 GitHub 私有仓库。`master` 已作为默认分支，并代表当前最新稳定 V1.0。没有上传 EXE、ZIP、业务数据或含敏感历史的本地 Bundle。

## GitHub 仓库

- 仓库网页：<https://github.com/huangyongming0327-hash/non-route-distance-calculator>
- 仓库可见性：Private，仅获得权限的账号可访问。
- 登录账号：`huangyongming0327-hash`
- 本地远程名称：`origin`
- 远程地址：`https://github.com/huangyongming0327-hash/non-route-distance-calculator.git`
- 默认分支：`master`

远程地址不含密码或 Token。电脑使用 Git Credential Manager 的浏览器授权保存登录状态。

## 已上传的分支

| 分支 | 用途 | 首次上传时提交 |
|---|---|---|
| `master` | GitHub 默认分支、最新稳定 V1.0 | `ce74ad28b3cda0e30bce0833b4e9adefac940a6d`，本报告提交后继续顺向增加一条纯文档提交 |
| `release/v1.0` | V1.0 正式发布分支 | `ce74ad28b3cda0e30bce0833b4e9adefac940a6d` |
| `release/v1.0-rc1` | V1.0 历史候选版本 | `96dc005c9e9681f017d602c432dca847ddb7f251` |
| `fix/task-005a-responsive-ui` | TASK-005A 界面修复历史 | `9f8f293e523c72d2d4ec4b97e5da9a2227da2100` |

所有本地分支都有明确历史价值，因此没有未上传的本地分支。没有删除任何本地历史分支，没有使用强制推送。

## 已上传的标签

| 标签 | 指向的清理后安全提交 |
|---|---|
| `v1.0` | `4075063ff8c0425715bbedbf70b6ffc10dd4ca9e` |
| `task-005a-baseline` | `d178c23914041f9a96ebd1210fac251c7d0181c5` |
| `v1.0-pre-task008` | `9e15d21a9b9368a1092cb806f7e45baffc641420` |
| `v1.0-rc1` | `96dc005c9e9681f017d602c432dca847ddb7f251` |

`v1.0` 是注释标签，仍固定指向清理后的正式构建提交。本次推送没有移动该标签。

## 当前正式版本

- 版本：V1.0
- 正式构建提交：`4075063ff8c0425715bbedbf70b6ffc10dd4ca9e`
- 正式标签：`v1.0`
- 稳定主线：`master`
- 正式发布分支：`release/v1.0`

`master` 已通过安全 fast-forward 更新到 `release/v1.0` 的最新稳定内容，没有产生额外合并提交，也没有修改业务代码。

## 安全扫描结论

- 完整 Git 历史中的明文高德 Key、GitHub Token、password、secret、credential 和私钥：0 命中。
- 未审计的手机号、真实业务地址、客户或仓库信息、业务坐标：0 命中。
- 被 Git 跟踪的 EXE、ZIP、根目录 `release`、运行缓存、日志、业务 Excel、SQLite、`.env`：0 个。
- Git 历史中超过 50 MiB / 100 MiB 的文件：0 / 0。
- 已清理的业务 JSON、地址确认截图、业务结果截图和验收元数据：在全部分支、标签和对象中均为 0 命中。
- 测试代码中保留的手机号和坐标只用于固定合成测试，已经逐项复核，不来自真实业务。
- 项目外应急 Bundle 包含清理前敏感历史，未进入项目目录，也未被 Git 跟踪或上传。

详细清理记录见 `docs/TASK-GITHUB-HISTORY-CLEAN_RESULT.md`。

## GitHub 远程验证

- GitHub 确认为 Private 仓库。
- `master`、`release/v1.0` 和两个历史分支均可见。
- 4 个标签均可见，`v1.0` 指向 `4075063ff8c0425715bbedbf70b6ffc10dd4ca9e`。
- `README.md`、`src`、`tests`、`scripts`、`docs`、`CURRENT_STATUS.md`、`CHANGELOG.md`、`KNOWN_ISSUES.md`、`VERSION.txt` 和 `.gitignore` 均可从远程完整克隆。
- 临时克隆默认进入 `master`，对象检查通过，禁入路径 0，工作区干净。
- 临时克隆过程中未运行程序、未构建、未调用真实高德 API；验证后临时目录已删除。

## 还需要用户操作吗

本次首次源码推送不需要额外网页操作。默认分支已经设置为 `master`。

本任务没有创建 GitHub Release，没有上传正式便携版 ZIP 或 EXE，也没有开始 V1.1。仓库中保留的《使用说明.pdf》属于已完成安全审计的开发文档，不是便携版发布附件。

## 下一步：以后创建 V1.0 下载页面

等用户单独授权创建 GitHub Release 后，再执行以下操作：

1. 打开仓库网页的 Releases 页面。
2. 选择现有标签 `v1.0`，不要新建或移动标签。
3. 发布标题建议使用“非线路运距计算工具 V1.0”。
4. 上传经过 SHA-256 核对的正式便携版 ZIP。
5. 在发布说明中写明 Windows、Excel/WPS 要求，以及普通驾车距离不代表货车实际可通行。

以上 Release 操作不属于本任务，本次已在首次代码和文档推送完成后暂停。
