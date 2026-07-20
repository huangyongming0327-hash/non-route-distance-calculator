# 非线路运距计算工具 V1.0

Windows 本地桌面工具，使用高德地理编码和路径规划 2.0 普通驾车接口，为 Excel/WPS 中精确等于“非线路报价”的行生成参考公路距离，并通过本地可信地址库实现“唯一地址一次确认、以后自动复用”。

> 普通驾车参考距离，不代表货车实际可通行路线。本工具不考虑货车限高、限宽、限重、禁行及车牌限制。

当前状态：**TASK-005A 已完成并暂停等待总指挥验收；尚未正式发布 V1.0。**

## 快速启动

环境：Windows 11、Python 3.12，以及 Microsoft Excel 或已验证的 WPS 表格。

```powershell
cd "D:\AI project\非线路运距计算"
.\.venv\Scripts\python.exe -m src.main
```

也可双击 `scripts/run_prototype.bat`。

## 正式口径

- 地理编码：`GET https://restapi.amap.com/v3/geocode/geo`
- 路径规划：`GET https://restapi.amap.com/v5/direction/driving`
- 参数：`strategy=32`、`cartype=0`、`ferry=1`、`alternative_route=1`、`output=json`
- 距离：读取第一条 `route.paths` 的 `distance` 米数，Decimal `ROUND_HALF_UP` 换算为一位小数公里
- 正式缓存：`cache/driving_real.sqlite`
- 可信地址：`confirmed_addresses`，地址/坐标确认后跨行、跨角色、跨工作簿复用
- 车型：可选只读，不参与请求、缓存键、距离或状态

## 使用流程

1. 在“API 设置”中安全保存高德 Web 服务 Key；不要把 Key 写入聊天、配置、Excel 或文档。
2. 选择工作簿并确认工作表、表头和字段映射。
3. 在“地址确认”区刷新唯一地址清单。先处理“待进一步核实”和真正有风险的“未确认”地址，不需要逐行确认订单。
4. 可使用原始地址、高德标准地址或只用于查询的修正地址重新解析；原 Excel 城市和详细地址不会修改。
5. 点击“确认定位正确”后，同地址以后直接复用；也可导出 Excel 待确认清单，线下填写后按地址ID导回。
6. 选择 Excel/WPS 和普通驾车正式计算，确认风险后开始。程序只写工作副本和新结果文件，不覆盖输入。

完整步骤见 `docs/USER_GUIDE_DRAFT.md`。

## 地址精度状态

- 系统高可信：门牌号/门址、名称匹配兴趣点、名称匹配道路或明确园区，不标黄。
- 查询成功—定位待复核：允许生成参考距离，但乡镇/村庄、名称不足或其他证据值得人工复核，标黄。
- 查询成功—地址冲突待确认：按详细地址坐标计算，必须人工确认；确认后可信库复用，不再重复标红。
- 地址风险过高—未计算：仅到区县、行政区错位、坐标异常或无法解析，距离留空并标红。
- 地址无效 / 多目的地待确认：阻止自动算路。

详细规则和真实样表证据见 `docs/ADDRESS_PRECISION_ANALYSIS.md`。

## 样表 TASK-005A 结果

- 目标行 74；唯一详细地址文本 30；城市限定地址ID 31。
- 系统高可信 15；建议人工复核 12；不允许自动算路 4。
- Excel/WPS 均为：67 条距离、52 定位待复核、12 缓存复用参考、3 城市冲突、6 风险过高、1 多目的地。
- 业务结果逐行一致；两次 Office 运行均为 0 HTTP。
- 原样表和 TASK-004R 两份结果文件哈希保持不变。
- 自动化回归：157 passed、2 skipped、0 failed；Excel/WPS 实机保存保护另行通过。

## 验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\analyze_address_precision.py
.\.venv\Scripts\python.exe scripts\run_task005a_acceptance.py excel
.\.venv\Scripts\python.exe scripts\run_task005a_acceptance.py wps
.\.venv\Scripts\python.exe scripts\final_task005a_audit.py
```

Excel/WPS 阶段会启动本工具专属隐藏 Office 进程并执行安全保存和重开验证。不要手工结束这些进程。

## 安全边界

- Key 优先保存到 Windows Credential Manager，回退到当前用户 DPAPI；所有 HTTP 审计删除 Key/sig 并脱敏电话号码。
- 输入文件先指纹校验再复制；禁止覆盖输入或写入 `samples/input`。
- 原 Excel 地址只读；修正查询地址只保存到本地 SQLite。
- 禁止宏、事件、更新链接和刷新；拒绝 XLM 宏表。
- 不调用 `/v4/direction/truck`，不在普通驾车失败时伪造距离，也不把 mock 写入正式缓存。
- 不删除或修改原车型列；旧货车距离列属于不同口径，原样保留。

## 当前交付

- `CURRENT_STATUS.md`
- `docs/ADDRESS_PRECISION_ANALYSIS.md`
- `docs/CONFIRMED_ADDRESS_DESIGN.md`
- `docs/ADDRESS_CONFIRMATION_TEST_REPORT.md`
- `docs/TASK-005A_RESULT.md`
- `samples/expected/address_confirmation/Excel_样表_可信地址库结果_TASK-005A_待验收.xlsm`
- `samples/expected/address_confirmation/WPS_样表_可信地址库结果_TASK-005A_待验收.xlsm`
- `outputs/task005a/待确认地址清单_TASK-005A.xlsx`

专业货车方案因最低采购成本过高已终止；历史文档保留并标记，不代表当前实现。

