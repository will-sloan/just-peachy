# Opt-in saved-file desktop prototype — native qualification pending

App.py supplies ordinary configuration-driven file and GUI commands around the same frozen S7 engine, eight assets and original C065/C088 profiles. It does not consume research job manifests at runtime. Prepare.py creates CONFIG.json and copies existing headless/GUI execution adapters plus the exact AST-equivalent closure predicate. Research queues and original defaults stay unchanged.

Modes: caption_only(M0), open_conversation(M1), open_with_names(M2), selected_emphasis(M3). These are implementation candidates pending native smoke/mode qualification. M0 actually disables optional identity work in the existing engine. M3 uses the full gallery and display emphasis; it is not a restricted classifier. Strict filters, directions and scanner are not exposed pending eligibility decisions. Start a fresh process to change the model workload; GUI mode switching is disabled. Selection, full view and manual active/listening/dim controls remain. Dim does not reduce model work.

Inputs: CONFIG.json with explicit source integrity, eight asset paths/hashes, two profile definitions and gallery location; English mono16kHz16-bit PCM WAV at already prepared gain; optional selected gallery IDs. No mixing, resampling, gain or trimming. Live device/recording/enrollment controls are disabled. Outputs: a fresh run folder with LAUNCH.json, RESULT.json, native session/consumer/resource/GUI logs and rotating application.log. Actual GUI runs close after full source and writer drain. No audio playback.

Application diagnostics rotate at1MiB with4backups per fresh run. Full session/scientific evidence is preserved separately and never auto-deleted. Maximum input is one hour. Study runs remain subject to the S7 runner40GiB cap and C/G free-space floors; future runs need space for preserved evidence. Retention never scans other directories.

Preparation/checks are safe during core compute. Do not execute file/gui while measured native/analysis work owns the machine. Native smokes and clean-path relocation remain mandatory before recommendation. File/gui examples are implemented but not yet executed; final handoff must use actual tested inputs/receipts.

## PowerShell
~~~powershell
$Task = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S7\20260917T141700Z\application\prototype_v1'
$Py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $Py -B "$Task\Prepare.py"
& $Py -B "$Task\App.py" --help
& $Py -B "$Task\App.py" validate --config "$Task\CONFIG.json" --mode caption_only
& $Py -B "$Task\App.py" profiles --config "$Task\CONFIG.json"
& $Py -B "$Task\App.py" gui-check --config "$Task\CONFIG.json" --mode open_with_names
# After qualification/serial admission; actual WAV and fresh output paths:
& $Py -B "$Task\App.py" file --config "$Task\CONFIG.json" --mode caption_only --wav 'G:\path\to\mono.wav' --output 'G:\path\to\fresh_file_run'
& $Py -B "$Task\App.py" gui --config "$Task\CONFIG.json" --mode open_with_names --wav 'G:\path\to\mono.wav' --output 'G:\path\to\fresh_gui_run'
~~~

## Anaconda Prompt / CMD
~~~bat
set "TASK=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S7\20260917T141700Z\application\prototype_v1"
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%PY%" -B "%TASK%\App.py" validate --config "%TASK%\CONFIG.json" --mode caption_only
"%PY%" -B "%TASK%\App.py" gui-check --config "%TASK%\CONFIG.json" --mode open_with_names
"%PY%" -B "%TASK%\App.py" file --config "%TASK%\CONFIG.json" --mode caption_only --wav "G:\path\to\mono.wav" --output "G:\path\to\fresh_file_run"
"%PY%" -B "%TASK%\App.py" gui --config "%TASK%\CONFIG.json" --mode open_with_names --wav "G:\path\to\mono.wav" --output "G:\path\to\fresh_gui_run"
~~~

Use the existing environment; no installation/activation. validate verifies source integrity, asset presence/schema and actual engine construction, but does not hash full models or instantiate neural models. file/gui verify model hashes. gui-check constructs the actual withdrawn window without source/model. profiles prints enrolled IDs/names. Add --selected ID1 ID2 for selected_emphasis using returned IDs.

Missing/invalid gallery is an explicit error by default. --allow-caption-fallback explicitly permits M0 fallback and records reason/effective mode; valid ASR assets remain necessary. --language accepts this configured English model; --device fails with saved-file instructions. Wrong WAV channels/rate/encoding are rejected. To stop, create STOP_REQUEST in the exact output folder. Cancellation preserves evidence and is not full completion.

Rollback: close this opt-in process and use the prior launcher. Defaults, enrolled vectors, weights, historical evidence and the Word guide are unchanged. Portable config/gallery derivatives and Windows native smokes remain pending; no CM5/ARM64/power claims. Existing output files are refused; preserve failures rather than rebuilding into them.

