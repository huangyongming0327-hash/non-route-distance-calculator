# TASK-003A Office 保存兼容性技术验证报告

测试日期：2026-07-20  
项目根目录：`D:\AI project\非线路运距计算`  
结论：**阶段 3A 关键技术门通过，允许进入阶段 3B；Excel/WPS 支持均带明确边界。**

## 1. 结论总表

| 验证项 | Excel | WPS | 结论 |
| --- | --- | --- | --- |
| 样表 `.xlsx → .xlsm` | 已通过 | 已通过 | 两份结果均为有效 OOXML，FileFormat=52 |
| 已有 `.xlsm` 再次保存 | 已通过 | 已通过 | 均使用 `Workbook.Save()`，只修改 Q3 的模拟值 |
| 宏禁用只读重开 | 已通过 | 已通过 | `Workbook_Open` 标记保持 `NOT_RUN` |
| VBA/按钮/形状/公式保留 | 已通过 | 已通过 | VBA 组件和源码逐行一致；`vbaProject.bin` 哈希会变化 |
| 245 个原公式 | 已通过 | 已通过 | 240 个 IF、5 个 DISPIMG 均保留 |
| 2 个 JPEG / cellimages 部件 | 已通过 | 已通过 | 文件名、大小、SHA-256 均与源一致 |
| DISPIMG 视觉显示 | 已通过 | 已通过 | 5 个位置均显示真实缩略图，无错误占位 |
| 3 条条件格式 | 已通过 | 已通过 | 数量、范围、公式、优先级和显示格式语义均保留 |
| 原筛选与 206 个隐藏行 | 已通过 | 已通过 | WPS 将内部 Filters 等价改写为 CustomFilters equal |
| 冻结窗格、工作表、定义名称 | 已通过 | 已通过 | 无关键变化 |
| 用户现有 Office 进程不受影响 | 已通过（条件式） | 已通过 | Excel 需专属辅助进程和精确 PID 兜底；WPS 可正常 Quit |
| 原样表保护 | 已通过 | 已通过 | 哈希、大小、修改时间前后完全一致 |

四份结果文件的 comparison JSON 均为 `compatible_pass=true`，关键失败数均为 0。

## 2. 测试环境

| 项目 | 实测值 |
| --- | --- |
| Windows | Windows 11，10.0.26200，64 位 |
| Python | 3.12.10，64 位，项目 `.venv` |
| Microsoft Excel | Version 16.0，Build 20131，64 位 |
| WPS 表格 | Version 12.0，Build 26895；安装包 12.1.0.26895 |
| Excel 自动化 | `DispatchEx("Excel.Application")` |
| WPS 自动化 | `DispatchEx("KET.Application")` |
| 核心验证库 | openpyxl 3.1.5、pywin32 312、psutil 7.2.2、oletools 0.60.2、Pillow 12.3.0 |

所有 Office 会话均在打开文件前设置 `AutomationSecurity=3`、`EnableEvents=False`、`DisplayAlerts=False`、`AskToUpdateLinks=False`、`ScreenUpdating=False`；打开时使用 `UpdateLinks=0` 和 `AddToMru=False`。

## 3. 源文件与基线

源文件：`samples\input\副本26年6月干线账单 2.1-对账2.0-物流商(2).xlsx`

| 属性 | 测试前 | 测试后 |
| --- | --- | --- |
| 大小 | 828,799 字节 | 828,799 字节 |
| 修改时间 | 2026-07-19 23:55:12.446944 +08:00 | 相同 |
| SHA-256 | `52011587F8F12A87749087ABEA0ADCE2557874D1B268A55F348E86F8DFA7A951` | 相同 |

结构化基线位于 `samples\expected\office_spike\source_baseline.json`，组合了 OOXML ZIP、openpyxl 只读检查、Excel COM 和隔离 WPS COM 观察。基线包括全部 3,891 个非空单元格摘要、工作表结构、公式、媒体哈希、条件格式、筛选、隐藏行、定义名称和关键 OOXML 部件。

