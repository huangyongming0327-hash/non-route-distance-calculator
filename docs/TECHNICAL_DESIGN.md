# 高德货车公路距离批量计算工具 V1.0 技术方案

文档日期：2026-07-20  
适用阶段：阶段 0–3A 技术方案与 Office 保存兼容性验证  
当前结论：阶段 0–2 已有条件通过；当前仅执行阶段 3A，在验证完成前不开发完整 GUI。

## 审核决定：TASK-003A 阶段调整与验收门槛

### 阶段顺序

- 阶段 3A：Excel/WPS 保存兼容性技术验证；
- 阶段 3B：核心业务原型和模拟 API；
- 阶段 4：真实高德 API 联调；
- 后续阶段再完成正式 GUI、打包和全面验收。

阶段 3A 通过前不开发完整 GUI。本阶段仅允许对 Office 保存链路、测试夹具和只读验证工具做最小技术实现，不开发正式业务流程。

### WPS 兼容性声明原则

WPS 兼容不能只依据 COM 对象可创建或样表可只读打开。只有正式保存、生成有效 `.xlsm`、重新打开、公式和图片保留、宏未自动执行、不影响用户现有 WPS 进程且不遗留本程序创建的进程全部实测通过后，才能声明对应能力兼容。未满足的能力必须明确标为“未验证”“实验性”或“当前不支持”，不得声明 Excel 与 WPS 完全兼容。

### 样表结果列与原筛选保护

样表实际业务最后列为 P；Q 虽无值，但有样式并在原 AutoFilter 范围内。阶段 3A 测试副本固定使用：Q“高德货车公路距离（公里）”、R“距离查询状态”、S“距离查询说明”。写入不得改变原 M 列筛选条件、隐藏行状态或筛选结果；本阶段不要求、也不主动把 AutoFilter 范围扩展到 S。

### 高德距离单位正式门槛

在取得真实专业货车 API 权限前，不得仅凭推断将 `paths.distance` 除以 1000 并作为正式公里数。阶段 4 必须使用已知线路、原始返回、包含 `steps` 的对照请求和接口返回结构共同确认距离单位后，才允许启用正式换算。

### TASK-003A 实测结论（2026-07-20）

- **[已实测]** Excel 16.0 Build 20131 完成样表 `.xlsx → .xlsm` 和已有 `.xlsm` 再次 `Save()`；两份结果的 FileFormat 均为 52，所有关键对比无失败。
- **[已实测]** WPS 12.0 Build 26895 在用户已有 WPS 文档打开的场景下，`DispatchEx("KET.Application")` 可创建 Hwnd/PID 可归属的新 ET 进程；完成转换和再次保存后，新进程退出，用户原窗口未变化。
- **[已实测]** 两个引擎保存后均保留 245 个原公式、5 个 `DISPIMG`、2 个 JPEG、`cellimages.xml`、3 条条件格式、原筛选语义、206 个隐藏行、冻结窗格和 COM 已定义名称。
- **[已实测]** 安全宏夹具在 Excel/WPS 中打开时 `Workbook_Open` 均未运行；保存后 VBA 组件和源码、按钮、形状及公式保留。两引擎都会改写 `vbaProject.bin` 的二进制哈希，因此只能承诺本夹具的语义保留，不能据此承诺数字签名不失效。
- **[已实测]** Excel 本机 `Quit()` 后 15 秒内仍可能保留专属进程。正式适配器必须采用独立辅助进程，并且只允许在 Hwnd/PID 归属已确认、`Workbooks.Count=0` 时对该单一 PID 精确回收；禁止按名称批量结束。
- **[已实测]** Excel 保存规范化了 7 个原单元格样式；原值、原公式和任务要求的关键对象未改变，但不得宣称逐单元格样式完全无损。WPS 样表 C/D 未检出该类样式差异。

阶段 3A 的关键技术门已通过，允许进入阶段 3B；Office 保存能力仍须按上述引擎版本、隔离方式和兼容边界实现。

## 0. 验证状态图例

本文使用以下标签，避免把方案或理论兼容写成已完成：

- **[已实测]**：已在当前电脑或当前样表上实际执行并记录结果。
- **[官方文档]**：依据截至 2026-07-20 查阅到的官方文档设计，尚未完成本项目真实联调。
- **[待实机]**：必须在 Excel/WPS 或目标 Windows 电脑上实际测试后才能确认。
- **[待 API 权限]**：必须获得可用的高德 Web 服务 Key 和专业货车接口权限后才能确认。
- **[设计决策]**：本方案拟采用的实现，不代表代码已经完成。

当前环境实测基线：

