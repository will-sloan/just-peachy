@echo off
rem User-invoked A2/D1 anonymous-speaker preview; see README_NEMOTRON_WINDOWS_PREVIEW_V1.md.
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%~dp0start_nemotron_preview_v1.py" --mode anonymous_conversation %*
exit /b %ERRORLEVEL%
