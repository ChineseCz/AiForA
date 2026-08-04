@echo off
echo Starting Celery browser worker...
start "Celery-Browser" cmd /k "C:\Users\HJF\PycharmProjec\PythonProject1\backend\.venv-host\Scripts\activate.bat && cd /d C:\Users\HJF\PycharmProjec\PythonProject1\backend && celery -A app.workers.celery_app worker -Q browser --pool=solo"

echo Starting natapp...
start "natapp" C:\Users\HJF\PycharmProjec\PythonProject1\natapp\run_natapp.bat

echo Done.
exit
