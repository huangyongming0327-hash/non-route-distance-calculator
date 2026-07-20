# TASK-003B RESULT

任务：核心业务原型与模拟 API 端到端验证  
状态：**已完成，阶段 3B 停止**  
日期：2026-07-20

## 1. 实际完成

- 建立 `src/ui`、`application`、`domain`、`office`、`workbook`、`validation`、`amap`、`cache`、`config`、`utils` 分层源码；
- 完成可运行 PySide6 主流程原型；
- 完成工作表/表头/六字段映射、只读预览和用户确认；
- 完成精确“非线路报价”、地址清洗、多目的地、城市冲突、空地址和车型映射；
- 完成完整模拟与仅本地校验两种模式；
- 完成确定性 mock 地理编码/货车路线和 mock 独立缓存；
- 完成 SQLite WAL、五张表、增量/强制模式、任务水位和失败恢复；
- 完成暂停/继续/停止状态机和 10 行/60 秒检查点；
- 完成 Excel 独立 worker/PID 安全后端和 WPS 新 ET 隔离后端；
- 完成动态结果列、模拟警告、红/黄条件格式和重开验证；
- 完成 Excel/WPS 样表真实端到端输出和 95 项自动化测试；
- 更新 README、CURRENT_STATUS、依赖清单和 3B 文档。

## 2. 启动方式

双击：

```text
D:\AI project\非线路运距计算\scripts\run_prototype.bat
```

命令行：

```powershell
cd "D:\AI project\非线路运距计算"
.\.venv\Scripts\python.exe -m src.main
```

## 3. 当前界面

当前不是最终产品 GUI，而是一个可运行的单窗口业务原型，包含：

- 工作簿、输出目录、工作表和表头；
- 六字段映射下拉框和前 10 行预览；
- Excel/WPS 安装状态与引擎选择；
- 完整模拟/仅本地校验；
- 大号红色模拟数据警告和映射确认框；
- 运行前摘要；
- 进度、当前 Excel 行、目标/成功/警告/缓存统计；
- 开始、暂停、继续、停止、打开结果、打开目录和日志。

## 4. 模拟与缓存

- 未调用任何高德接口，也未请求或保存 API Key。
- 模拟坐标和距离来自输入 SHA-256，可重复、不可随机漂移。
- 所有 mock 结果说明均包含“模拟数据，不可用于正式业务”。
- 新鲜样表运行得到 29 个 geocode 缓存、33 个 route 缓存和 40 次路线复用。
- Excel 交付结果显示 44 个“缓存复用—模拟数据”状态；WPS 在共享暖缓存后显示 70 个。冲突行即使命中缓存，状态仍优先显示冲突警告。

## 5. 任务控制

- RUNNING/PAUSING/PAUSED/STOPPING/STOPPED/COMPLETED/FAILED 已实现。
- 暂停/停止在行事务后生效；先写 SQLite，再保存 Office。
- 正常每 10 行或 60 秒保存；暂停、停止、完成强制保存。
- 保存失败保留 partial 和数据库；恢复只重新处理保存水位后的行或输入已变化行。
- WPS 故障任务已实测从水位 50、70 分次恢复并完成。

## 6. Excel/WPS 实测

| 项目 | Excel | WPS |
| --- | --- | --- |
| 8 个检查点保存 | 通过 | 通过 |
| FileFormat=52 / 重开 | 通过 | 通过 |
| 专属实例归属 | 新 Excel Hwnd/PID | 唯一新 ET Hwnd/PID |
| 用户进程/窗口保护 | 通过 | 7 个既有 PID 和可见窗口不变 |
| 工具进程残留 | 无；精确 PID 兜底 | 无 |
| 16 个异常单元格红色 DisplayFormat | 通过 | 通过 |
| 原公式/图片/筛选/隐藏行/原 CF | 通过 | 通过 |

## 7. 样表端到端

- 目标行 74；有模拟距离 73；
- 行 248 多目的地，距离空；
- 行 39、78、272 地址冲突，仍有模拟距离；
- 三种货车 size 覆盖；
- Q/R/S 动态结果列，非目标行未写；
- 245 个公式、5 个 DISPIMG、2 个 JPEG、206 个隐藏行、原 3 条条件格式保留；
- 源 SHA-256、大小和修改时间不变；
- Excel/WPS 验证 JSON 均 `passed=true`。

## 8. 测试统计

- pytest：**95 passed，0 failed**；
- Excel 完整 E2E：通过；
- WPS 完整 E2E：通过；
- Excel/WPS 条件格式 COM DisplayFormat：通过；
- 电子表格结构/视觉 QA：通过（渲染器不支持 DISPIMG，图片结论使用 OOXML/Office 证据）。

## 9. 未完成

本任务按边界没有完成：

- 真实高德地理编码/专业货车路线和 Key 管理；
- 正式距离和距离单位确认；
- 真实 API 错误码、额度、限流和网络恢复；
- 多目的地拆分/顺序、多工作簿/多工作表；
- 费用、时间、正式产品 GUI、EXE 和 PDF；
- 任意 Office 版本或复杂宏对象完全兼容。

## 10. 阶段 4 建议与用户需提供

建议在单独的 TASK-004 中进行真实 API 联调，并保持 `mode=real` 与 mock 缓存完全隔离。

用户需提供：

1. 总指挥明确的阶段 4 授权；
2. 已开通高德 Web 服务专业货车路径规划权限的 Key；
3. 至少 3 条已知公路距离的脱敏对照线路；
4. 是否允许保存脱敏后的原始 API 响应和 steps 汇总；
5. 额度、QPS、重试和日常调用量预期。

只有 `paths.distance`、steps 距离汇总和已知线路对照共同确认单位后，才能把返回值换算为正式公里数。

## 11. 交付路径

- 启动脚本：`D:\AI project\非线路运距计算\scripts\run_prototype.bat`
- 设计：`D:\AI project\非线路运距计算\docs\PROTOTYPE_DESIGN.md`
- 测试：`D:\AI project\非线路运距计算\docs\PROTOTYPE_TEST_REPORT.md`
- Excel：`D:\AI project\非线路运距计算\samples\expected\prototype\Excel_样表_模拟结果.xlsm`
- WPS：`D:\AI project\非线路运距计算\samples\expected\prototype\WPS_样表_模拟结果.xlsm`

TASK-003B 至此停止。未继续开发阶段 4、真实 API、正式 GUI 或 EXE。
