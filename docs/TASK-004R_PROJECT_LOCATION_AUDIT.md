# TASK-004R 项目目录审计

审计时间：2026-07-20 16:19（Asia/Shanghai）  
审计性质：只读目录与 Git 审计；除本报告外未执行任何写入。  
禁止动作确认：未执行回滚、复制、移动、删除或清理。

## 1. TASK-004R 实际项目根目录

TASK-004R 实际使用并写入的项目根目录为：

```text
D:\AI project\非线路运距计算
```

核验结果：

- `Get-Item` 解析为 `D:\AI project\非线路运距计算`；
- Git 根目录为 `D:/AI project/非线路运距计算`；
- 目录是普通目录，`LinkType` 为空，不是符号链接或目录联接；
- 本报告路径 `D:\AI project\非线路运距计算\docs\TASK-004R_PROJECT_LOCATION_AUDIT.md` 位于该根目录内；
- `docs` 也是普通目录，`LinkType` 为空。

## 2. 本任务文件变更清单

### 2.1 新增的永久源码、脚本和文档

```text
D:\AI project\非线路运距计算\src\amap\driving_clients.py
D:\AI project\非线路运距计算\scripts\run_driving_real.py
D:\AI project\非线路运距计算\scripts\capture_driving_visuals.py
D:\AI project\非线路运距计算\scripts\final_task004r_audit.py
D:\AI project\非线路运距计算\docs\CURRENT_STATUS.md
D:\AI project\非线路运距计算\docs\DRIVING_API_DESIGN.md
D:\AI project\非线路运距计算\docs\DRIVING_REAL_TEST_REPORT.md
D:\AI project\非线路运距计算\docs\TASK-004R_RESULT.md
D:\AI project\非线路运距计算\docs\USER_GUIDE_DRAFT.md
D:\AI project\非线路运距计算\docs\archive\truck_api_abandoned\README.md
D:\AI project\非线路运距计算\docs\TASK-004R_PROJECT_LOCATION_AUDIT.md
```

最后一项是本次目录审计按用户要求新增的报告，不属于 TASK-004R 功能开发。

### 2.2 修改的永久源码、测试、脚本和文档

```text
D:\AI project\非线路运距计算\CURRENT_STATUS.md
D:\AI project\非线路运距计算\README.md
D:\AI project\非线路运距计算\requirements\requirements.txt
D:\AI project\非线路运距计算\requirements\requirements-lock.txt
D:\AI project\非线路运距计算\docs\API_INTEGRATION_DESIGN.md
D:\AI project\非线路运距计算\docs\DISTANCE_UNIT_VALIDATION.md
D:\AI project\非线路运距计算\docs\VEHICLE_PARAMETER_VALIDATION.md
D:\AI project\非线路运距计算\docs\REAL_API_TEST_REPORT.md
D:\AI project\非线路运距计算\docs\TASK-004_RESULT.md
D:\AI project\非线路运距计算\docs\TASK-004_WAITING_FOR_KEY.md
D:\AI project\非线路运距计算\docs\MANUAL_ROUTE_CHECKLIST.md
D:\AI project\非线路运距计算\docs\PROTOTYPE_DESIGN.md
D:\AI project\非线路运距计算\src\__init__.py
D:\AI project\非线路运距计算\src\domain\models.py
D:\AI project\非线路运距计算\src\domain\ports.py
D:\AI project\非线路运距计算\src\amap\mock_clients.py
D:\AI project\非线路运距计算\src\amap\distance.py
D:\AI project\非线路运距计算\src\amap\errors.py
D:\AI project\非线路运距计算\src\amap\real_clients.py
D:\AI project\非线路运距计算\src\amap\http_client.py
D:\AI project\非线路运距计算\src\cache\sqlite_cache.py
D:\AI project\非线路运距计算\src\application\processor.py
D:\AI project\非线路运距计算\src\application\runner.py
D:\AI project\非线路运距计算\src\workbook\preview.py
D:\AI project\非线路运距计算\src\workbook\writeback.py
D:\AI project\非线路运距计算\src\workbook\verification.py
D:\AI project\非线路运距计算\src\office\worker.py
D:\AI project\非线路运距计算\src\ui\main_window.py
D:\AI project\非线路运距计算\src\main.py
D:\AI project\非线路运距计算\src\security\key_store.py
D:\AI project\非线路运距计算\scripts\verify_cf_com.py
D:\AI project\非线路运距计算\tests\test_amap_http.py
D:\AI project\非线路运距计算\tests\test_cache.py
D:\AI project\非线路运距计算\tests\test_mock_clients.py
D:\AI project\非线路运距计算\tests\test_processor.py
D:\AI project\非线路运距计算\tests\test_real_clients.py
D:\AI project\非线路运距计算\tests\test_real_mode.py
D:\AI project\非线路运距计算\tests\test_workbook_preview.py
D:\AI project\非线路运距计算\tests\test_ui_smoke.py
```

