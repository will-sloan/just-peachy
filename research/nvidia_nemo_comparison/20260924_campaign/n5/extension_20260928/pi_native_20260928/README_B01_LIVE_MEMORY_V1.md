# First real B01 failure and import-only memory investigation

Purpose: preserve and independently review the first user-consented live trial, then measure whether importing the actual audio dependency contributes virtual reservations absent from the saved-source fixture. This does not repeat capture, loosen the 768 MiB cap, alter models, or edit the original app. The failed live source receipt reports restoration before native abort; the reader checks actual command readbacks separately from absent application finalization.

`review_b01_live_failure_v1.py` reads the fixed private run `b01-live-trial-user-20260929T175035Z`, exact owners, admission/source hashes, unit ABRT outcome, allocation errors, partial events, device receipt/readbacks and sampled process memory. It creates a private exclusive-write FAILURE_REVIEW_V1.json. Its successful review records a failed trial; it is not successful live application acceptance. No transcription text or audio is published.

`live_import_memory_v1.py` runs in a fresh admitted native process, samples /proc status/smaps before imports, after application imports and after sounddevice import, and exits. It instantiates no controller/model/stream and sends no XVF commands. Importing sounddevice initializes PortAudio host APIs; capture status must remain closed. The purpose is import-related memory attribution, not complete live-stream memory qualification. No inference, recording, playback, training, download or GUI. Smaps evidence stays private.

Inputs: unchanged qualified shared-app-b01-fir-v1 source and installed Python/audio dependencies, existing admission guards, a fresh comprehensive host census. Outputs: private live-import-memory-v1[-evidence] source-bound admission, exact owners, process mappings, memory stages, RESULT, launch and independent review. Guard reuses the research flock and original app/boot/source checks. CPUs2/3,total200%,Tasks64,one numerical thread,hard768MiB virtual,1MiB stacks,180s service,10s stop,>=850MiB available RAM/5GiB disk;8MiB output reservation within the existing combined1GiB allowance. No settings or shared ledger changes.

PowerShell:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_b01_live_failure_v1.py
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/dispatch_live_import_memory_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V33.json
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_live_import_memory_v1.py
```

CMD / Anaconda Prompt: `cd /d G:\Just_Peachy_N1\20260924_campaign\worktree`; use the same commands without `&` and double-quote the interpreter path. Existing Python is reused; no environment installation. Census must be under15minutes old. Preserve the fixed run and any failure; use a fresh version rather than overwriting. A later capture requires the user's current readiness; this code never opens a stream.
