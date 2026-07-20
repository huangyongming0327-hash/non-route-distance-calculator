@echo off
setlocal

cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo ERROR: Python virtual environment was not found.
    echo Expected file:
    echo %CD%\.venv\Scripts\python.exe
    echo.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m src.main %*

set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo Program failed to start.
    echo Exit code: %EXIT_CODE%
    echo.
    pause
)

endlocal & exit /b %EXIT_CODE%