说明：`distance.py`、`real_clients.py`、`processor.py`、`test_real_clients.py` 和 `test_real_mode.py` 在实现过程中采用同路径替换方式重写，最终仍存在，因此按“修改”而不是“删除”记录。

### 2.3 新增的报告、证据和视觉文件

```text
D:\AI project\非线路运距计算\docs\evidence\TASK004R_CONNECTION.json
D:\AI project\非线路运距计算\docs\evidence\TASK004R_SMALL_ROUTES.json
D:\AI project\非线路运距计算\docs\evidence\TASK004R_EXCEL_VALIDATION.json
D:\AI project\非线路运距计算\docs\evidence\TASK004R_WPS_VALIDATION.json
D:\AI project\非线路运距计算\docs\evidence\TASK004R_VISUAL_CAPTURE.json
D:\AI project\非线路运距计算\docs\evidence\TASK004R_FINAL_AUDIT.json
D:\AI project\非线路运距计算\docs\evidence\visuals\excel\top.png
D:\AI project\非线路运距计算\docs\evidence\visuals\excel\conflict.png
D:\AI project\非线路运距计算\docs\evidence\visuals\excel\multi_destination.png
D:\AI project\非线路运距计算\docs\evidence\visuals\wps\top.png
D:\AI project\非线路运距计算\docs\evidence\visuals\wps\conflict.png
D:\AI project\非线路运距计算\docs\evidence\visuals\wps\multi_destination.png
D:\AI project\非线路运距计算\docs\evidence\visuals\excel_native\top.png
D:\AI project\非线路运距计算\docs\evidence\visuals\excel_native\conflict.png
D:\AI project\非线路运距计算\docs\evidence\visuals\excel_native\multi_destination.png
D:\AI project\非线路运距计算\docs\evidence\visuals\excel_via_wps\top.png
D:\AI project\非线路运距计算\docs\evidence\visuals\excel_via_wps\conflict.png
D:\AI project\非线路运距计算\docs\evidence\visuals\excel_via_wps\multi_destination.png
D:\AI project\非线路运距计算\docs\evidence\visuals\wps_native\top.png
D:\AI project\非线路运距计算\docs\evidence\visuals\wps_native\conflict.png
D:\AI project\非线路运距计算\docs\evidence\visuals\wps_native\multi_destination.png
```

审计时 `docs\evidence` 共 21 个文件、9,162,665 字节。

### 2.4 新增或更新的运行产物

正式缓存：

```text
D:\AI project\非线路运距计算\cache\driving_real.sqlite
```

该文件创建于 2026-07-20 15:19:28，审计时大小 1,343,488 字节，最后修改时间 15:37:49。既有 `D:\AI project\非线路运距计算\cache\task_003b.sqlite` 最后修改于 03:27:05，不属于 TASK-004R 写入。

最终 Excel 结果：

```text
D:\AI project\非线路运距计算\samples\expected\driving_real\Excel_样表_普通驾车距离结果_待验收.xlsm
D:\AI project\非线路运距计算\samples\expected\driving_real\WPS_样表_普通驾车距离结果_待验收.xlsm
```