关键基线：1 张可见工作表；实际有值区 `A1:P281`；Excel UsedRange `A1:P281`；WPS UsedRange `A1:Q281`；245 个公式；5 个 DISPIMG 位于 O38/O39/O58/O78/O118；2 个 JPEG；3 条条件格式；AutoFilter `A1:Q281` 且 M 列等于“非线路报价”；206 个隐藏行；冻结窗格 A2。

## 4. 测试写入

每份工作副本写入 Q/R/S 表头，只处理 M 列精确等于“非线路报价”的 74 行。普通目标行写入静态模拟距离 `round(100 + 行号/10, 1)`、状态“模拟测试”和明显的非业务说明。第 248 行 Q 为空、R 为“多目的地待确认”、S 明确说明检测到多个目的地。其他报价类型的 Q/R/S 均为空。

## 5. Excel 测试结果

### 测试 A：`.xlsx → .xlsm`

生成 `samples\expected\office_spike\Excel_样表转换结果.xlsm`，大小 827,598 字节，SHA-256 `2C64EFD5E29D6DB82BC0D5F240BFA2010ABFE812705D873C4E27F6A5D6E7846B`。保存与宏禁用重开均返回 FileFormat 52。74 个目标行、特殊第 248 行和所有非目标空白断言通过。

### 测试 B：已有 `.xlsm` 再次保存

复制测试 A，Q3 从 100.3 改为 100.4，调用 `Workbook.Save()`，生成 `samples\expected\office_spike\Excel_xlsm再次保存结果.xlsm`。大小 827,595 字节，SHA-256 `8B6D8984DD35DA817AD9D64F9A726D0DD111394DC7709C6D9CCAF0BE8999DC5C`。除 Q3 外未检出其他测试结果变化。

### Excel 差异与进程边界

- 关键内容和对象全部通过，但 Excel 保存规范化了 7 个原样式：A2 的空白单元格样式重置；P239、P240、P246、P249、P277、P280 增加垂直居中。原值和原公式未改变。该差异不是本任务定义的关键失败，但必须披露，不能宣称逐样式完全无损。
- 条件格式内部 `dxfId` 顺序发生重排；对应的规则、范围、公式、优先级、字体和填充语义一致，归类为必要且已解释的元数据变化。
- 本机 Excel 在 `Quit()`、COM 释放并等待 15 秒后仍可能驻留。测试仅在 Hwnd→PID 归属成立且 `Workbooks.Count=0` 时，对记录的单一专属 PID 使用精确回收兜底；所有会话最终无 Excel 残留。正式程序必须把 Excel 自动化放进独立辅助进程，并保留同等所有权校验；不能按进程名结束 Excel。

## 6. WPS 测试结果

隔离探测前已有用户 WPS/ET 进程和一个可见样表窗口。`DispatchEx("KET.Application")` 每次创建新的 ET PID，COM Hwnd 能映射到该 PID；`Quit()` 只关闭本次 ET/伴生进程，原有 PID 和可见窗口指纹不变。

测试 C 生成 `samples\expected\office_spike\WPS_样表转换结果.xlsm`，大小 830,711 字节，SHA-256 `56F6F13E28057C7041777B761BE1ED6D546391D98FD04CB66836632ED5A1A34E`。WPS 和 Excel 均可宏禁用重开，FileFormat=52。

测试 D 使用 `Workbook.Save()` 修改 Q3，生成 `samples\expected\office_spike\WPS_xlsm再次保存结果.xlsm`，大小 830,709 字节，SHA-256 `C05E07E99CB03B5BA5593313F68BB2C95CE27B42C5D7A1A859DAC590AF66083E`。

