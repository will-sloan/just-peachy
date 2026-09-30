# Shared producer slots and archive Stop binding V1

Purpose: connect preserved archive publication failures to a latched Stop request and independent closure evidence, using one shared sidecar layout. This is changed native archive-worker integration. It does not activate the installed controller or qualify live source/model/storage composition.

`field_run_outputs_v1.py` owns three directories: failure, closure and telemetry. Ten producers (entry, source, transport, presentation, worker, gate, stage, archive, native and launcher) each reserve64KiB raw failure,8KiB failure JSON and32KiB closure. Presentation and gate separately reserve256KiB append telemetry with8KiB writes. Names, publication modes and individual limits are fixed. Under the retained GroupWriter filesystem lock, each file is checked against its own slot as well as the group total; a producer cannot consume another slot. Allocation is1,589,248bytes plus262,144bytes for four directories, total1,851,392bytes per shared root. Pending bytes count and remain preserved; the retained helper conservatively blocks further writes to that group after any pending failure. Closure uses another group. One owner per producer is required; concurrent-owner or arbitrary external-writer stress is not qualified.

Failure latches before calling a nonblocking `request_stop` callback and before writing diagnostics. Callbacks must signal/queue Stop, never join the current archive thread. Failed or oversized raw retention remains explicit. Each closure is attempted once; a failed closure is never converted into success by a repeated call. This module covers sidecars only. Source/config/TRACE/native journals/archive files and complete host backup are still outside this shared layout; the full run is not qualified by adding these byte totals.

`field_archive_stop_v1.py` wraps the actual retained EpochArchive. Archive errors request Stop once; queue rejection also reaches this path. Publication failure latches its exact outcome and disables further publisher calls during worker finalization and close. Close joins the real archive thread and writes the shared archive closure with counts/error/physical worker status, then raises when the archive failed. The old primary may remain OPEN after failure: only the separate closure reports the joined worker; no primary is rewritten to fabricate success. Constructor/queue/closure-callback failures are implemented but not all exercised by this protocol. No durable cross-process archive failure latch is claimed.

The retained finalization sessions source calls its detail publisher with262144bytes. New `field_archive_budget_v4.py` therefore extends V3's explicit slot ceiling to262144, while the actual epoch/conversation callers retain65536. Old-plus-pending detail is524288bytes; primary131072bytes and failure detail262144bytes bring these three reserved maxima to917504bytes, within the existing1MiB diagnostic reserve. This is control/diagnostic arithmetic, not complete archive allocation. The copied `archive_stop_sessions_v1.py` changes only its helper import and documentation; all class/method bodies are retained. V3's11-case pass stays unchanged and does not imply whole-archive compatibility.

Inputs: fresh CPU14 census, exact baseline/leases/closed-capture/resource preflight, unchanged WINDOW_V5, source hashes and six retained v12 module/config/manifest pins. The actual app package and bounded artifact module come from v12; the sessions module is the fresh exact derivative loaded as app.sessions in an isolated research process. No package/catalogue/model assets are recopied. Test metadata is synthetic and private.

Changed checks: two distinct producer closure files share a root; four malformed/slot-limit requests reject without writing the archive closure. The rejected32769byte payload is preserved privately. Two actual archive workers then exercise (1) a three-byte injected checkpoint short write after successful initial publication: only two publisher writes total, old primary preserved, worker joined and independent failed closure; (2) late70000character metadata: actual detail publication exceeds64KiB, source-stop event set and joined PARTIAL metadata/counts retained. The external Stop is explicitly a real threading.Event fixture with an ordering observer, not a hardware source, engine or installed Controller. No audio samples, models, capture, GUI, physical exhaustion, power loss or concurrency stress. No old V101/component suites rerun.

Outputs: Pi `~/JustPeachy/research/nemotron-20260928/field-archive-stop-v1`; private host `field-archive-stop-v1-evidence`. Three separate shared sidecar roots reserve5,554,176bytes. The fixed protocol adds two no-audio archive directories and four case receipts (128KiB total/64KiB each). Stage/outer outputs remain scoped by retained guards and sampled target cap; this is not whole-live writer maxima or a filesystem hard quota. A fresh16MiB admission (8MiB target+8MiB host) must fit both caps, irrespective of the earlier census's requested-byte example. The dispatcher recomputes target-inclusive admission using16MiB; no old policy is changed.

Envelope: actual768MiB AS/1MiB stack/CPU2,3/shared200%/Tasks64/300s/Stop60/32MiB file, one native model thread/GPUoff; gate128MiB CPU3. Initial850MiB available, sampled192MiB available/640MiB aggregate stops. Fixed32GB Pi/5GiB free floor, host C50GiB/G75GiB floors, 52GiB total payload and5GiB combined output unchanged. Preserve display270 and original rc5. All work/cleanup/backup before October1 17:42:44UTC; finalization starts16:42:44UTC.

## PowerShell

Run once after fresh source/owner/allocation review. Use a new census/output version; never retry a staged target or overwrite a closed receipt.

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B -c "import psutil; psutil.Process().cpu_affinity([14]); import sys,json; from pathlib import Path; sys.path.insert(0,str(Path.cwd().parent)); from window_guard_v5 import snapshot; b=Path(r'G:\Just_Peachy_N1\20260924_campaign\local'); json.dump(snapshot(b,16*1024**2),(b/'n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V198.json').open('x',encoding='utf-8'),indent=2)"
& $py -B dispatch_field_archive_stop_v1.py --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V198.json'
& $py -B review_field_archive_stop_v1.py
& $py -B backup_field_archive_stop_v1.py
& $py -B collect_native_closure_v5.py --version 217
```

## Command Prompt / Anaconda Prompt

Use the existing interpreter without installs or activation. A fresh census uses the same Python `-c` body above with the quoted interpreter instead of `& $py`.

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_archive_stop_v1.py --census "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V198.json"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_archive_stop_v1.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B backup_field_archive_stop_v1.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B collect_native_closure_v5.py --version 217
```

Internal gate/worker flags belong only to this dispatcher. To integrate later, supply the shared RunOutputs and nonblocking real controller/source Stop callback to `archive_class`, bind that class before Store.begin, and account every other producer before enabling capture. Full live, operator, offline and field acceptance remain open until observed.
