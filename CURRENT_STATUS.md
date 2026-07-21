# 当前状态：V1.0 RC1 已完成，等待用户实机验收

更新时间：2026-07-21

## 发布状态

- 当前分支：`release/v1.0-rc1`
- 功能冻结提交：`62ad85b81e8f77cf9b2118463af25d08182be536`
- 已验收基线标签：`task-005a-baseline`（保留）
- 发布候选版本：V1.0 RC1
- 正式 V1.0：尚未发布

## 已完成

- `master` 已快进合并 TASK‑005A 响应式三页签 UI、可信地址库、确认清单表头识别和启动脚本修复。
- 正式启动不再扫描或加载样表，不打开 Excel/WPS，不调用高德 API；用户选择文件后才读取工作簿。
- 运行数据使用便携版目录下的 `config/cache/logs/outputs/temp`。
- 增加可信地址库与普通驾车缓存的安全 JSON 导入/导出。
- PyInstaller 6.21.0 onedir 便携版构建成功，无 Python/`.venv`/源码依赖。
- Excel、WPS、宏 `.xlsm`、冻结 EXE Office 辅助入口均已实机通过。
- 中文路径、带空格路径和无源码/无 `.venv` 启动通过，主窗口最慢 2.272 秒出现。
- 用户手册 Markdown 与 5 页 PDF 已完成视觉核验。
- 发布目录安全扫描通过：无 Key、凭据、业务 Excel、SQLite、日志、缓存或输出。

## 测试摘要

- 合并前离线测试：182 passed，2 skipped。
- RC1 最终离线测试：189 passed，4 skipped；4 项为默认关闭且已单独实机通过的 Office 测试。
- Office 实机测试：4 passed（Excel/WPS 注册与 `.xlsm` 宏夹具）。
- 业务 `.xlsx`：Excel/WPS 均生成有效 `.xlsm`，73 条缓存距离、1 条多目的地待确认、0 次 HTTP，280 行结果一致。
- 冻结 EXE：Excel/WPS 辅助进程均通过 VBA 保留、宏禁用、进程释放和既有窗口保护。

## 当前交付路径

- EXE：`D:\AI project\非线路运距计算\release\非线路运距计算工具_V1.0_RC1\非线路运距计算工具.exe`
- ZIP：`D:\AI project\非线路运距计算\release\非线路运距计算工具_V1.0_RC1_便携版.zip`
- 用户手册：`docs\USER_GUIDE.md`
- PDF：`output\pdf\使用说明.pdf`，并复制到发布目录。

## 下一步

请用户在目标电脑完成首次 Key 保存/连接、实际业务样表、Excel/WPS 和 Windows 10/11 验收。通过后再决定是否把 RC1 升级为正式 V1.0；本任务不会自行宣布正式发布。
