# TASK-005A 地址确认测试报告

测试日期：2026-07-20  
结论：**通过**。

## 自动测试

完整命令：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

结果：157 passed、2 skipped、0 failed，共收集 159 项。TASK-004R 原有 148 项全部保留；新增 11 项覆盖可信地址与门址别名。2 项跳过仍是常规 pytest 不启动桌面 Excel/WPS 的既有策略，本任务已另外执行真实 Excel 和 WPS 端到端验收。

| 要求 | 覆盖证据 |
| --- | --- |
| 可信地址库新增、更新和失效 | `test_confirmed_address_crud_and_route_invalidation` |
| 同地址跨行复用 | `test_processor_reuses_confirmed_address_and_route_across_rows` |
| 同地址跨工作簿复用 | `test_same_address_reused_across_rows_and_workbooks` 重开同一 SQLite |
| 修正地址后重新地理编码 | `test_corrected_address_regeocodes_and_confirms` |
| 修正地址后路线缓存失效 | `test_confirmed_address_crud_and_route_invalidation` |
| 人工确认后不再标黄 | `test_city_conflict_manual_confirmation_is_reused_without_warning` |
| 城市冲突确认后复用 | 同上 |
| 地址无效阻止算路 | `test_invalid_address_blocks_route` |
| 系统高可信批量确认 | `test_batch_confirms_high_confidence_candidates` |
| 待确认 Excel 导入导出 | `test_pending_excel_export_import_matches_by_address_id` |
| 导入重复和冲突校验 | `test_import_rejects_duplicate_conflicts` |
| 坐标修正使路线失效 | `test_coordinate_change_invalidates_route` |
| 高德“门址”别名 | `test_amap_door_address_alias_is_high_precision` |
| 原 Excel 地址不修改 | 原有工作簿值/公式摘要测试 + 实机输出审计 |
| 非目标行不修改 | 原有 `test_non_target_rows_are_not_processed` + 两份输出验证 |
| Excel/WPS 保存保护 | 两次真实 COM 端到端、重开及 OOXML 验证 |

## 真实样表分析验收

| 项目 | 结果 |
| --- | --- |
| 目标行 | 74，动态统计 |
| 唯一详细地址文本 | 30 |
| 唯一地址身份 | 31 |
| 系统高可信 | 15 |
| 建议人工复核 | 12 |
| 不允许自动算路 | 4 |
| TASK-004R 旧低精度 | 70 |
| TASK-005A 定位待复核 | 52 行，由重复使用的风险地址产生 |
| 城市冲突 | 3 行、2 个唯一地址身份 |
| 风险过高不计算 | 6 行 |
| 多目的地 | 第 248 行，继续不计算 |

第 39/78 行共享一个地址ID；确认一次即可共同复用。第 272 行因 Excel 城市不同形成独立地址ID，可单独确认。自动测试已证明人工确认后同一冲突身份不再标黄、标红或重新地理编码。

## Excel 实机验收

输出：`samples/expected/address_confirmation/Excel_样表_可信地址库结果_TASK-005A_待验收.xlsm`  
SHA-256：`1EAFBEF4F94C5EE3D93E3C08C2830C8FCF5BC5AEB14F8F8182B00FA5607FB147`  
大小：829239 字节。

- 74 条目标行全部写状态；67 条有距离；62 条警告；67 次路线缓存复用；0 次 HTTP。
- 状态：52 定位待复核、12 缓存复用参考、3 城市冲突、6 风险过高、1 多目的地。
- 真正 `.xlsm`；Office 保存后退出并重开验证通过。
- A:P 值/公式、245 个公式、5 个 DISPIMG、2 个 JPEG、筛选、206 个隐藏行和原条件格式保留。
- 非目标行结果列未写入；原样表 SHA-256 不变。

## WPS 实机验收

输出：`samples/expected/address_confirmation/WPS_样表_可信地址库结果_TASK-005A_待验收.xlsm`  
SHA-256：`389D8BC951A077BCC72458FF489BC992F25BB8765919348930DDA5F68CE9970F`  
大小：832331 字节。

业务计数、距离、状态和说明逐行与 Excel 完全一致；WPS 独立进程保存、退出、重开和工作簿保护检查全部通过，0 次 HTTP。

## 待确认清单验收

输出：`outputs/task005a/待确认地址清单_TASK-005A.xlsx`  
SHA-256：`FFC7203CE649FCD3B28213D9F80120CCDD47778EE78AD5571F62992D02B4A55C`。

- 16 个待复核/拦截唯一地址；不是 74 行订单；
- 地址ID完整保存，确认列有“是/否/地址无效/待进一步核实”数据验证；
- 已检查关键单元格、公式错误和视觉渲染，无截断关键表头或公式错误；
- 导入不依赖行号，重复/冲突处理已有自动测试。

## 最终保护审计

`docs/evidence/TASK005A_FINAL_AUDIT.json` 全部检查通过：

- 源文件 SHA-256 保持 `52011587F8F12A87749087ABEA0ADCE2557874D1B268A55F348E86F8DFA7A951`；
- TASK-004R 两份待验收文件哈希保持不变；
- Excel/WPS 结果逐行一致；
- `confirmed_addresses` 必需字段完整，共 31 条；
- 24 个有效唯一路线缓存均带两端地址ID和地理编码版本；
- 第 248 行仍不计算；
- 两次 Office 样表运行均为 0 HTTP。

