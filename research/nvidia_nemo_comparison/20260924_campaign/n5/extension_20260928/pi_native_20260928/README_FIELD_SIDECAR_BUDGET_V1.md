# Native sidecar output budgets V1

Purpose: give source receipts, TRACE, controls, logs and telemetry explicit pre-write byte/file limits, and finish the arithmetic for a complete target plus host-backup proposal. This is a small no-capture component test. The old source/GUI/dispatcher writers are not silently replaced. The 120-second live path is still unadmitted and whole-run integration is false.

## Inputs, outputs and allocation

`FIELD_WHOLE_RUN_ALLOCATION_V1.json` retains the reviewed archive/native-journal/conversation maxima and assigns ten bounded sidecar groups. Exact target sum is76MiB; host target-copy maximum76MiB plus4MiB host-only metadata is80MiB, combined156MiB. This corrects an earlier hypothetical80+80MiB plan that did not separately identify backup metadata. Source/config/control groups each1MiB; telemetry/logs/code/receipts/failure each2MiB; TRACE12MiB; remaining5,083,604bytes are explicitly assigned to bounded closure reserve. These are maxima, not observed simultaneous live usage. No allowance changes or live admission follow from the arithmetic. Keep52GiB total payload, retained2.5GiB reservations, all prior output, fixed32GB Pi and5GiB free. Host backup must independently enforce76MiB copied target plus4MiB local metadata.

`field_sidecar_budget_v1.py` validates strict finite integer policies and supplies `GroupWriter` for a dedicated flat directory. Every cooperating writer takes the same nonblocking flock, encodes complete JSON as exact UTF8 before writing, and checks each write/file/group/file-count and the5GiB device reserve. Append refuses the entire new block if it would exceed a bound. Atomic replacements count old plus pending bytes/files before mutation, fsync data/directory, and preserve an interrupted pending file. A retained pending file blocks later writes until separately reviewed. Existing evidence is never deleted, automatically retried or truncated. Physical disk errors may leave a partial append or pending file and are errors, not logical success. Nonregular paths/hardlinks are rejected; open uses NOFOLLOW. The guard is not an OS filesystem quota against external writers or privileged changes. An outer data lease remains necessary in future integration.

`field_sidecar_budget_protocol_v1.py` runs20 small native cases,17 rejection checks. It tests exact Unicode/escaped JSON and JSONL, write/file/group/file-count boundaries, old-plus-pending reservation, successful atomic replacement, path/pending-name rejection, free-floor rejection, lock contention, nonregular input and invalid policies. The free-space result and nonregular stat mode are explicitly injected; no disk exhaustion or physical symlink fixture. Lock contention uses another open flock handle in the same process. An injected os.write failure writes exactly two pending bytes; old bytes remain, and a subsequent different write rejects without modifying either. All synthetic inputs/outcomes stay private. No large files, audio, models, source, controller, Tk or healthy-case reruns.

`dispatch_field_sidecar_budget_v1.py` binds fresh source/policy/authority/census hashes after exact host/Pi owner, unit, lease, original app/config, RAM/disk and target-inclusive accounting checks. It uses a new root only. `review_field_sidecar_budget_v1.py` independently verifies actual envelope, cases, exact retained bytes, free guards and baseline/owner closure. `backup_field_sidecar_budget_v1.py` copies and rehashes every private target file.

Inputs: fresh CPU14 host census, unchanged WINDOW_V5, September29 authority, original baseline identities and these exact source files. Output root: `~/JustPeachy/research/nemotron-20260928/field-sidecar-budget-v1`. Private host root: `G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\field-sidecar-budget-v1-evidence`. Outputs include ADMISSION/owners/LIVE_ENVELOPE, small fixture files, immediate case receipts, aggregate RESULT, review and exact backup. Raw private data never goes to Git.

## Resource envelope and limitations

This test admits4MiB target+4MiB host under unchanged WINDOW_V5. Native768MiB AS,1MiB stack,CPU2/3/shared200%/Tasks64,parent300s/Stop60s/32MiB file,initial850MiB available and sampled192MiB available/640MiB aggregate stops. No child/model process. Host coordinator CPU14. Planned76+80MiB remains larger than current output headroom and needs fresh measured policy/admission before use. Existing live/source/TRACE/log writers still need explicit integration into matching groups; this component pass is not whole-run enforcement, capture, controller finalization, interchange or field readiness.

## PowerShell

Create a fresh census with the existing snapshot interface (CPU14 before reading). This numbered receipt and run are single-use.

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B -c "import psutil; psutil.Process().cpu_affinity([14]); import sys,json; from pathlib import Path; sys.path.insert(0,str(Path.cwd().parent)); from window_guard_v5 import snapshot; base=Path(r'G:\Just_Peachy_N1\20260924_campaign\local'); value=snapshot(base,8*1024**2); out=base/'n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V166.json'; json.dump(value,out.open('x',encoding='utf-8'),indent=2)"
& $py -B dispatch_field_sidecar_budget_v1.py --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V166.json'
& $py -B review_field_sidecar_budget_v1.py
& $py -B backup_field_sidecar_budget_v1.py
& $py -B collect_native_closure_v5.py --version 166
```

## Command Prompt or Anaconda Prompt

Use the existing interpreter explicitly; no install/activation/download. If the census above was already created, do not recreate it. It must be younger than15minutes at dispatch; use a fresh numbered receipt if stale without altering the old one.

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -c "import psutil; psutil.Process().cpu_affinity([14]); import sys,json; from pathlib import Path; sys.path.insert(0,str(Path.cwd().parent)); from window_guard_v5 import snapshot; base=Path(r'G:\Just_Peachy_N1\20260924_campaign\local'); value=snapshot(base,8*1024**2); out=base/'n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V166.json'; json.dump(value,out.open('x',encoding='utf-8'),indent=2)"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_sidecar_budget_v1.py --census "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V166.json"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_sidecar_budget_v1.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B backup_field_sidecar_budget_v1.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B collect_native_closure_v5.py --version 166
```

Never rerun a completed dispatcher or edit a bound source/admission/README. Preserve all failures and prepare distinct reviewed derivatives if necessary. Original app/config/personal data are untouched, so restoration is verification of unchanged baseline. `--worker`/`--gate` are internal guarded execution paths, not user GUI flags.
