@echo off
rem User-operated saved-file preview; README_PREVIEW_V2.md.
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%~dp0start_preview_v2.py" --backend A0 %*
exit /b %ERRORLEVEL%