审计时分别为 828,654 和 831,745 字节。

真实调用与 Office 审计日志全部保存在以下绝对目录中：

```text
D:\AI project\非线路运距计算\logs\driving_real
```

该目录审计时共有 108 个文件、2,278,618 字节；文件时间范围为 2026-07-20 15:19:18 至 15:37:49。其子目录全部属于 TASK-004R：

```text
D:\AI project\非线路运距计算\logs\driving_real\connection_validation
D:\AI project\非线路运距计算\logs\driving_real\small_route_validation
D:\AI project\非线路运距计算\logs\driving_real\task004r_excel_20260720152001
D:\AI project\非线路运距计算\logs\driving_real\task004r_wps_20260720152630
D:\AI project\非线路运距计算\logs\driving_real\task004r_excel_20260720153139
D:\AI project\非线路运距计算\logs\driving_real\task004r_wps_20260720153615
```

Office 工作副本、作业 JSON 和响应 JSON 全部保存在：

```text
D:\AI project\非线路运距计算\samples\working\driving_real
```

该目录审计时共有 76 个文件、7,404,901 字节；其 TASK-004R 子目录为：

```text
D:\AI project\非线路运距计算\samples\working\driving_real\task004r_excel_20260720152001
D:\AI project\非线路运距计算\samples\working\driving_real\task004r_wps_20260720152630
D:\AI project\非线路运距计算\samples\working\driving_real\task004r_excel_20260720153139
D:\AI project\非线路运距计算\samples\working\driving_real\task004r_wps_20260720153615
```

Python/pytest 在 `src`、`scripts`、`tests` 下的 `__pycache__` 以及根目录 `.pytest_cache` 中生成或更新了常规测试缓存。这些是自动测试运行产物，不是交付源码；本审计没有清理它们。

### 2.5 删除的文件

没有永久项目文件被净删除，也没有移动文件。SQLite 和原子写入过程可能短暂创建 `-wal`、`-shm`、`.partial` 或点前缀临时文件，并在正常关闭或原子替换后消失；这些属于库和安全保存机制的临时生命周期，不是人工清理或项目文件删除。

## 3. 是否修改 `D:\AI project\直播智能切片`

结论：**TASK-004R 没有修改该目录。**

依据：

- 本任务所有写工具调用的工作目录和目标路径均位于 `D:\AI project\非线路运距计算`；
- `D:\AI project\直播智能切片` 根目录最后修改时间为 2026-07-20 02:13:14；
- 从 TASK-004R 开始时间约 14:57 至本次审计，递归检查未发现该目录内有文件写入；
- 本次只对该目录执行了 `Get-Item`、`Get-ChildItem` 和 `git status` 等只读命令。

该目录当前 Git 工作区并不干净，但这些状态在 TASK-004R 时间窗之前已存在，不能归因于本任务。

## 4. 是否修改 `D:\AI project\非线路运距计算`

结论：**是。** TASK-004R 的源码、测试、缓存、真实调用日志、报告和 Excel/WPS 结果均实际保存在该目录下，具体路径见第 2 节和第 6 节。

## 5. 两个目录的 Git status

### 5.1 `D:\AI project\直播智能切片`

执行命令：

```powershell
git -C "D:\AI project\直播智能切片" status --short --branch --untracked-files=all
```

结果：

