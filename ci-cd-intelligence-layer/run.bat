@echo off
REM Windows batch file to launch the run.py script using the workspace virtual environment if available.

set SCRIPT_DIR=%~dp0
set WORKSPACE_DIR=%SCRIPT_DIR%..
set VENV_PYTHON=%WORKSPACE_DIR%\.venv\Scripts\python.exe

if exist "%VENV_PYTHON%" (
    echo [Launcher] Found virtual environment at .venv
    "%VENV_PYTHON%" "%SCRIPT_DIR%run.py"
) else (
    echo [Launcher] Workspace .venv not found, trying system python
    python "%SCRIPT_DIR%run.py"
)

pause
