# Preflighted target metadata V1

Purpose: bound actual target staging and runtime ownership/envelope metadata before publication. A fresh dispatcher stages code/ and control/ through the retained exact GroupWriter, publishes control/ADMISSION.json last, then uses the same control group for actual OWNER, DISPATCH_OWNER and LIVE_ENVELOPE. No model/source/Controller/audio/capture/GUI runs. The V80 outer writer is reused without rerunning its failure protocol.

Inputs: fresh CPU14 host census, unchanged WINDOW_V5, September29 authority, exact original install/config/boot/PID/start identities, closed capture/free leases and retained V80 dispatcher plus V74 helper hashes. The admitted bootstrap executes the new staged module's exact supplied bytes in memory after verifying the retained helper; every staged byte is then hash-bound in ADMISSION. No full release, catalogue, runtime or asset copy. Original baseline and personal data remain unchanged.

The entire code/control batch is checked in memory before creating its destination: exact groups, flat names, byte payloads, finite control JSON, per-write/file/group/file-count ceilings and mandatory final admission marker. Code2MiB/512KiBfile/64files; control1MiB/64KiBfile/16files;5GiB free floor. Three runtime names are forbidden in the initial batch, with three file slots and3xmaximum_file_bytes reserved before publication. Runtime controls use those exact bounds. Other arbitrary control names reject. Every file uses GroupWriter pre-write checks/fsync/readback; existing destinations and partial writes are preserved, not retried or deleted.

Nine cases: one tiny complete batch with last-admission/repeat rejection, seven prepublication rejects (path/codebytes/filecount/controlbytes/nonfinite/runtime reservation/runtime name), and one injected interrupted control write. The interruption retains both code files and exactly three CONFIG.json.pending bytes, leaves no ADMISSION and returns an explicit StageFailure. This is an injected write fault, not real disk exhaustion/power loss. All input bytes, outcomes and partial files stay private. No unchanged generic writer/outer/source/controller/timer tests run.

Three fixture directories reserve196608bytes. The actual code/control/outer capsule declares nine directories and reserves589824bytes within the existing1MiB directory allowance. Exact optional outer directory names are validated before creation; all directories precede file publication and the final admission marker. Observed directory extents are checked during publication. Other fixture/archive/transport/host directories and inode/journal metadata are not claimed covered. A failed directory creation or write preserves partials and prevents normal dispatch; no automatic cleanup/retry. This does not provide an external-writer filesystem hard quota.

Actual staged code/control hash checks and bounded OWNER/DISPATCH_OWNER/LIVE_ENVELOPE are independently reviewed. LIVE_ENVELOPE retains the prior live systemd/AS/stack/affinity/cgroup property queries; only its publication destination/writer changes. Actual resource/log/result outputs reuse V80 mapped groups. Host PREFLIGHT/launch/review/backup/automation metadata and fixture harness files remain under the existing small admission, not a new portable host writer. Host metadata and full archive/transport directory enforcement remain next; this is not a field launch or capture admission.

Envelope: actual main768MiBAS/1MiBstack/CPU2,3/shared200%/Tasks64/300s/Stop60/32MiBfile; bootstrap/gate128MiBAS CPU3. One native thread/GPUoff. Initial850MiB available, sampled192MiB available/640MiB unique-owner aggregate stops.4MiB target+4MiB host. Fixed32GBPi/5GiB floor,5GiB campaign output/52GiB total with retained2.5GiB reservations and checkpoint unchanged. The future156MiB capture proposal is still unadmitted and must be reassessed against shrinking headroom.

Outputs: ~/JustPeachy/research/nemotron-20260928/field-metadata-budget-v1 on Pi; private field-metadata-budget-v1-evidence on host. Code in code/, ADMISSION/backups/descriptor/ownership/envelope in control/, V80 outputs in outer/. Independent REVIEW and exact BACKUP include all partial fixtures. Audio/transcripts/profiles/weights/credentials never enter Git.

## PowerShell

Run once. Use a fresh numbered census under15minutes. Do not recreate an existing census or retry a staged/completed/failed target; changed recovery needs a fresh reviewed derivative/admission.

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B -c "import psutil; psutil.Process().cpu_affinity([14]); import sys,json; from pathlib import Path; sys.path.insert(0,str(Path.cwd().parent)); from window_guard_v5 import snapshot; b=Path(r'G:\Just_Peachy_N1\20260924_campaign\local'); json.dump(snapshot(b,8*1024**2),(b/'n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V174.json').open('x',encoding='utf-8'),indent=2)"
& $py -B dispatch_field_metadata_budget_v1.py --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V174.json'
& $py -B review_field_metadata_budget_v1.py
& $py -B backup_field_metadata_budget_v1.py
& $py -B collect_native_closure_v5.py --version 173
```

## Command Prompt / Anaconda Prompt

Use the existing interpreter directly without installs or activation. For a new census, use the same Python -c body above with the quoted full interpreter instead of `& $py`.

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_metadata_budget_v1.py --census "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V174.json"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_metadata_budget_v1.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B backup_field_metadata_budget_v1.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B collect_native_closure_v5.py --version 173
```

Internal --gate/--worker flags belong only to the new dispatcher. The host dispatcher explicitly invokes code/dispatch_field_metadata_budget_v1.py. No old launcher flags are invented. No capture, baseline activation, quality/endurance, host metadata or full-N5 acceptance follows from this test.
