# TASK-GITHUB-001B：GitHub V1.0 正式 Release 结果

报告日期：2026-07-23

## 一句话结论

GitHub V1.0 正式下载页面已经创建成功。Release 使用原有 `v1.0` 标签，没有新建或移动标签；正式 ZIP 和使用说明 PDF 已上传，并通过重新下载、哈希核对和解压检查。

## Release 信息

- GitHub 仓库：<https://github.com/huangyongming0327-hash/non-route-distance-calculator>
- 仓库可见性：Private。
- Release 标题：非线路运距计算工具 V1.0
- Release 网页：<https://github.com/huangyongming0327-hash/non-route-distance-calculator/releases/tag/v1.0>
- 使用标签：`v1.0`
- 标签目标：`4075063ff8c0425715bbedbf70b6ffc10dd4ca9e`
- 状态：正式发布，不是 Draft，也不是 Pre-release。

`v1.0` 是首次源码推送时已经存在的正式标签。本任务没有删除、移动或重新创建该标签。

## 下载地址

### 正式便携版 ZIP

- 页面显示名称：`非线路运距计算工具_V1.0_便携版.zip`
- 下载地址：<https://github.com/huangyongming0327-hash/non-route-distance-calculator/releases/download/v1.0/_V1.0_.zip>
- 文件大小：55,208,960 字节。
- SHA-256：`8A33F080F6BF040B122EE6C35335577E3BB0F8D6B9EFE30F58F664BF159F9ED1`

### 使用说明 PDF

- 页面显示名称：`使用说明.pdf`
- 下载地址：<https://github.com/huangyongming0327-hash/non-route-distance-calculator/releases/download/v1.0/default.pdf>
- 文件大小：298,863 字节。
- SHA-256：`2C737ED891F8AAE62171A3495D6858F41B18793DE0287D4B9EB28B344EC2DEBA`

GitHub 会自动把中文附件的实际存储文件名规范化，因此下载链接中的名称分别是 `_V1.0_.zip` 和 `default.pdf`；Release 页面上的中文显示名称已经正确设置。文件内容、大小和 SHA-256 均未改变。

## 附件安全检查

正式 ZIP 上传前和从 GitHub 下载后均已检查：

- ZIP 内共 191 个文件，`_internal` 内有 185 个文件。
- `config`、`cache`、`logs`、`outputs`、`temp` 五个运行目录全部为空。
- EXE、`USER_GUIDE.md`、`使用说明.pdf`、`VERSION.txt`、`CHANGELOG.md`、`KNOWN_ISSUES.md` 均存在。
- `VERSION.txt` 记录正式构建提交 `4075063ff8c0425715bbedbf70b6ffc10dd4ca9e`。
- 真实高德 Key、GitHub Token、DPAPI 凭据、业务 Excel、真实地址库、路线缓存、日志、SQLite、`.py` 源码和 `.venv`：0 命中。
- 从 GitHub 下载的 ZIP SHA-256 与本地正式 ZIP 完全一致。
- 从 GitHub 下载的 PDF SHA-256 与本地正式 PDF 完全一致。
- 下载后的 ZIP 可以正常解压，目录结构完整；验证时没有运行 EXE，也没有调用真实高德 API。
- 下载和解压使用的项目外临时目录已删除。

Release 附件不会进入 Git 提交历史。远程 `master` 中仍不存在 EXE、ZIP 或根目录 `release`。

## 普通用户如何下载

由于仓库是 Private，使用者需要先登录有访问权限的 GitHub 账号，然后：

1. 打开 Release 网页。
2. 在 Assets 区域点击 `非线路运距计算工具_V1.0_便携版.zip`。
3. 下载完成后右键 ZIP，选择“全部解压”。
4. 打开解压后的完整文件夹。
5. 双击“非线路运距计算工具.exe”。
6. 不要直接在 ZIP 内运行，不要只复制 EXE，也不要删除 `_internal`。
7. 第一次使用时，输入当前电脑自己的高德 Web 服务 Key。

目标电脑应使用 Windows 10 或 Windows 11，并至少安装 Microsoft Excel 或 WPS 表格中的一种；不需要安装 Python。

## 下一步如何建立自动审核流程

建议以后单独创建一个安全审核任务，再逐项配置：

1. 每次代码变更先运行离线 pytest，不调用真实高德 API。
2. 自动扫描 Key、Token、业务 Excel、数据库、缓存、日志、EXE 和 ZIP，命中时阻止合并。
3. 对 `master` 启用分支保护，要求测试和安全扫描通过后才能合并。
4. 正式附件继续由人工核对 SHA-256、ZIP 结构和空运行目录。
5. 未来版本仍由人工确认标签和发布说明后再发布，不自动移动标签或自动创建正式 Release。

本任务只完成 V1.0 正式 Release。没有开始 V1.1，没有配置自动合并，也没有配置未来版本自动发布。
