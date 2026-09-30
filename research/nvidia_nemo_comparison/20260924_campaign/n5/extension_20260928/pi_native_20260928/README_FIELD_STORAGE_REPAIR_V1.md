# Native storage repair components V1

Purpose: address two concrete V84 integration blockers before composing live D1 storage. New immutable derivatives preserve failed archive control bytes and reject overflowing target JSON numbers before staging. This does not activate a release, repair V65 retroactively, or qualify the complete live source/model/storage path.

`field_archive_budget_v3.py` retains V2 budget, encoding, detail and index behavior. Its new publisher reserves an old control and one deterministic `.name.pending` slot, each at most the supplied limit (1–65536 bytes). It exclusively creates the pending file, checks a complete write, flushes/fsyncs, replaces the control and fsyncs the directory. No failure unlinks a partial. An existing pending file prevents publication before writing. `PublicationFailure.replaced` distinguishes failure before replacement from failure after replacement; callers must latch Stop, preserve files and inspect the outcome, never retry. This is a single archive writer contract, not concurrent-writer or crash recovery qualification. Post-replacement directory-fsync failure leaves the new control and explicitly reports replacement; cross-process retries after that outcome are not prevented by a durable failure marker. The installed archive must be rebound and its failure latch verified before live use.

`field_metadata_budget_v2.py` retains the exact V1 stage/control layout and limits. It adds a finite float-token parser, including duplicate-key values that would disappear after JSON decoding. Positive, nested negative and hidden duplicate overflow reject before mkdir/writer invocation. Finite input bytes are preserved, including an underflow token; exact numerical underflow representation is not claimed. The new dispatcher's real code/control staging also uses V2. Old V1 and V83 host evidence remain separate.

Inputs: a fresh CPU14 host census, WINDOW_V5 and authority, exact baseline boot/PID/start/config/install identities, free leases, closed capture, unchanged retained outer/helper sources and the reviewed small source list. Every byte is bound in ADMISSION. No model/audio/UI/release assets are copied or opened.

The changed native protocol runs eleven cases: four injected archive I/O failures (three-byte short write, file fsync, replacement, directory fsync), successful publication, pre-existing pending rejection, oversized-control rejection, three float overflow rejections, and finite exact-byte staging. Faults are injected at named Python I/O seams while actual private files are written on the Pi. They are not physical disk exhaustion, power loss, arbitrary native stalls or concurrency tests. No failed mutation is retried. All partials and test inputs remain private. The finite stage success checks only the new raw parser path, not the old metadata suite.

Outputs: `~/JustPeachy/research/nemotron-20260928/field-storage-repair-v1` on Pi and private `field-storage-repair-v1-evidence` on host. Stage code/control and outer receipts use the existing guarded paths. Small fixture files have a declared 64KiB/24-file/8KiB-file ceiling; each actual archive payload is bounded by its 1KiB control slot and each stage payload by preflight. Twelve directories reserve 768KiB. Two case/closure receipts share 64KiB, 32KiB per write/file. The harness checks the total fixture layout after the fixed list; this is not a generic filesystem hard quota. The existing outer/stage maxima are admission-scoped and are not a proof of full live composition fit.

Envelope: fresh 4MiB target +4MiB host allocation under unchanged 52GiB payload and 5GiB combined output caps; Pi fixed32GB and 5GiB free floor. Main768MiB AS, stack1MiB, CPU2,3/shared200%, Tasks64,300s/Stop60,32MiB file, one thread/GPUoff. Gate128MiB CPU3, initial850MiB available, sampled192MiB available/640MiB aggregate stops. Save actual properties, review exact closure, then back up every file. No capture, model, GUI, new speed or accuracy claim.

## PowerShell

Run once after a fresh census and source/allocation review. Existing output labels and bound sources must never be overwritten or retried. The collector performs CPU14 setup before reading; the dispatcher does likewise. Use an unused census/closure version when continuing later.

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B -c "import psutil; psutil.Process().cpu_affinity([14]); import sys,json; from pathlib import Path; sys.path.insert(0,str(Path.cwd().parent)); from window_guard_v5 import snapshot; b=Path(r'G:\Just_Peachy_N1\20260924_campaign\local'); json.dump(snapshot(b,8*1024**2),(b/'n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V197.json').open('x',encoding='utf-8'),indent=2)"
& $py -B dispatch_field_storage_repair_v1.py --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V197.json'
& $py -B review_field_storage_repair_v1.py
& $py -B backup_field_storage_repair_v1.py
& $py -B collect_native_closure_v5.py --version 215
```

## Command Prompt / Anaconda Prompt

Use the existing interpreter directly, without installs or activation. For a fresh census use the same Python `-c` body above with the quoted interpreter instead of `& $py`.

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_storage_repair_v1.py --census "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V197.json"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_storage_repair_v1.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B backup_field_storage_repair_v1.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B collect_native_closure_v5.py --version 215
```

Internal `--gate`/`--worker` are only for this fresh dispatcher. No old launcher gains new flags. Preserve display270 and original rc5. All work plus cleanup/backup must finish before October1 17:42:44UTC; no feature/model work after16:42:44UTC.
