# Native XVF converter component diagnostic

Purpose: measure the actual app.live_audio.StreamingDecimator dependency and memory cost, then independently compare a NumPy causal FIR candidate on the CM5. This does not open a microphone, play audio, load speech models, or qualify live integration.

Inputs: the already admitted 16 kHz PCM16 saved source, expanded by repeating each sample three times into an explicitly constructed 48 kHz diagnostic; impulse, quiet and empty controls. The original native constructor supplies the exact 97 float64 FIR coefficients. Cases cover regular and irregular block boundaries, fresh repeats, sample counts and unchanged inputs. Existing 1 ms filter delay and no appended tail flush are preserved. Numeric max-absolute tolerance is fixed at 1e-7 before execution. This is audio amplitude parity, not the separate D1 1e-5 probability gate or speech accuracy.

Files: live_decimator_check_v1.py executes the component; decimator_numpy_v1.py holds the unintegrated candidate; dispatch_live_decimator_v1.py stages fresh admissions; live_decimator_gate_v1.py shares the existing preview lease. review_live_decimator_v1.py independently reconstructs the full causal convolution and validates closure, bindings and outputs. Candidate dispatch requires the closed original reference review.

Resource envelope: CPU2/3, CPUquota200%, one native thread, 768 MiB hard virtual address limit, 1 MiB startup stack, 64 tasks, 90 seconds, 32 MiB reserved output per dispatch. Fresh host census, >=850 MiB target available RAM and >=5 GiB disk are required. No changes to the original app, OS or previous evidence.

Outputs stay private in local/n5/research-extension-20260928/pi-native-20260928/<run>-evidence and corresponding target directories: admissions, exact owners, original WAV hardlink, coefficients, output arrays, resource results, dispatch receipt and independent review. Raw arrays/audio are not committed.

## Run from PowerShell

Use the campaign worktree, a fresh window_guard census, and the installed environment:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$p = 'research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928'
$census = 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V23.json'
& $py -B "$p/dispatch_live_decimator_v1.py" --run-id live-decimator-reference-v1 --census $census
& $py -B "$p/review_live_decimator_v1.py" --run-id live-decimator-reference-v1
& $py -B "$p/dispatch_live_decimator_v1.py" --run-id live-decimator-numpy-v1 --census $census
& $py -B "$p/review_live_decimator_v1.py" --run-id live-decimator-numpy-v1
```

## CMD or Anaconda Prompt

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "P=research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928"
set "CENSUS=G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V23.json"
"%PY%" -B "%P%/dispatch_live_decimator_v1.py" --run-id live-decimator-reference-v1 --census "%CENSUS%"
"%PY%" -B "%P%/review_live_decimator_v1.py" --run-id live-decimator-reference-v1
"%PY%" -B "%P%/dispatch_live_decimator_v1.py" --run-id live-decimator-numpy-v1 --census "%CENSUS%"
"%PY%" -B "%P%/review_live_decimator_v1.py" --run-id live-decimator-numpy-v1
```

Run IDs are single-use; never overwrite or repeat an existing run. Census must be under 15 minutes old. Review completion is component-only: application memory, capture routing, rate/channel selection, long-run state, visible UI and real spoken/noisy audio remain separate gates.
