# TASK-003A 执行结果

状态：**已完成；建议允许进入阶段 3B。**  
完成日期：2026-07-20

## 实际执行

- 更新技术方案中的阶段顺序、WPS 声明门槛、Q/R/S 列位置、筛选保护和高德距离单位门槛。
- 建立 `samples\working\office_spike`、`samples\expected\office_spike`、`logs\office_spike` 和 `tests\fixtures`。
- 生成组合 OOXML、Python、Excel COM、WPS COM 的 `source_baseline.json`。
- 使用复制件完成 Excel A/B 与 WPS C/D 四组真实保存、宏禁用重开和逐文件对比。
- 创建安全 VBA 夹具，实测 Excel/WPS 的宏不自动运行、VBA 源码/按钮/形状/公式保留。
- 完成 25 张 DISPIMG 位置截图与人工视觉复核。
- 最终复核原样表哈希、大小和修改时间完全未变。

## 通过项

- Excel 和 WPS 的 `.xlsx → .xlsm` 与已有 `.xlsm` 再次 `Save()`；
- 有效 OOXML、宏启用 ContentType、FileFormat=52、Excel/WPS 重开；
- 74 个精确目标行、特殊第 248 行、非目标行 Q/R/S 空白；
- 245 个原公式、5 个 DISPIMG、2 个 JPEG、cellimages 部件；
- 3 条条件格式、原筛选语义、206 个隐藏行、冻结窗格、工作表和定义名称；
- Excel/WPS 宏禁用与无签名 VBA 组件/源码保留；
- WPS 专属进程退出且用户原窗口不受影响；
- Excel 专属 PID 在安全所有权条件下最终无残留；
- 原样表未修改。

四个 comparison JSON 的关键失败数均为 0。

## 已发现但不阻塞 3B 的差异

1. Excel 保存规范化 7 个原单元格样式：A2、P239、P240、P246、P249、P277、P280；原值与原公式未变。
2. Excel `Quit()` 后 15 秒内专属进程仍可能驻留；必须使用独立辅助进程和“归属已确认 + Workbooks.Count=0 + 单 PID”精确回收兜底。
3. WPS 把筛选内部表示等价改写为 `CustomFilters equal`，筛选条件和可见结果不变。
4. Excel/WPS 保存都会改变 `vbaProject.bin` 二进制哈希，但 VBA 组件和源码逐行一致。数字签名保持未实测。

## 未执行/未覆盖

- VBA 数字签名、ActiveX、UserForm、受保护 VBA 工程和 Excel 4.0 宏；
- 其他 Office/WPS 版本和第三方加载项组合；
- 完整 GUI、真实高德 API、正式缓存、EXE 和端到端业务流程。

## 阶段 3B 准入

**建议：是。** TASK-003A 没有关键失败，Office 保存核心路径已经用真实 Excel/WPS 实机验证。阶段 3B 必须继承本报告的进程隔离、宏安全、保存后重开/对比和兼容声明边界；不得把本次结论扩大为“任意版本完全无损兼容”。

## 主要交付物

- `CURRENT_STATUS.md`
- `docs\OFFICE_COMPATIBILITY_SPIKE.md`
- `docs\TASK-003A_RESULT.md`
- `samples\expected\office_spike\source_baseline.json`
- `samples\expected\office_spike\Excel_样表转换结果.xlsm`
- `samples\expected\office_spike\Excel_xlsm再次保存结果.xlsm`
- `samples\expected\office_spike\WPS_样表转换结果.xlsm`
- `samples\expected\office_spike\WPS_xlsm再次保存结果.xlsm`
- 四个对应的 `*_comparison.json`
- `tests\fixtures\office_spike_macro_fixture.xlsm`
- `tests\fixtures\office_spike_macro_fixture_wps_saved.xlsm`
- `logs\office_spike` 下的进程、宏、视觉和原件完整性审计日志
