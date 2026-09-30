# Corrected ALSA package and installed GUI live boundary

Purpose: repair the specific V1 startup failure in a fresh `b01-offline-20260930-v5` package, then run the new installed GUI Start/Stop boundary. V1 exited1 before GUI/model/capture: the release builder silently omitted `config/alsa_hw_only_v1.conf` because `.conf` was absent from its suffix whitelist. Its failed code/admission/release27file backup remains immutable; no reset or unchanged capture retry.

`field_live_build_v2.py` copies the exact old code-only v4 release into a new source folder, adds the already pinned process-local ALSA config, and makes exactly that relative path an exception to the existing suffix whitelist. A synthetic unrelated.conf must remain excluded. New field_entry_v5 health requires the exact ALSA SHA256 before proceeding. Model/runtime assets are shared without copy. Original v4 and rc5/data/config remain unchanged; no pointer activation. The packaged release_tools/release.py change is produced explicitly by this builder, included in its release manifest and independently compared with v4. Package source plus installed code and ZIP are counted in the same64MiB reservation.

Inputs/outputs, current autonomous quiet authority, safety/resource limits and actual GUI28s Stop/30s backup/512000failure ceiling are the same as README_FIELD_LIVE_GUI_V1.md. `field_live_gui_v2.py` adds only the new build before loading the installed v5 entry. Every accepted tail is retained. The acceptance observer and140s protocol limit are harness safeguards; no unsupervised field/endurance claim. The new entry still needs this live execution; do not infer it from the packaging fix. No solicited speech, playback, reset, model download or enrollment. No new1e-5captured-input reference or acoustic-quality score.

`review_field_live_startup_failure_v1.py` independently verifies V1 exit/log/envelope/exact owners, absent session/source directories, closed capture/leases and unchanged baseline, then hashes/backups all27private files. `review_field_live_gui_v2.py` uses the independent V1 source/PCM/model/closure checks with the new release-build bindings. It also verifies exact prior release preservation, the intended new builder/entry/ALSA changes, rejection of unrelated.conf and actual installed health/GUI passage. Outputs are private REVIEW/BACKUP and pending manual visual inspection. Prior V1 reader remains unused because V1 failed before RESULT.json; it is not a passing review.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B review_field_live_startup_failure_v1.py
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B dispatch_field_live_gui_v2.py --census '<fresh HOST_CENSUS JSON absolute path>'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B review_field_live_gui_v2.py
```
CMD / Anaconda Prompt(existing interpreter; no activation):
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_live_startup_failure_v1.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_live_gui_v2.py --census "<fresh HOST_CENSUS JSON absolute path>"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_live_gui_v2.py
```
Each command is once-only against a fresh run/output directory. V1 failure review has already run; do not repeat it. Fresh census/target accounting and exact ownership/lease checks precede V2 dispatch. All private audio/text/images stay out of Git. LiveCPU/thermal/clock/throttle series is short-run evidence, not endurance. Visible screenshots are not physical touch.
