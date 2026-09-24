@echo off
setlocal
powershell.exe -NoProfile -File "%~dp0Start-N1.ps1" %*
exit /b %ERRORLEVEL%
