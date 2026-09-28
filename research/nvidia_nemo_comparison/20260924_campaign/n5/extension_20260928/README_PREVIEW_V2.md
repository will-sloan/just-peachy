# Engineering previews with visible backend failures

Purpose: provide separate user launchers for the source containing the verified error-priority repair. These are Windows saved-file engineering previews, not accepted N4/N5 releases or Pi packages. The old launchers/source stay unchanged. The new launcher requires both the selected backend's full-file E0-parent lifecycle review and the fresh UI-derivative controls/startup/recovery review. It verifies ancestry, source, assets, configuration and process receipts before proceeding.

Inputs: retained local assets, `a0-controls-v3-REVIEW.json` / `a2-controls-v3-REVIEW.json`, the matching E0-parent review, and optionally an already-prepared mono 16 kHz PCM16 O0 WAV. Without both reviews the corresponding preview refuses to launch. Outputs: captions and isolated saved sessions under `local/n5/prepi-20260928/Windows-A0-ui-error-v1-preview` or `Windows-A2-ui-error-v1-preview`. Original personal data is never used. E0 remains available, but these empty-gallery previews do not establish persistent naming accuracy.

Only the user launches a visible app. The agent uses `--check-only`, which starts no GUI, model, microphone or playback. Visible launches open idle unless `--wav` is supplied, refuse a live campaign worker, share the old preview exclusion lock, use CPUs4/14 with one native thread/model and GPU off, and keep live input disabled. Close the preview before scheduled numerical work. No target connection, training, enrollment or downloads occur.

PowerShell / Anaconda PowerShell, from this directory:

```powershell
$researchPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $researchPython -B build_preview_v2.py
& $researchPython -B start_preview_v2.py --backend A0 --check-only
& $researchPython -B start_preview_v2.py --backend A2 --check-only
# Later user-operated launch, only after campaign worker closure:
& .\Start-SHERPA-NEMOTRON-REDIMNET.cmd
# Alternative after closing the first:
& .\Start-NEMOTRON-NEMOTRON-REDIMNET.cmd
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928
set "RESEARCH_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%RESEARCH_PY%" -B build_preview_v2.py
"%RESEARCH_PY%" -B start_preview_v2.py --backend A0 --check-only
"%RESEARCH_PY%" -B start_preview_v2.py --backend A2 --check-only
rem Later user-operated launch after workers close:
Start-SHERPA-NEMOTRON-REDIMNET.cmd
rem Or the alternative after closing the first:
Start-NEMOTRON-NEMOTRON-REDIMNET.cmd
```

Optional input: append `--wav "ABSOLUTE_PREPARED_O0_PATH.wav"` to a user-operated launcher. No additional gain is applied. These launchers do not carry private model assets into Git; the local hash-addressed assets remain prerequisites. The generator refuses existing output files. The checkpoint still governs automated research; a user preview is an explicit interactive action, not an automatically dispatched campaign worker.