| 项目 | 结果 | 状态 |
| --- | --- | --- |
| Windows | Windows 11，10.0.26200，64 位 | [已实测] |
| Python | 3.12.10，项目虚拟环境位于 `.venv` | [已实测] |
| Microsoft Excel | Version 16.0，Build 20131，64 位 | [已实测] |
| Excel COM | `Excel.Application` 可创建、查询版本并退出 | [已实测] |
| WPS 表格 | Version 12.0，Build 26895；安装包 12.1.0.26895 | [已实测] |
| WPS COM | `KET.Application` / `KET.Application.9` 已注册，可只读打开样表 | [已实测] |
| Excel `.xlsm` 保存与宏保留 | 未执行 | [待实机] |
| WPS `.xlsm` 保存与宏保留 | 未执行 | [待实机] |
| 高德专业货车真实调用 | 无 Key/权限，未调用 | [待 API 权限] |

## 1. 总体架构

**[设计决策]** 采用分层、端口/适配器式结构，UI 不直接操作 Office、SQLite 或 HTTP。

```text
PySide6 UI
  └─ Application Service / Task Orchestrator
       ├─ Workbook Preview（只读）
       ├─ Validation Pipeline
       ├─ Geocode Service
       ├─ Truck Route Service
       ├─ Cache / Task Journal（SQLite）
       └─ Office Backend Port
            ├─ Microsoft Excel COM Backend
            └─ WPS KET COM Backend
```

核心数据对象：

- `WorkbookSelection`：输入路径、工作表、表头行、字段映射、筛选值；
- `RowInput`：原始六字段和 Excel 行号，仅用于写回定位；
- `NormalizedRowInput`：规范化值、车型映射、输入摘要；
- `GeocodeResult`：原始/清洗地址、结构化地址、省市区、level、坐标、冲突标志；
- `RouteRequest`：起终点坐标、货车等级、策略、接口/算法版本；
- `RowOutcome`：距离、标准状态、中文说明、警告单元格集合；
- `TaskCheckpoint`：任务、输入摘要、已完成结果、保存水位。

业务服务只依赖抽象接口，模拟 API、真实 API、Excel、WPS 均可替换并独立测试。

## 2. 界面技术选择

**[设计决策]** 使用 Python 3.12 + PySide6（Qt 6）。原因：

- 原生 Windows 桌面体验，支持中文、中文路径和空格路径；
- 高 DPI 和 Windows 缩放支持优于基础 Tk 界面；
- `QThread`/信号槽适合把长任务、COM 与 HTTP 从 UI 线程隔离；
- 可实现字段映射表、进度、暂停/继续/停止和多设置页；
- 可由 PyInstaller 打包为无需 Python 的便携目录。

拟定页面：主流程页、字段设置、车型设置、API 设置、Office 设置、缓存/导入导出、进度与完成汇总。用户只选择“列名 + 样例”，不输入列字母。

高 DPI：应用启动前设置 Qt 高 DPI 策略；所有固定尺寸以布局和最小尺寸控制，不使用绝对像素堆叠。UI 线程只渲染，不直接执行 Office 或网络操作。

## 3. Excel COM 方案

**[已实测]** 本机 `Excel.Application` 可创建，版本 16.0 Build 20131；只读打开样表得到 UsedRange `A1:P281`、245 个公式、3 条条件格式、无 VBA。

**[设计决策]** 正式保存使用 `pywin32` 的独立 Excel 自动化实例：

1. 使用 `DispatchEx("Excel.Application")` 创建本工具专属实例，而不是绑定用户当前实例。
2. 通过 `Application.Hwnd` 获取窗口句柄并解析 PID，只管理该 PID。
3. 打开前设置 `AutomationSecurity=3`、`EnableEvents=False`、`DisplayAlerts=False`、`AskToUpdateLinks=False`、`ScreenUpdating=False`。
4. `Workbooks.Open` 显式设置 `UpdateLinks=0`、`ReadOnly=False`（只对工作副本）、`IgnoreReadOnlyRecommended=True`、`AddToMru=False`。
5. 所有修改仅作用于已复制的输出工作副本；原文件只用于预检和复制。
6. `try/finally` 按 Range → Worksheet → Workbook → Workbooks → Application 顺序释放 COM 引用。
7. 关闭后检查本工具记录的 PID；禁止按进程名批量结束 Excel。