```text
## master
 M .gitignore
 M docs/CURRENT_STATUS.md
 M docs/DECISIONS.md
?? docs/ASR_DEPENDENCY_PLAN.md
?? docs/ASR_MODEL_COMPARISON_REPORT.md
?? experiments/__init__.py
?? experiments/asr/README.md
?? experiments/asr/__init__.py
?? experiments/asr/adapters/__init__.py
?? experiments/asr/adapters/base.py
?? experiments/asr/adapters/faster_whisper.py
?? experiments/asr/adapters/paraformer.py
?? experiments/asr/adapters/sensevoice.py
?? experiments/asr/benchmark.py
?? experiments/asr/common.py
?? experiments/asr/locks/faster-whisper.lock.txt
?? experiments/asr/locks/funasr.lock.txt
?? experiments/asr/locks/sherpa-onnx.lock.txt
?? experiments/asr/metrics.py
?? experiments/asr/normalize.py
?? experiments/asr/resource_monitor.py
?? experiments/asr/review.py
?? experiments/asr/tests/test_benchmark.py
?? experiments/asr/tests/test_common.py
?? experiments/asr/tests/test_metrics.py
?? experiments/asr/tests/test_review.py
?? tasks/TASK-002.md
?? tasks/reports/TASK-002_RESULT.md
```

这些改动/未跟踪文件不属于 TASK-004R。

### 5.2 `D:\AI project\非线路运距计算`

执行命令：

```powershell
git -C "D:\AI project\非线路运距计算" status --short --branch --untracked-files=all
```

结果首行为：

```text
## No commits yet on master
```

随后 `.gitignore`、`CURRENT_STATUS.md`、`README.md`、`docs/`、`pytest.ini`、`requirements/`、`scripts/`、`src/` 和 `tests/` 中的项目文件全部显示为 `??`。原因是该仓库尚无首次提交；不存在可供 Git 比较的已跟踪基线。被 `.gitignore` 忽略的 `cache/`、`logs/`、`samples/input/`、`samples/working/` 和 `samples/expected/` 不会出现在普通 `git status` 中，但已在本报告单独审计。

因此：Git status 可以证明当前仓库没有提交，但不能单独区分 TASK-004R 与更早 TASK-003/TASK-004 创建的文件。第 2 节分类依据本次工具操作记录、文件时间线和 TASK-004R 命名运行目录。

## 6. 本次实际保存位置确认

| 类别 | 实际绝对路径 |
| --- | --- |
| 项目源码 | `D:\AI project\非线路运距计算\src` |
| 自动测试 | `D:\AI project\非线路运距计算\tests` |
| TASK-004R 正式缓存 | `D:\AI project\非线路运距计算\cache\driving_real.sqlite` |
| 真实 HTTP/Office 日志 | `D:\AI project\非线路运距计算\logs\driving_real` |
| Office 工作副本与作业记录 | `D:\AI project\非线路运距计算\samples\working\driving_real` |
| 设计报告 | `D:\AI project\非线路运距计算\docs\DRIVING_API_DESIGN.md` |
| 真实测试报告 | `D:\AI project\非线路运距计算\docs\DRIVING_REAL_TEST_REPORT.md` |
| 任务结果报告 | `D:\AI project\非线路运距计算\docs\TASK-004R_RESULT.md` |
| 当前状态 | `D:\AI project\非线路运距计算\CURRENT_STATUS.md` |
| JSON/视觉证据 | `D:\AI project\非线路运距计算\docs\evidence` |
| Excel 结果 | `D:\AI project\非线路运距计算\samples\expected\driving_real\Excel_样表_普通驾车距离结果_待验收.xlsm` |
| WPS 结果 | `D:\AI project\非线路运距计算\samples\expected\driving_real\WPS_样表_普通驾车距离结果_待验收.xlsm` |
| 本目录审计 | `D:\AI project\非线路运距计算\docs\TASK-004R_PROJECT_LOCATION_AUDIT.md` |

安全保存的高德 Key 位于项目的本机安全凭据机制中，本任务只读取它；未在本报告中记录 Key 值，也未修改凭据文件。

## 7. 最终确认

- TASK-004R 实际根目录：`D:\AI project\非线路运距计算`；
- `D:\AI project\直播智能切片`：本任务未修改；
- `D:\AI project\非线路运距计算`：本任务已修改并保存全部成果；
- 两个目录的 Git status 已分别执行；
- 未执行任何回滚、复制、移动、删除或清理；
- 本次审计完成后不继续开发。
