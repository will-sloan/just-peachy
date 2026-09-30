# Entry configuration publication V1

Purpose: prepare the selected installed entry CONFIG through explicit byte/file/group and directory bounds. The exact installed native/field_entry_v5.py _live_config config dictionary projection is retained. Dynamic epoch-UUID mkdir is replaced by a declared source directory; direct JSON publication and IsolatedLiveConfig return are replaced by bounded publication and an explicit CONFIGURATION_PREPARED_NOT_LAUNCHABLE receipt. The original intended capture=true/quiet_only=true values are preserved in the prepared CONFIG; no source factory, transport, Controller, model, GUI or capture is invoked. No launchable IsolatedLiveConfig object is returned. This is not a new live launcher and does not pass new flags to any old launcher.

Inputs: fresh CPU14 census; exact retained entry/authority/ALSA paths and hashes; adapter/helper/allocation pins; exact private data config hash, epoch and admitted root. The small data/live_config.json fixture is an exact private copy of the admitted baseline backup, not a modification of personal data. Descriptor schema/scope/source/map/group and directory limits are validated before the entry layout. The root must be a new direct child of the admitted fixture parent. Config values, types and mapped paths are exact; the CONFIG byte ceiling is checked before any entry directory exists. Each publisher permits one attempt, preserving rejected or successful evidence without retries or deletion.

The declared layout is five directories: root plus config/source/failure/closure_reserve. It reserves5x64KiB=327680bytes of directory extent capacity within the retained1MiB metadata allowance and128-directory ceiling. Before CONFIG publication, after publication and after closure, a cooperating layout lock checks exact membership, real directories, max(st_size,st_blocks*512) for each directory, count/extent limits and GroupWriter inventories. Directory creation itself reserves the declared capacity first; unexpected observed growth rejects publication. The selected layout is not the whole archive/transport/host directory tree or a filesystem hard quota against external writers. Directory extents do not claim to count every filesystem inode/journal/superblock overhead. GroupWriter retains its5GiB free-space floor and exact old+pending/file/count limits.

CONFIG.json uses config; case_directory points to source. CONFIG_CLOSURE.json in closure_reserve records preparation only. A failed closure preserves the published CONFIG, reports failure and returns no prepared object; it never retries that rejected write. Separate CONFIG_REJECTED.bin/CONFIG_FAILURE.json retain bounded diagnostics when the layout and failure budget allow. Injected unexpected-directory drift rejects CONFIG and diagnostics, leaves all directories intact and reports raw retention false; the harness independently retains the exact input bytes. No raw-retention or logical-success claim is fabricated after a publication failure.

Fourteen native cases: seven malformed descriptors (fields/scope/source pin/map/directory count/directory reserve/group budget) reject before layout; seven config cases cover exact mapped publication plus duplicate-attempt rejection, bad factory, bool/int capture confusion, first-write cap, bool epoch, injected directory drift, and closure quota. Only two CONFIG files are expected: complete preparation and closure-failed preparation. No unchanged generic GroupWriter/source/transport/controller tests run. Inputs for changed failure cases are retained privately even when the adapter cannot retain them. All private cases, source/envelope/owner/RESULT/REVIEW/BACKUP remain preserved.

Main768MiBAS/1MiBstack/CPU2,3/shared200%/Tasks64/300s/Stop60/32MiBfile. Initial850MiB available, sampled192MiB available/640MiB unique-identity aggregate stops.4MiB target+4MiB host. Fixed32GBPi/5GiB available floor,5GiB campaign output and52GiB total including retained2.5GiB reservations unchanged. This does not admit the proposed long capture. Outputs are field-entry-config-budget-v1 on target and field-entry-config-budget-v1-evidence privately on host. No full release/catalogue/runtime/asset copy.

## PowerShell

Run once. Use a fresh numbered census under15minutes; never recreate V172 if it already exists or retry an admitted completed/failed target. Recovery needs a fresh reviewed derivative/admission.

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B -c "import psutil; psutil.Process().cpu_affinity([14]); import sys,json; from pathlib import Path; sys.path.insert(0,str(Path.cwd().parent)); from window_guard_v5 import snapshot; b=Path(r'G:\Just_Peachy_N1\20260924_campaign\local'); json.dump(snapshot(b,8*1024**2),(b/'n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V172.json').open('x',encoding='utf-8'),indent=2)"
& $py -B dispatch_field_entry_config_budget_v1.py --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V172.json'
& $py -B review_field_entry_config_budget_v1.py
& $py -B backup_field_entry_config_budget_v1.py
& $py -B collect_native_closure_v5.py --version 171
```

## Command Prompt / Anaconda Prompt

Use the existing interpreter explicitly; no install/download or activation. To create a fresh census, use the same Python census command with the full quoted interpreter in place of `& $py`.

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_entry_config_budget_v1.py --census "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V172.json"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_entry_config_budget_v1.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B backup_field_entry_config_budget_v1.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B collect_native_closure_v5.py --version 171
```

Internal --gate/--worker flags belong only to the dispatcher. Outer service logs/resources/RESULT/staging/host metadata and complete archive/transport/host layout enforcement remain pending, followed by a fresh complete allocation and explicit live binding. Research configurations, original baseline and all older releases/policies/admissions remain immutable. No microphone, physical-GUI, quality, endurance, arbitrary external-writer or power-loss acceptance.
