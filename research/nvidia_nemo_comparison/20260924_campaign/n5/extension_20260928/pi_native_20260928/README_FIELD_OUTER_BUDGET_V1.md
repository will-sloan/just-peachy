# Bounded outer dispatcher outputs V1

Purpose: integrate the qualified GroupWriter at the actual new dispatcher's service-log, resource-row, worker RESULT and gate DISPATCH_RESULT writes. This fresh dispatcher runs nine small changed failure fixtures, with no source, audio, Controller, model or GUI. Older dispatchers/admissions/evidence remain immutable. This is not a capturable field launcher.

Inputs: fresh CPU14 host census, WINDOW_V5, exact original app/config/boot/PID/start ticks, free leases and closed capture, pinned previous dispatcher, new adapter/helper/dispatcher/allocation hashes and OUTER_DESCRIPTOR. Retained allocation V2 supplies logs/telemetry/receipts/failure/closure_reserve groups. Each group enforces exact pre-write bytes, file size, total bytes, file count and5GiB free-space floor via the unchanged helper. Six declared directories reserve393216bytes; observed real-directory membership/extents are checked at publication. The scope excludes the rest of the archive/transport/host layout and all other filesystem inode/journal overhead.

Actual gate writes outer/logs/service.log in whole blocks, with64KiB maximum pipe reads including the final drain. Resource rows go to outer/telemetry/resources.jsonl; the in-memory sample list is cleared after each row, and the final receipt contains a row count instead of a growing sample array. Owner sampling deduplicates exact boot/PID/start ticks. When the worker finishes too quickly, the observed gate/owner aggregate remains a real sample, with worker_rss_sample_available=false where applicable. It is not a worker peak measurement.

Actual worker RESULT and gate DISPATCH_RESULT use outer/receipts. Per-role reserved closures go to outer/closure_reserve. Work_complete means the worker protocol returned, or the gate reaped its systemd-run process and closed its pipe, respectively; it never asserts the still-running writer process is dead. Independent closure checks provide that evidence. Each receipt/finalization permits one attempt; subsequent finalized outcomes are detached copies and cannot silently change failed closure to success.

On the first write/serialization failure, the sink latches failure and requests Stop BEFORE diagnostics. The gate uses actual systemctl Stop; small failure fixtures use a counted callback, including an injected callback exception. Rejected raw blocks and subsequent tails append to a separate role-specific failure file. It records byte counts and SHA, does not slice accepted blocks, and explicitly reports incomplete raw retention if the reserve rejects. After that rejection it does not retry that mutation; additional bytes only update counts/hash. Live unbounded producers and arbitrary blocking Stop/GIL/process stalls are not qualified. All fixture inputs remain private even when the sink's reserve rejects. Nonfinite serialization has no encoded byte payload and records a ValueError; its literal input is specified in the preserved fixture source.

Nine changed cases: log first-write quota, append quota plus retained tail, resource quota, RESULT quota, DISPATCH_RESULT quota, diagnostic quota, closure quota, Stop callback exception, nonfinite serialization. They verify explicit failure, one Stop request, preserved old bytes, exact rejected bytes where retained, repeat-finalization immutability and no receipt retry. No unchanged generic writer/controller/source/timer protocol is rerun. In addition, the actual outer gate/worker use the new mapped writes for this run; those ordinary receipts and samples are independently reviewed.

Outputs: target ~/JustPeachy/research/nemotron-20260928/field-outer-budget-v1; host private field-outer-budget-v1-evidence. All source/admission/owner/envelope/cases, partial/failure inputs, REVIEW and exact BACKUP are retained. OWNER/LIVE_ENVELOPE, staging, host launch/backup metadata and fixture-harness files still use the older bounded dispatcher admission, not the new mapped sinks. They must be integrated separately before whole-run acceptance. The fixture sink accepts arbitrary test roots only within the admitted fresh harness; the actual gate root is fixed by its bound source/admission. No claim of external-writer filesystem hard quota, real exhaustion or power-loss recovery.

Envelope: main768MiBAS, gate128MiBAS; main1MiBstack/CPU2,3/shared200%/Tasks64/300s/Stop60/32MiBfile, one native thread, GPUoff. Initial850MiB RAM available; sampled192MiB availability/640MiB unique-owner aggregate stops.4MiB target plus4MiB host. Fixed32GBPi with5GiB available, current5GiB output and52GiB total with retained2.5GiB reservations remain unchanged. No policy revision or capture admission.

## PowerShell

Run only once with a fresh numbered census under15minutes. V173 is this prepared run's census; do not recreate existing evidence or retry the same target after any stage/failure. Use a fresh reviewed derivative for changed work.

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B -c "import psutil; psutil.Process().cpu_affinity([14]); import sys,json; from pathlib import Path; sys.path.insert(0,str(Path.cwd().parent)); from window_guard_v5 import snapshot; b=Path(r'G:\Just_Peachy_N1\20260924_campaign\local'); json.dump(snapshot(b,8*1024**2),(b/'n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V173.json').open('x',encoding='utf-8'),indent=2)"
& $py -B dispatch_field_outer_budget_v1.py --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V173.json'
& $py -B review_field_outer_budget_v1.py
& $py -B backup_field_outer_budget_v1.py
& $py -B collect_native_closure_v5.py --version 172
```

## Command Prompt / Anaconda Prompt

Use the existing interpreter directly, without installs or activation. For a new census use the same Python -c body above with the quoted full interpreter in place of `& $py`.

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_outer_budget_v1.py --census "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V173.json"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_outer_budget_v1.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B backup_field_outer_budget_v1.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B collect_native_closure_v5.py --version 172
```

Internal --gate/--worker belong only to this dispatcher. Future live integration requires remaining mapped staging/owner/envelope/host writes, complete directory limits, explicit source/controller bindings and a fresh complete measured allocation. Current156MiB proposal is not admitted; do not reset usage, delete evidence or silently raise52GiB.
