# V1.0 RC1 便携版打包报告

打包日期：2026-07-21  
功能冻结提交：`62ad85b81e8f77cf9b2118463af25d08182be536`

## 1. 打包方案

- 工具：PyInstaller 6.21.0
- 模式：onedir
- 启动类型：windowed，不显示不必要的黑色命令行窗口
- Python：3.12.10，随包携带
- 主要依赖：PySide6 6.9.1、openpyxl 3.1.5、Pillow 12.3.0、psutil 7.2.2、pywin32 312
- 构建脚本：`scripts/build_release.ps1`
- 验证脚本：`scripts/verify_portable_release.ps1`、`scripts/verify_frozen_office_worker.py`
- 清理与 ZIP：`scripts/finalize_release.ps1`

选择 onedir 是为了避免 onefile 每次启动解压造成的额外等待。精简掉 pywin32 测试/演示模块的过度收集后，发布目录约 126.45 MB。

## 2. 输出

- 发布目录：`D:\AI project\非线路运距计算\release\非线路运距计算工具_V1.0_RC1`
- EXE：`D:\AI project\非线路运距计算\release\非线路运距计算工具_V1.0_RC1\非线路运距计算工具.exe`
- ZIP：`D:\AI project\非线路运距计算\release\非线路运距计算工具_V1.0_RC1_便携版.zip`
- 首轮最终化 ZIP 大小：55,179,421 字节；最终元数据提交后由同一脚本重建。

发布目录包含：

- `非线路运距计算工具.exe`
- `_internal`
- `config`、`cache`、`logs`、`outputs`、`temp`
- `USER_GUIDE.md`
- `使用说明.pdf`
- `VERSION.txt`
- `CHANGELOG.md`
- `KNOWN_ISSUES.md`

## 3. 便携根目录与资源处理

- 开发运行时根目录为项目根目录；冻结运行时根目录为 EXE 所在目录。
- `config/cache/logs/outputs/temp` 均在便携版目录下创建，不把大量数据写到 C 盘。
- 车型资源 JSON 打入 `_internal/src/config`。
- 冻结 Office 子进程使用同一 EXE 的 `--office-worker` 入口，不依赖源代码或本机 `.venv`。
- 启动异常写入 `logs/startup_error.log`，阶段耗时写入 `logs/startup.log`。

## 4. 独立运行验证

验证了：

- 发布目录直接运行；
- 复制到另一中文路径运行；
- 复制到带空格路径运行；
- 目录内没有 `src`；
- 目录内没有 `.venv`；
- 三处 EXE 退出码均为 0；
- 最慢主窗口出现时间 2.272 秒；
- 冻结 EXE 的 Excel/WPS 子进程入口可用。

## 5. 数据迁移

API与设置页提供：

- 导出/导入可信地址库；
- 导出/导入普通驾车地理编码与路线缓存。

迁移文件为带格式版本的 JSON。路线缓存导出不包含任务历史、源文件路径、Key 或行级结果。备份仍可能包含业务地址，手册已要求受控保存。

## 6. 发布安全检查

清理后的目录与 ZIP 扫描结果：

- 禁止扩展名文件：0；
- Key/Token/Password/Secret 高熵赋值命中：0；
- `config`：0 个文件；
- `cache`：0 个文件；
- `logs`：0 个文件；
- `outputs`：0 个文件；
- `temp`：0 个文件；
- 业务 Excel：0；
- SQLite/数据库：0；
- `.env`/凭据：0；
- `src`：不存在；
- `.venv`：不存在。

项目本机的真实缓存、DPAPI 凭据、日志和业务样表仍留在被 `.gitignore` 排除的开发目录中，没有复制进公共发布包。

## 7. 已知打包限制

- 尚未在 Windows 10 目标机验证。
- Office COM 依赖目标机正确安装并注册 Excel 或 WPS。
- 新电脑必须由当前 Windows 用户重新输入 Key。
- 杀毒软件可能让新复制目录的首次进程退出比主窗口出现更慢；本轮主窗口出现仍低于 3 秒。
