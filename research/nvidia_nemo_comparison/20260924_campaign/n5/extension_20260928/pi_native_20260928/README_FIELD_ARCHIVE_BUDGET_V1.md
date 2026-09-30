# Explicit archive metadata and auxiliary bounds

Purpose: derive `archive_budget_v1/app/sessions.py` from the exact installed v12 archive without changing old releases. An explicit `archive_budget` validates raw metadata input <=16MiB, combined resources/windows/transforms output <=2MiB, and each epoch/conversation JSON <=64KiB. Initial epoch metadata is serialized and checked before directory/thread publication. Replacement metadata checks exact UTF-8 bytes before creating a temporary file, then fsyncs and replaces; old and temporary files are both included in allocation. Existing event journal, PCM, queue/record, free-space and failure-accounting guards remain. Enhanced audio is unavailable in this compact contract. Stores without the new contract retain legacy limits and SQLite behavior.

The bounded compact archive creates no SQLite index: its production reopen path already decodes compact events directly. Native small fixtures check one actual SessionStore saved/reopened synthetic caption and 160 generated zero samples, not microphone silence. Small lowered limits separately force raw metadata and combined auxiliary failures, drain the accepted following queue item without pretending it completed, preserve PARTIAL/error/count gaps, and publish worker_alive=false after joining. Control overflow preserves prior bytes and leaves no temporary file. Invalid config, oversized initial metadata and enhanced mode reject before epoch publication. Maximum-sized files are not rewritten. No installed Controller/live/GUI propagation or long-recording success is claimed.

Inputs: immutable installed v12 release, exact source/derivative hashes, ARCHIVE_BUDGET_V1.json, current authority and fresh CPU14 census. Outputs: small native fixtures, case receipts, applied resource envelope, independent review and exact private backup. Synthetic data, config copies and failures stay private. Limits apply to the epoch/store writers, not an entire live source/TRACE/service/log allocation. Only one compact epoch, its two possible control JSON versions and optional one conversation's two JSON versions can be summed with their specific counts. No policy allowance is changed. A later live run still needs source/TRACE/control telemetry budgets, an installed config/manifest binding and a fresh complete target+host admission.

The isolated native worker uses CPU2,3/shared200%, one library thread,768MiB AS,1MiB stacks,Tasks64,300s with60sStop and32MiB per-file ceiling; stricter4MiB target+4MiB host total admission. Initial850MiB available; sampled192MiB available/640MiB aggregate stops. Fixed32GB Pi retains5GiB free. WINDOW_V5 and52GiB total remain unchanged. Config/release/baseline are preserved; no catalogue/asset/runtime/audio fixture copy, models, PortAudio, playback, GUI or capture.

PowerShell:
```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B dispatch_field_archive_budget_v1.py --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V161.json'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B review_field_archive_budget_v1.py
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B backup_field_archive_budget_v1.py
```

CMD / Anaconda Prompt (the explicit existing Python needs no environment switch):
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_archive_budget_v1.py --census "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V161.json"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_archive_budget_v1.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B backup_field_archive_budget_v1.py
```

The fresh dispatcher refuses an existing run root and binds immutable inputs. Review/backup outputs are exclusive. Failures remain evidence; do not rerun a passed case or edit a bound source. The module helper accepts `validate(config)`, `publish(path, value, byte_limit)` and the archive/store policy accepts `archive_budget=config`; the protocol is the documented bounded native invocation. Extended external import/export remains unqualified.
