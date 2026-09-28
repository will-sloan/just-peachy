@echo off
rem User-invoked encoder-free D1 preview; see README_D1_ANONYMOUS_PREVIEW_V1.md.
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%~dp0start_d1_anonymous_preview_v1.py" --encoder none %*
exit /b %ERRORLEVEL%
