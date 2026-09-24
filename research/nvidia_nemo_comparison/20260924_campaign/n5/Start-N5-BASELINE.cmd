@echo off
rem Purpose: open the preserved baseline idle with isolated campaign data.
rem Inputs: optional Start-N1.ps1 arguments. Outputs: existing GUI/private data.
powershell.exe -NoProfile -File "%~dp0..\Start-N1.ps1" %*
exit /b %ERRORLEVEL%
