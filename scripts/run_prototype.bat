@echo off
setlocal
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] 未找到项目虚拟环境：.venv
  echo 请先按 README.md 安装依赖。
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m src.main
if errorlevel 1 pause
endlocal
