@echo off
title Syncing Subtitle AI to autosub
echo ========================================================
echo   Syncing all updated files from New folder to autosub
echo ========================================================

robocopy "D:\projects\New folder" "D:\projects\autosub" /E /XD .git node_modules __pycache__ /XO /NFL /NDL /NJH /NJS

echo.
echo Sync Complete! Starting backend in D:\projects\autosub\backend ...
cd /d "D:\projects\autosub\backend"
python main.py

pause