Microsoft 官方说明：程序化打开默认可能启用宏，应使用 `AutomationSecurity`；`Workbooks.Open(UpdateLinks=0)` 可禁止外部链接更新。[Workbooks.Open](https://learn.microsoft.com/en-us/office/vba/api/Excel.Workbooks.Open)；`msoAutomationSecurityForceDisable=3` 会禁用程序化打开文件中的宏，但不禁用 Excel 4.0 宏。[AutomationSecurity](https://learn.microsoft.com/en-us/office/vba/api/excel.application.automationsecurity)

## 4. WPS COM / ET 探测结果

**[已实测]**：

- `KET.Application` 已注册，CurVer 为 `KET.Application.9`；
- CLSID 为 `{45540001-5750-5300-4B49-4E47534F4655}`；
- COM 返回 Version 12.0、Build 26895；
- 安装路径为 `C:\Users\黄泳铭\AppData\Local\Kingsoft\WPS Office\12.1.0.26895\office6`；
- `AutomationSecurity=3` 属性赋值未报错；
- 可只读打开样表，识别 1 个工作表、245 个公式和筛选状态；
- WPS UsedRange 返回 `A1:Q281`，与 Excel 的 `A1:P281` 不一致。

WPS 官方资料确认 `ket.application` 是 WPS 表格应用标识符，但未找到足以证明当前桌面版 COM 的 `.xlsm` 保存、宏安全和实例隔离完全等同 Excel 的官方合同。[WPS CreateObject](https://open.wps.cn/documents/app-integration-dev/wps365/client/wpsoffice/jsapi/macro-editor-api/function/createobject)

**[待实机]** 当前 WPS 测试时系统已有 WPS/ET 进程，不能证明 `KET.Application` 一定创建隔离新进程，也不能证明 `Quit()` 不影响用户实例。阶段 6 必须在“WPS 全关闭”和“用户已有 WPS 打开”两种场景分别记录进程基线、PID 和窗口行为。在实例隔离未通过前，WPS 正式保存功能保持禁用或标为实验性。

## 5. `.xlsx` 转 `.xlsm` 方案

**[官方文档]** Excel `xlOpenXMLWorkbook=51` 对应 `.xlsx`，`xlOpenXMLWorkbookMacroEnabled=52` 对应 `.xlsm`。[XlFileFormat](https://learn.microsoft.com/en-us/office/vba/api/excel.xlfileformat)；`Workbook.SaveAs` 支持显式 FileFormat。[Workbook.SaveAs](https://learn.microsoft.com/en-us/office/vba/api/Excel.Workbook.SaveAs)

**[设计决策]**：

1. 在用户选定输出目录创建唯一的 `.partial.xlsx` 工作副本，绝不覆盖输入。
2. 用 Excel COM 打开副本，完成目标单元格更新。
3. 调用 `SaveAs(partial_xlsm, FileFormat=52)`，生成真实 OOXML 宏启用工作簿。
4. 关闭后检查 ContentType、扩展名、ZIP 完整性和 FileFormat=52。
5. 以宏禁用、只读方式重新打开验证，再将 `.partial.xlsm` 原子重命名为最终文件名。

禁止直接改扩展名。样表包含 `DISPIMG` 单元格图片，`.xlsx`→`.xlsm` 后是否保留必须在阶段 5 实测，未通过就阻止交付结果。

## 6. `.xlsm` 宏保留方案

**[设计决策]** 对 `.xlsm` 输入先做二进制复制，输出副本仍为 `.xlsm`；在副本上用 Office 引擎仅修改目标单元格，然后 `Save()`，避免跨格式转换。

验证清单：

- 保存前后 `vbaProject.bin` 存在；
- `HasVBProject=True` 保持；
- VBA 二进制大小/哈希变化需解释，异常即失败；
- 工作表、形状、ActiveX、按钮、图表、图片和定义名称清单未异常减少；
- 专用宏夹具中的模块、UserForm、按钮仍可在用户手动启用宏后使用；
- 自动宏在工具打开过程中没有运行。

**[待实机]** Excel/WPS 对数字签名 VBA、ActiveX 和 WPS 特定宏对象的保留仍未知。若保存导致数字签名失效，必须明确提示并在兼容报告记录，不能称为无损保留。

## 7. 自动宏禁用方案

**[设计决策]** 打开任何 Office 工作簿前先做 OOXML 预检：

- 检查 VBA、ActiveX、外部链接、DDE、Excel 4.0 宏表、嵌入对象；
- 对 Excel 4.0 宏表直接停止自动化处理，因为 Microsoft 明确说明 `AutomationSecurity=3` 不禁用 XLM 宏；
- VBA 工作簿允许继续，但必须设置 `AutomationSecurity=3` 和 `EnableEvents=False`；
- `UpdateLinks=0`，不调用 `RefreshAll`、`CalculateFull`、`Run` 或 `RunAutoMacros`；
- 不接受任何宏安全弹窗的自动确认。

打开和保存后恢复应用级设置，仅恢复本工具专属实例。WPS 的 `AutomationSecurity` 实际语义须用“Workbook_Open 写入临时标记”的无害夹具验证，未通过前不开放正式 WPS 保存。

## 8. 地址清洗设计

**[设计决策]** 保留原始地址，所有清洗都生成新字段，永不写回原地址。

处理顺序：

1. Unicode NFKC 只用于全/半角数字、字母和常见符号规范化；原文仍保留。
2. 去除首尾普通空格、全角空格、不间断空格、零宽字符和 BOM。
3. 换行、回车、制表符转为可审计分隔符；合并连续空白。
4. **先做多目的地检测，再移除分隔符**，防止把两个地点合并为一个地址。
5. 手机号仅匹配明确的 `1[3-9]` 开头 11 位；座机仅匹配有区号结构的号码。门牌号、库号、楼号不删除。
6. 联系人只在有“联系人/收货人/电话”等标签且模式明确时移除；默认保留企业、园区和仓库名称。
7. 删除重复、无定位意义的装饰符号；保留省市区县、道路、门牌、园区、仓库、厂区、楼栋、门岗和 POI。

输出审计字段：`raw_address`、`cleaned_address`、`redacted_log_address`、`cleaner_version`。普通日志只记录脱敏摘要和哈希；技术诊断需用户显式开启才记录有限上下文。

## 9. 多目的地检测

**[设计决策]** 采用高精度、低召回的保守规则，在调用地理编码前执行：

- 城市列明确包含两个已知行政城市；或
- 地址被换行、分号、斜杠、顿号等分隔为两个片段，且每个片段都包含独立的省/市/区 + 道路/园区/门牌结构；或
- 地址内出现两个互不从属的完整省市地址。

只出现“苏州市常熟市”这类行政层级、道路交叉口中的斜杠、园区/企业并列，不判为多目的地。不确定时进入人工确认，不猜测顺序。

**[已实测]** 样表第 248 行满足高置信规则；第 39、78 行是单一详细地址与城市列冲突，不应误报多目的地。

## 10. 城市冲突检测

**[设计决策]** 详细地址优先，避免 city 参数把明显的异地详细地址强行定位到城市中心：

1. 若详细地址本身含明确省/市，先全国地理编码，不传 city 限制。
2. 若详细地址无行政信息且首次结果失败/过低，才用城市列作辅助提示重试。
3. 比较返回 province/city/district/adcode 与城市列，处理直辖市、县级市和上下级行政关系。
4. 有冲突但详细地址定位成功时仍按详细地址坐标计算，状态为“查询成功—地址冲突待确认”。
5. 冲突来源（发货/目的）记录到 RowOutcome，用于只标记对应城市与详细地址单元格。

**[已实测]** 样表文本候选为第 39、78、272 行；**[待 API 权限]** 尚未通过高德结构化返回确认。

## 11. 地址精度判断

高德地理编码官方响应包含 province、city、district、street、number、adcode、location、level，并给出 level 列表。[地理/逆地理编码](https://developer.amap.com/api/webservice/guide/api/georegeo)

**[设计决策]**：

| 高德 level / 证据 | 处理 |
| --- | --- |
| 门牌号、门址、单元号、道路、道路交叉路口、明确兴趣点/住宅区/园区 | 计算，正常成功 |
| 乡镇、村庄、区县、开发区、热点商圈，或仅有街道级证据 | 计算，黄色“定位精度较低” |
| 市 | 不算路，“详细地址定位失败” |
| 省、国家、未知、无结果 | 不算路，“地址解析失败” |

坐标必须是两个有限数字、非零，经度纬度顺序正确，粗边界位于中国合理范围，并与返回省市区一致。坐标异常直接拒绝，不调用货车路径接口。

## 12. 高德地址解析调用流程

**[官方文档]** 地理编码接口为 `GET https://restapi.amap.com/v3/geocode/geo`，必填 `key`、`address`，`city` 可选；文档最后更新 2026-02-02。[官方文档](https://developer.amap.com/api/webservice/guide/api/georegeo)

**[设计决策]**：

1. 计算地址缓存键：清洗地址 + city hint + `geocode_v3` + 清洗算法版本 + 正式/模拟模式。
2. 命中有效缓存则复用。
3. 未命中时按第 10 节的“详细地址优先”规则请求。
4. 校验 `status/count/info/infocode` 和 geocodes 列表。
5. 记录 formatted_address、province、city、district、street、number、adcode、level、location。
6. 必要时做一次带 city hint 的备选请求，但不能用低精度城市中心替代失败的详细地址。
7. 缓存结构化结果和原始响应摘要；Key 永不进入日志或缓存。

“仅校验”模式默认提供“深度地址校验”选项：启用时会调用地理编码但不调用货车路线，界面明确显示预计消耗地址解析额度；关闭时只做本地规则检查，不能声称已完成精度与城市冲突验证。

## 13. 高德专业货车接口调用流程

**[官方文档]** 截至 2026-07-20，高德“货车路径规划基础版”文档最后更新 2026-06-08：

- URL：`GET https://restapi.amap.com/v4/direction/truck`；
- `origin`、`destination` 和 `size` 必填；坐标最多 6 位小数；
- `size`：1 微型、2 轻型、3 中型、4 重型；
- `strategy=13`：不考虑路况、距离优先；
- `nosteps=1` 可不返回步骤；`showpolyline=0` 不返回轨迹；
- 专业货车接口是收费物流服务，试用/正式应用需商务工单；
- 不传车牌时不考虑政策限行；不传实际宽高重时物理限制能力受限，但货车路线仍考虑路牌限制。

来源：[高德货车路径规划基础版](https://developer.amap.com/api/logistic-service/guide/wagon_path/truck-route-plan-basis)

**[设计决策]** 正式最小请求参数：

```text
key=<secret>
origin=<lon,lat>
destination=<lon,lat>
size=<2|3|4>
strategy=13
nosteps=1
showpolyline=0
intelligent_sorting=0
cartype=0
```

第一版按任务要求不收集实际宽、高、总重、核定载重、轴数和车牌，因此不发送这些可选字段。界面和说明必须明确“简化车辆参数”限制；不能声称已覆盖所有物理/政策限行。

响应同时兼容货车接口的 `errcode/errmsg/errdetail` 和平台级 `status/info/infocode` 错误形态。解析全部有效 paths，并按距离优先策略核验返回路径；将原始距离保留为整数，再转换为公里并用 Decimal 四舍五入到 1 位。

**[待 API 权限]** 基础货车文档对 `paths.distance` 顶层字段没有明确标注单位，虽然高德其他路线文档通常标为米，本项目不得仅凭推断上线。阶段 4 必须用真实响应、已知路线和一次含 steps 的对照请求确认单位后，才能启用“除以 1000”的正式逻辑。

## 14. API 未开通时的模拟模式

**[设计决策]** 模拟客户端与真实客户端实现同一接口，但使用独立命名空间：

- 基于固定夹具和输入哈希生成可复现结果；
- 支持成功、低精度、冲突、权限错误、超时、空地址等场景；
- UI 顶部持续显示红色横幅“模拟数据，不可用于正式业务”；
- 输出文件名包含“模拟结果”；
- 每条说明以 `【模拟数据，不可用于正式业务】` 开头；
- 缓存键包含 `mode=mock`，与正式缓存物理/逻辑隔离；
- 模拟模式不伪造“真实高德联调完成”。

## 15. 车型映射

**[设计决策]** 映射配置保存别名、业务等级、高德 size、配置版本和条目指纹。

安全规范化：

- 数字 `4.20` → `4.2`，数字 `13.0` → `13`；
- 文本忽略前后空白和 `M/m` 大小写；
- 仅接受精确配置别名，如 `4.2`、`4.2米`、`4.2m`；
- 不去掉任意单位，因此 `4.2吨` 不会误匹配 `4.2米`；
- 未配置值不回退轻型，写“车型未识别”。

默认业务映射：4.2 → size 2；6.8/7.6 → size 3；9.6/13 → size 4。用户可新增 5.2、17.5 或内部名称。修改后递增映射版本，使相关任务状态和路线缓存重新判断。

**技术风险**：高德官方 size 同时参考车长和总质量，任务中的 Excel 仅给车长式车型。默认映射是业务简化，不等同于完整国标判定；须由业务负责人审核接受。

## 16. SQLite 缓存结构

**[设计决策]** 单库多表，启用 WAL、外键和事务；数据库位于项目/便携目录 `cache\truck_distance.sqlite3`。

主要表：

```text
schema_meta(schema_version, app_version, created_at, migrated_at)
geocode_cache(cache_key, cleaned_address, city_hint, api_contract,
              cleaner_version, mode, formatted_address, province, city,
              district, adcode, level, longitude, latitude, status,
              queried_at, response_digest)
route_cache(cache_key, origin_lon, origin_lat, destination_lon, destination_lat,
            origin_address_digest, destination_address_digest, truck_size,
            strategy, mapping_version, api_contract, algorithm_version, mode,
            distance_raw, distance_km, queried_at, status, response_digest)
tasks(task_id, source_fingerprint, output_path, sheet_signature, mode,
      status, created_at, updated_at, last_saved_sequence)
row_results(task_id, row_identity, input_hash, sequence, outcome_json,
            persisted_to_workbook, updated_at)
```

路线键包含 API 接收的 6 位坐标、标准地址摘要、size、strategy、映射版本、接口合同版本、算法版本和正式/模拟模式。缓存不以 Excel 行号作为业务键；行号只作为当前输出写回位置。

缓存导入：先校验 manifest、数据库/schema/API 版本和每条记录；在事务中按 key 去重，较新的有效记录优先；统计成功、跳过、冲突、损坏。API Key 永不导出。

## 17. 三种运行模式

### 模式一：计算未完成及已变更行

默认。对每个目标行计算六字段、映射版本和路线配置的 `input_hash`。本地状态能验证且已有成功结果时跳过；距离空、旧状态失败/待确认、输入变化、配置变化或缺少可验证摘要时重新处理。无法验证的旧结果宁可重算，不盲目信任。

### 模式二：重新计算全部非线路报价

扫描全部精确匹配行，忽略工作簿旧结果，但允许复用当前有效地理编码/路线缓存。界面显示任务指定提示。

### 模式三：仅校验地址和异常

不调用货车路径接口。可选择深度地理编码校验（消耗地址解析额度）或纯本地校验。距离不写；正常行可使用新增状态“地址校验通过”，异常使用任务规定状态。其他报价类型行仍完全不写。

## 18. 暂停、继续、停止

**[设计决策]** 使用线程安全状态机：`RUNNING → PAUSING → PAUSED → RUNNING`，以及 `STOPPING → STOPPED`。

- 暂停：不发起下一次请求，等待当前网络/COM 原子操作完成，立即提交 SQLite 并保存工作副本。
- 继续：从下一条未完成记录开始。
- 停止：不发新请求，等待当前安全点，提交/保存/关闭 Office；不批量把未处理行写成“用户停止”。
- 单行失败：记录后继续下一行。
- UI 关闭：等同“停止并安全保存”，若用户强制终止则由下次任务日志恢复。

网络超时建议：连接 5 秒、读取 30 秒、总请求上限 40 秒；最多 3 次递增退避并加抖动。网络异常、HTTP 429/5xx、服务繁忙可重试；Key 无效、权限不足、日额度/余额耗尽不重复重试。

## 19. 中间保存和断点续算

**[设计决策]** 每行结果先写 SQLite 事务；每 10 行或 60 秒（先到者）批量写 Office 并保存工作副本。暂停、停止、API 权限错误和任务完成时强制保存。

崩溃恢复：

1. 读取未完成 task 和 output partial 文件；
2. 校验输入/工作表签名与目标结果列；
3. 将 SQLite 中 `persisted_to_workbook=false` 的结果重放到副本；
4. 从下一条未完成输入继续；
5. 若副本损坏，从原文件重新复制并重放已完成结果。

输出目录不可写或文件被占用时，在任何 API 调用前失败。保存失败时停止新请求，保留 SQLite 和 partial 文件，不覆盖已有最终文件。

## 20. 红黄警告格式

**[设计决策]** 使用条件格式叠加，不直接替换用户单元格基础格式。

- 建立隐藏工作簿名称 `_AMAP_TRUCK_WARNING_MARKER`；
- 本工具规则的公式都引用该名称，便于只识别/删除本工具规则；
- 每条异常按 RowOutcome 中的精确单元格集合创建规则；
- 红色用于冲突、多目的地、地址失败、车型未识别；黄色用于低精度；
- 距离单元格默认不着色；
- 重新计算后状态改变，规则条件立即为假；更新该行时删除旧的本工具规则并按新结果重建；
- 不调用 `FormatConditions.Delete` 清空整表，不恢复/覆盖用户原有格式。

WPS 对公式型条件格式、规则优先级和隐藏名称的兼容必须实测。若无法稳定识别本工具规则，WPS 模式不得启用可破坏用户格式的直接填色回退。

## 21. Office 进程释放

**[设计决策]** Office 操作集中在单一 STA 工作线程，线程内 `pythoncom.CoInitialize()` / `CoUninitialize()`。

Excel：专属实例 + 记录 PID；正常 `Close(False)`、`Quit()`、释放 COM。若专属 PID 超时残留，只有在确认 PID 是本任务创建且不含用户工作簿时才可结束该 PID，绝不按名称结束全部 Excel。

WPS：先证明能创建独立实例并取得 PID。若 COM 连接到预有进程，则不允许自动结束该进程；正式保存功能应阻止并提示用户关闭 WPS 或改用 Excel。

进程测试必须覆盖正常完成、单行异常、保存异常、用户停止、程序崩溃，以及用户已有 Excel/WPS 窗口场景。

## 22. 安全和 API Key 存储

**[设计决策]** 优先级：

1. Windows Credential Manager 原生 Generic Credential；
2. 若凭据管理器不可用，使用 Windows DPAPI 当前用户范围加密后保存二进制密文；
3. 两者都不可用则拒绝持久化，只允许本次内存使用。

DPAPI `CryptProtectData` 通常只允许同一登录凭据、同一电脑解密，符合 API Key 不随普通配置迁移的要求。[CryptProtectData](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata)

日志脱敏：只显示 Key 前 3/后 2 位或固定哈希摘要；HTTP 日志在记录前移除 `key` 和签名参数；异常对象禁止直接打印完整请求 URL。配置导出不含 Key，删除操作同时清理凭据和内存副本。

## 23. EXE 打包

**[设计决策]** PyInstaller `onedir` + `windowed`，不优先 onefile。原因：onefile 每次会解压到临时目录，而本项目要求尽量不向 C 盘写大体积临时数据；onedir 更可控、启动更快，也便于便携目录放置 config/cache/logs/temp。PyInstaller 官方说明 onedir 会把依赖与可执行文件放在一个目录，onefile 会在运行时解包。[PyInstaller operating mode](https://www.pyinstaller.org/en/stable/operating-mode.html)

构建固定：

- `TEMP`、`TMP`、`PYINSTALLER_CONFIG_DIR` 指向项目 `temp`；
- `--workpath build`，`--distpath release`，spec 位于 `build` 或 `scripts`；
- 最终目录 `release\高德货车距离计算工具`；
- 生成版本资源、USER_GUIDE、VERSION、KNOWN_ISSUES 和 ZIP；
- 不请求管理员权限；
- 在干净 Windows 10/11 虚拟机测试无 Python 启动、中文/空格路径和 Office 探测。

## 24. 多电脑迁移

**[设计决策]**：

- 车型配置与字段配置导出为带 `schema_version`、时间、checksum 的 UTF-8 JSON；
- 缓存导出为 ZIP：manifest + 版本化 SQLite/JSONL 数据，不包含 Key；
- 导入先在临时数据库验证，完成后事务合并；
- 新记录不覆盖本机更新时间更晚的有效记录；
- 模拟/正式缓存不能互相导入；
- 迁移后 API Key 必须在新电脑重新输入并本机加密。

## 25. 自动测试

**[设计决策]** 使用 pytest，分层测试：

- 单元：空白规范化、精确报价匹配、车型安全规范化、电话清洗、多目的地、城市层级、精度分级、坐标校验、状态映射、缓存键；
- 属性/参数化：数字 4.2/4.20/13.0、文本单位、`4.2吨` 误匹配防护；
- 集成：SQLite WAL、缓存导入去重、任务恢复、模拟 HTTP、网络重试；
- 工作簿：在测试副本验证新增/复用结果列、其他报价类型值和格式前后完全一致；
- Office：专用 fixture 验证 xlsx/xlsm、宏、图片、图表、ActiveX、筛选、条件格式、数据验证、外链、中文路径、占用文件和进程释放。

样表验收将固定保存源文件哈希、74 行目标计数、0 地址空值、29 个起终点、36 个原始车型组合、34 个映射等级组合和第 248 行多目的地等断言。

## 26. Excel 和 WPS 实机测试计划

### Microsoft Excel

1. 建立包含 Workbook_Open/Auto_Open 无害标记、VBA 模块、UserForm、按钮、ActiveX、图表、图片、透视表、外链和数据验证的 `.xlsm` 夹具。
2. 在宏强制禁用下打开副本，确认标记未产生、外链未更新。
3. 测试 `.xlsx`→FileFormat 52 和 `.xlsm` 原格式保存。
4. 保存前后做 OOXML 对象清单、VBA、公式、样式和人工视觉对比。
5. 重新打开验证，无残留专属 Excel PID，不影响用户已有 Excel。

### WPS

1. WPS 全关闭时记录进程基线，创建 KET 实例并取得 PID；
2. 用户已有 WPS 文档时重复，验证是否隔离；
3. 测试 `AutomationSecurity` 是否确实阻止打开宏；
4. 分别测试 xlsx 输入、xlsm 输入、FileFormat 52/等价格式保存；
5. 检查 VBA、`DISPIMG`、图片、公式、格式、筛选和进程；
6. 不通过的能力在 UI 禁用并形成兼容报告，不使用理论回退。

## 27. 技术风险

| 优先级 | 风险 | 控制措施 |
| --- | --- | --- |
| 高 | 没有专业货车权限，无法真实联调 | 模拟模式隔离；取得权限后才宣称完成 |
| 高 | 只有车型长度式字段，缺少总质量/尺寸/车牌 | 明示简化参数；业务审核映射；不宣称完整限行 |
| 高 | WPS COM 可能复用用户进程 | 实例/PID实测；未通过则禁用正式保存 |
| 高 | `.xlsx`→`.xlsm` 可能影响 `DISPIMG` 单元格图片 | 样表转换前后专项检查；失败即停止 |
| 高 | 自动宏安全对 XLM 不完整 | OOXML 预检并拒绝 XLM 宏表 |
| 中 | Excel/WPS UsedRange 不一致 | 自研实际值边界算法，不以 UsedRange 定列 |
| 中 | 既有条件格式与工具警告规则冲突 | 唯一标记规则；不清空用户规则；实机验证 |
| 中 | 本地状态丢失或文件移动导致摘要不可验证 | 保守重算；缓存仍按业务键复用 |
| 中 | Office 保存中断导致 partial 损坏 | SQLite 先记账、批量保存、重放恢复、最终原子命名 |
| 低 | onedir 文件较多 | 便携目录整体压缩交付，版本清单校验 |

## 28. 暂时无法确认的问题

1. 高德 Key 是否已开通专业货车 API、可用额度、QPS 和商务授权范围。[待 API 权限]
2. `v4/direction/truck` 当前真实响应的错误码形态及 `paths.distance` 单位。[待 API 权限]
3. 不传宽高重时，当前服务端是否严格按文档“不考虑物理限制”，以及表格中默认值如何实际生效。[待 API 权限]
4. 任务默认车型映射在公司车辆真实总质量下是否正确。[需业务确认]
5. WPS 12.1.0.26895 是否能创建隔离 KET 进程并安全保存 `.xlsm`。[待实机]
6. WPS 是否真正阻止 Workbook_Open/Auto_Open，以及是否保留 VBA/按钮/ActiveX。[待实机]
7. 样表 5 个 `DISPIMG` 在 Excel/WPS `.xlsm` 保存后的显示与资源保留。[待实机]
8. 扩展现有 AutoFilter 到新结果列时能否跨 Excel/WPS 完整保留筛选条件与隐藏行；未验证前保持原筛选不变。[待实机]
9. 数字签名 VBA 在只改单元格并保存后的签名状态。[待实机]
10. 条件格式唯一标记方案在 WPS 中的规则识别和优先级。[待实机]

## 29. 结果列与原行保护的实现细节

**[设计决策]** 实际最后列算法：扫描表头有效值和数据区实际值/公式，忽略仅有样式的空单元格、历史筛选边界和极远条件格式。先在表头行全范围规范化搜索三个同名结果列；存在则原位更新，不存在则从实际最后列后连续追加，不插列。

样表：实际有值最后列 P；Q 虽有样式且被筛选范围覆盖但无值，因此新列拟为 Q、R、S。

处理循环先精确判断报价类型。非目标行不进入地址、车型、缓存或写入分支；新建列的这些行自然保持空白。若已有同名结果列且非目标行已有用户值，本工具也不清除或修改。

## 30. 输出文件保护与验证

**[设计决策]** 输出名为 `原文件名_货车距离计算结果_yyyyMMdd_HHmmss.xlsm`，冲突时加序号。原文件和最终文件路径做规范化、文件 ID/哈希检查，任何相同目标都拒绝。

最终验证至少包括：

- 文件存在、非零、ZIP/OOXML 可读、FileFormat=52；
- 原文件哈希、大小和修改时间未变化；
- 工作表数量、名称、顺序、可见性一致；
- 目标表和三个结果列存在；
- 非目标表无变更；
- 非目标报价行的原单元格值、公式和基础格式摘要一致；
- 公式、图片、图表、VBA、外链、条件格式、数据验证对象未异常减少；
- 以同一引擎宏禁用只读重开成功；
- 工具专属 Office 进程退出。

任何关键验证失败时保留 partial 和技术日志，不把文件重命名为最终结果。

## 31. 结论与审核门

阶段 0–2 已完成环境、样表事实与技术路线确认。当前没有可运行的业务程序、真实高德联调、正式 Office 保存、宏保留验收或 EXE。下一步必须先由总指挥审核以下重点：

1. 接受“简化车型参数”带来的限行能力边界；
2. 同意 Excel 为首选正式保存引擎，WPS 在完成实测前不宣称兼容；
3. 同意 strategy=13、size=2/3/4 的官方参数基线，并在阶段 4 开发前再次核对文档；
4. 同意本地 SQLite 状态、条件格式唯一标记和 onedir 便携打包方案；
5. 提供或安排专业货车 API Key/权限联调。

审核通过并明确通知“继续阶段 3”后，才开始核心原型。
