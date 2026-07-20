# TASK-003B 原型测试报告

测试日期：2026-07-20  
结论：**通过；仅代表阶段 3B 模拟原型，不代表真实高德距离可用。**

## 1. 环境

| 项目 | 实测 |
| --- | --- |
| Windows | Windows 11 64 位 |
| Python | 3.12.10 |
| PySide6 | 6.9.1 |
| openpyxl | 3.1.5 |
| pywin32 | 312 |
| Microsoft Excel | 16.0 Build 20131，64 位 |
| WPS 表格 | COM Version 12.0、Build 26895；安装包 12.1.0.26895 |

样表：`samples/input/副本26年6月干线账单 2.1-对账2.0-物流商(2).xlsx`。

源文件基线：828,799 字节，SHA-256 `52011587F8F12A87749087ABEA0ADCE2557874D1B268A55F348E86F8DFA7A951`。

## 2. 自动化测试

命令：

```powershell
$env:RUN_OFFICE_TESTS='1'
.\.venv\Scripts\python.exe -m pytest -q
```

结果：**95 passed，0 failed，58.56 秒**。

覆盖：

- 报价精确匹配、全角/不可见/NBSP 规范化；
- 地址清洗、手机号/座机/联系人、门牌和 POI 保留；
- 多目的地、上下级行政关系和城市冲突；
- 4.2/6.8/7.6/9.6/13 与未知车型；
- mock 确定性、路线键不含 Excel 行号；
- SQLite WAL、五张表、幂等缓存和行摘要；
- 样表动态表头、字段推荐、样式空壳忽略和同名结果列复用；
- 74 条样表业务验收、仅本地校验、空地址/未知车型短路；
- 增量未变化复用、变化重算、force all 和保存水位恢复；
- 任务暂停/继续/停止/完成/失败状态机；
- OOXML/XLM 预检和源文件指纹保护；
- Excel/WPS COM 注册探测。
- PySide6 主窗口离屏启动、样表加载和人工确认门槛。

## 3. 新鲜缓存业务结果

单元/集成测试用空数据库运行样表：

| 指标 | 结果 |
| --- | ---: |
| 目标“非线路报价” | 74 |
| 有模拟距离 | 73 |
| 多目的地留空 | 1（Excel 行 248） |
| 城市冲突 | 3（Excel 行 39、78、272） |
| 地址空白 | 0 |
| 未识别车型 | 0 |
| 模拟地理编码缓存 | 29 |
| 模拟路线组合 | 33 |
| 路线缓存复用 | 40 |

重复路线跨行复用；路线键只有 mode、算法版本、起终点和车型 size，不含 Excel 行号。

## 4. Excel 端到端

命令：

```powershell
.\.venv\Scripts\python.exe scripts\run_e2e.py excel --checkpoint-batch 10
```

完整任务：`20260720031033_da3b1128`。

- 10/20/30/40/50/60/70/74 共 8 个 Office 保存检查点；
- 首次 `.xlsx → .partial.xlsm` 使用 FileFormat=52，后续 `Workbook.Save()`；
- 独立 worker、`DispatchEx`、Hwnd/PID 归属、宏/事件/外链禁用均通过；
- 8 个写入会话均在 `Quit()` 后出现专属 PID 残留，均只在 `Workbooks.Count=0` 后精确回收该 PID；
- 无 Excel 进程残留，用户进程集合未变化；
- 宏禁用只读重开通过。

结果：`samples/expected/prototype/Excel_样表_模拟结果.xlsm`，828,742 字节，SHA-256 `D80B2DF5466861E5FD69B656DB529A1ADBBAFD99F7798E433F88CCF082555B2C`。

## 5. WPS 端到端

命令：

```powershell
.\.venv\Scripts\python.exe scripts\run_e2e.py wps --checkpoint-batch 10
```

最新完整任务：`20260720032620_0de81b2e`。

- 10/20/30/40/50/60/70/74 共 8 个保存检查点；
- 每个会话都出现唯一新 ET PID，COM Hwnd 映射到该 PID；
- 工具 ET/伴生进程全部退出；
- 测试前已有 7 个 ET/WPS PID 和可见样表窗口不变；
- 无窗口云后台服务 PID 单独记录，不影响用户工作簿硬性保护；
- 宏禁用只读重开通过。

