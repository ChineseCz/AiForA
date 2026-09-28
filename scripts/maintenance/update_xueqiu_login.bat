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

REM Activate virtual environment
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
    echo Using virtual environment
) else (
    echo Warning: Virtual environment not found, using system Python
)

cd backend
python export_xueqiu_state.py
cd ..

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Failed to export login state
    echo Please check if Edge opened correctly and you completed the login
    pause
    exit /b 1
)

echo.
echo Step 2: Uploading to server...
scp data\xueqiu-state.json ubuntu@124.222.169.60:/data/app/backend/data/

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
