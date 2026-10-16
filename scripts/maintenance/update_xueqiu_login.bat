@echo off
chcp 65001 > nul
echo ==========================================
echo Update Xueqiu Login State
echo ==========================================
echo.
echo This script will:
echo 1. Open Edge browser with your existing profile
echo 2. Wait for you to login to xueqiu.com (if not already logged in)
echo 3. Export the login state to xueqiu-state.json
echo 4. Upload it to the server
echo 5. Restart the browser worker
echo.
echo Press any key to start...
pause > nul

cd /d "%~dp0..\.."

echo.
echo Step 1: Exporting login state...
echo (Edge browser will open, check if you are logged in to xueqiu.com)
echo.

REM Select the repository/backend virtual environment first. Windows Store
REM execution aliases can exist without providing a working python.exe, so
REM fall back to the Python launcher only when it is actually available.
set "PYTHON="
if exist ".venv\Scripts\python.exe" set "PYTHON=.venv\Scripts\python.exe"
if not defined PYTHON if exist "backend\.venv\Scripts\python.exe" set "PYTHON=backend\.venv\Scripts\python.exe"
if not defined PYTHON (
    where py >nul 2>&1
    if not errorlevel 1 set "PYTHON=py -3"
)
if not defined PYTHON (
    where python >nul 2>&1
    if not errorlevel 1 set "PYTHON=python"
)
if not defined PYTHON (
    echo ERROR: No working Python interpreter was found.
    echo Install Python 3 or create a virtual environment, then try again.
    pause
    exit /b 1
)
echo Using Python: %PYTHON%

pushd backend
%PYTHON% export_xueqiu_state.py
set "EXPORT_EXIT=%ERRORLEVEL%"
popd

if not "%EXPORT_EXIT%"=="0" (
    echo.
    echo ERROR: Failed to export login state
    echo Please check if Edge opened correctly and you completed the login
    pause
    exit /b 1
)

echo.
echo Step 2: Uploading to server...
if not exist "backend\data\xueqiu-state.json" (
    echo ERROR: Export completed without creating backend\data\xueqiu-state.json
    pause
    exit /b 1
)
scp backend\data\xueqiu-state.json ubuntu@124.222.169.60:/data/app/backend/data/

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Failed to upload file
    pause
    exit /b 1
)

echo.
echo Step 3: Restarting browser worker...
ssh ubuntu@124.222.169.60 "cd /data/app/backend && docker compose restart browser-worker"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Failed to restart worker
    pause
    exit /b 1
)

echo.
echo ==========================================
echo SUCCESS!
echo ==========================================
echo.
echo Xueqiu login state has been updated successfully.
echo The crawler should start working again in the next run.
echo.
echo You can check the logs with:
echo   ssh ubuntu@124.222.169.60 "docker logs -f backend-browser-worker-1"
echo.
echo Press any key to close this window...
pause > nul