结果：`samples/expected/prototype/WPS_样表_模拟结果.xlsm`，831,756 字节，SHA-256 `D137C906FA8FF5B0E888465D7BF9F447BCF810F29AC70AD2F2DCF2F1C3F4339B`。

WPS 初版测试发现相对条件格式行引用被重写到 1,048,313 行。规则改为 `INDEX(有界绝对范围,ROW())` 后重新完成全部 8 个检查点，错误引用不再存在。

## 6. 工作簿验收

Excel/WPS 两份结果均通过：

| 验收项 | 结果 |
| --- | --- |
| 真正 `.xlsm` / ZIP 完整性 / FileFormat=52 | 通过 |
| 74 个目标状态，73 个距离 | 通过 |
| 非目标 Q/R/S 不写入 | 通过 |
| 行 248 多目的地、距离空 | 通过 |
| 行 39/78/272 冲突、仍有模拟距离 | 通过 |
| Q/R/S 表头和 1 位小数 | 通过 |
| 说明全部含“模拟数据，不可用于正式业务” | 通过 |
| 原 A:P 值/公式 | 通过 |
| 245 个公式、5 个 DISPIMG | 通过 |
| 2 个 JPEG 名称/哈希 | 通过 |
| 原筛选和 206 个隐藏行 | 通过 |
| 原 3 条条件格式 | 通过 |
| 工具规则唯一标记和有界公式 | 通过 |

Excel 会把相邻同公式区域合并，工具规则序列化为 5 条；WPS 序列化为 7 条。两种表示语义相同。

## 7. 条件格式实机验证

脚本：

```powershell
.\.venv\Scripts\python.exe scripts\verify_cf_com.py excel
.\.venv\Scripts\python.exe scripts\verify_cf_com.py wps
```

动态收集 G/H、R/S 的 16 个异常单元格。两个引擎均满足：

- 每个单元格至少命中 1 条条件格式；
- COM `DisplayFormat.Interior.Color = 13551615`（红底）；
- COM `DisplayFormat.Font.Color = 393372`（深红字）；
- 独立 Office 进程安全审计通过。

## 8. 失败、partial 和恢复

WPS 任务 `20260720031437_1abbe496` 在逐检查点审计中将临时 `wpscloudsvr.exe` 生命周期误判为用户进程变化，任务按保守策略失败：

- 最终文件未生成；
- `.partial.xlsm` 和 SQLite 行结果保留；
- 源文件未变；
- 用户可见 WPS 窗口和 7 个 ET/WPS PID实际未变。

补全审计后，任务先从水位 50 恢复到 70，再从水位 70 补写剩余 4 行并完成。之后又执行一次全新的 8 检查点 WPS 任务通过。该事件验证了“失败不覆盖最终结果、保留 partial、按水位恢复”。

## 9. 视觉 QA

使用电子表格渲染器检查 Excel/WPS 的 M:S 表头/正常行、冲突行 39 和多目的地行 248：

- Q/R/S 可读，距离、状态和说明对齐；
- 冲突与多目的地红底/深红字醒目；
- Excel/WPS 视觉表现一致。

渲染器不支持 `DISPIMG`，会把 O38/O39 显示为 `#NAME?`。这不是输出文件损坏；`DISPIMG` 结论以 5 个原公式、2 个 JPEG 的 OOXML 哈希和真实 Office 重开为准。

预览位于 `samples/expected/prototype/visuals`。

## 10. 源文件与进程终态

- 源文件测试前后大小、修改时间和 SHA-256 完全一致；
- 测试结束无 Excel 进程；
- 原有 ET PID 23680、WPS PID 6284/6980/9028/15444/22876/23688 均仍存在；
- 原有可见 WPS 样表窗口仍存在；
- 未执行任何按名称批量结束 Office 的操作。

## 11. 已知限制

- 距离为确定性 mock，不代表路线或地理距离；
- WPS 结论只适用于本机实测版本和当前隔离条件；
- Excel 会规范化少量原样式，沿用 3A 披露；
- 条件格式使用中文 `SEARCH` 与 `INDEX/ROW`，其他 Office 版本仍需回归；
- 不覆盖数字签名、ActiveX/UserForm、受保护 VBA、XLM；XLM 当前直接拒绝；
- 暂停/停止的 UI 人工交互做了状态机与保存路径自动化覆盖，未做长时间人工压测；
- 未测试真实网络、Key、额度、限流、错误码和真实距离单位。
