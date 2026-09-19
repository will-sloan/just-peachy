@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Restore-XVF.ps1"
if errorlevel 1 echo Restoration did not finish. Read the error above; keep the package and original files.
pause
