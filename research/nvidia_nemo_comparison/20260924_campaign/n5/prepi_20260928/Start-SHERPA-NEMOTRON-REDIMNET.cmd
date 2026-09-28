@echo off
rem User-invoked saved-file A0/D1/E0 preview. See README_PREVIEW.md.
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%~dp0start_preview_v1.py" --backend A0 %*
exit /b %ERRORLEVEL%
