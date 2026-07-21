# TASK-007 结果：V1.0 正式定版发布

日期：2026-07-21

状态：完成

V1.0 发布源码提交：`8aac1f78f6f4aeae7584ee4a7912678038a22448`

正式标签：`v1.0`

## 完成项

- 完成 Git/标签/分支/跟踪文件门禁检查；没有未提交源码或文档。
- 保留 `task-005a-baseline`、`v1.0-rc1`、RC1 分支、RC1 目录和 RC1 ZIP。
- 将版本常量、VERSION、CHANGELOG、KNOWN_ISSUES、README、状态、用户手册、PDF 和发布脚本更新为正式 V1.0。
- 未修改已验收业务规则；程序标题保持“非线路运距计算工具 V1.0 — 高德普通驾车距离版”。
- 离线测试 `189 passed, 4 skipped`；Office 实机测试 `4 passed`；Excel/WPS 兼容性比较与冻结 EXE Office worker 均通过。
- 使用 PyInstaller onedir 重新打包；正式/中文/空格路径启动均通过。
- 正式目录与 ZIP 安全扫描 0 命中；`config/cache/logs/outputs/temp` 为空。
- 用户实机验收结论已写入正式报告：74 条全部处理，73 条缓存距离，1 条多目的地警告，Excel/WPS 与人工距离检查无明显问题。

## 交付

1. EXE：`D:\AI project\非线路运距计算\release\非线路运距计算工具_V1.0\非线路运距计算工具.exe`
2. ZIP：`D:\AI project\非线路运距计算\release\非线路运距计算工具_V1.0_便携版.zip`
   - SHA-256：`62CAC7C60A81EB7D466EEC6D6098838B00E95987520FB91F016EFA3AA308F9E9`
3. 正式发布报告：`docs\FINAL_RELEASE_REPORT.md`
4. 最终产品测试报告：`docs\FINAL_PRODUCT_TEST_REPORT.md`
5. 打包报告：`docs\PACKAGING_REPORT.md`
6. 安全证据：`docs\evidence\release\security_scan.json`

## 限制

普通驾车不代表货车实际可通行；不考虑限高、限宽、限重、禁行和车牌政策；多目的地需拆分；WPS 依赖 COM；Key 绑定当前 Windows 用户；业务地址备份需受控保存。Windows 11 已验收，Windows 10 未专项实测，首次使用应先用副本测试。

TASK-007 完成后暂停，不继续开发 V1.1。
