@echo off
cd /d "%~dp0"
"C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -X utf8 -m measurement_app.server --open-browser
if errorlevel 1 pause