WPS 将 M 列筛选的 OOXML 表示从 `Filters=[非线路报价]` 改为 `CustomFilters(operator=equal, value=非线路报价)`；AutoFilter 范围、筛选列、筛选语义、FilterMode 和 206 个隐藏行不变。两份 WPS 结果未检出原 A:P 样式差异。

## 7. DISPIMG、图片和视觉验证

四份结果均保留 5 个 DISPIMG 公式及位置、`xl/cellimages.xml`、其关系文件和两个 JPEG：

- `xl/media/image1.jpeg`：389,880 字节，SHA-256 `0A168DA3140007D2279307859A0B44E52CF2186026F009CC7A241C194BA1C040`；
- `xl/media/image2.jpeg`：391,281 字节，SHA-256 `6C61EAFC0B615B3FB83BE0C121E505FEF0F1BEE1768643B157CA7446F5023A9F`。

使用隔离 WPS COM 对源文件及四份结果的 O38/O39/O58/O78/O118 邻域执行 `Range.CopyPicture`，共生成 25 张 PNG，并以原始分辨率人工检查。所有位置均显示真实缩略图，无 `#NAME?`、空白或错误占位。WPS C/D 的 PNG 与源逐文件和 RGBA 像素哈希一致；Excel A/B 彼此逐像素一致，渲染画布宽度比源多 1 像素，但图片位置和内容未改变。证据位于 `logs\office_spike\visuals` 和 `visual_capture_audit.json`。

## 8. 宏安全与宏保留

已自动创建 `tests\fixtures\office_spike_macro_fixture.xlsm`，包含标准模块 `SpikeModule`、`Workbook_Open` 无害标记、窗体按钮、普通公式和形状。未修改信任中心设置。

- Excel 宏禁用打开后 Z1 仍为 `NOT_RUN`；保存后 `HasVBProject=True`，3 个 VBA 组件及源码逐行一致，按钮、形状和公式保留。
- WPS 打开、保存和再次打开后 Z1 均为 `NOT_RUN`；Excel 交叉重开仍识别 VBA、按钮、形状和公式；3 个 VBA 组件及源码逐行一致。
- Excel 保存使 `vbaProject.bin` SHA-256 从 `300A023B...F85C` 变为 `CE05EC26...3838`；WPS 保存又变为 `8C28FA90...578A`。源码级内容一致，因此本无签名夹具判定宏语义保留通过；数字签名状态、签名有效性、ActiveX/UserForm 和受保护 VBA 工程仍未实测。

## 9. 能力承诺边界

当前可以承诺：在本机版本和本样表/安全夹具范围内，Excel 与 WPS 可生成和再次保存有效 `.xlsm`；关键公式、DISPIMG 资源与显示、筛选语义、隐藏行、条件格式、工作表结构和无签名 VBA 源码可保留；宏不会在本工具打开过程中自动运行；用户既有 WPS 窗口不受影响。

当前不能承诺：任意 Office/WPS 版本完全兼容、逐字节或逐样式无损、VBA 数字签名继续有效、ActiveX/UserForm/受保护 VBA/Excel 4.0 宏安全、所有第三方加载项环境下的进程行为。Excel 正式保存必须依赖专属辅助进程和单 PID 兜底，WPS 必须在每次运行时重新验证 Hwnd/PID 归属。

## 10. 下一阶段建议

建议进入阶段 3B，条件是：

1. Office 后端按本次已验证的隔离、宏禁用、原件保护、重开和比较门实现；
2. Excel 使用独立辅助进程，不采用长期驻留在 GUI 进程中的 COM 会话；
3. WPS 只有在新 ET PID 与 Hwnd 归属成立时启用保存；否则回退为“当前不支持/实验性”；
4. 保存后继续执行关键对象对比，并向用户披露 Excel 的 7 个样式规范化差异；
5. 阶段 4 继续保留真实高德 `paths.distance` 单位确认门槛。

本阶段未开发 GUI、真实高德 API、正式缓存、便携 EXE 或完整业务流程。
