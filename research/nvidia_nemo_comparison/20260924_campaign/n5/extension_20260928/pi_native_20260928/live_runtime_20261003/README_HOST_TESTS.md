# Focused host contract checks

This shared README covers the test executables listed below. They check storage/protocol/allocation/UI-source contracts with synthetic or explicitly pinned private fixtures. They are not CM5 model, microphone, acoustic-quality, physical-touch or sustained-runtime measurements. The module-specific READMEs describe the production behavior and any additional fixture requirements. Run only a changed, reviewed test target; do not run discovery or repeat healthy test groups merely for publication.

Inputs: the absolute source directory, an exact unittest module/class/method from this table, the qualified Python interpreter, and a writable private evidence root. Some tests read exact preserved package fixtures; a missing historical fixture is not permission to substitute current files or contact the device. Outputs: fresh registered-owner directory, captured test log and numeric exit summary; temporary synthetic stores/files are managed by the tests. No real recording or gallery is a test input.

| Executables | Purpose and related implementation README |
|---|---|
| `test_backup_external.py`, `test_backup_external_v2.py`, `test_backup_reconciler_v3.py`, `test_backup_reconciliation.py` | Exact backup scope, pins, traversal, transfer and receipt bounds; README_BACKUP_EXTERNAL, README_BACKUP_EXTERNAL_V2, README_BACKUP_RECONCILER_V3, README_PRODUCTION_BACKUP |
| `test_desktop_consolidation.py`, `test_desktop_rollback.py` | Prepared shortcut/rollback contracts; README_DESKTOP_ACTIVATION |
| `test_gui_repair.py`, `test_native_gui_driver.py`, `test_runtime_ui.py` | Actual source labels, bounded UI data and programmatic driver guards; README_NATIVE_GUI_DRIVER, README_RUNTIME_UI |
| `test_history_export_action.py`, `test_native_export.py`, `test_owned_export.py` | Export allocation, shared lease, child ownership and prepared widget action; README_NATIVE_EXPORT, README_OWNED_EXPORT, README_HISTORY_EXPORT_CHECK |
| `test_hostops_hour_binding.py`, `test_qualification_dispatch.py` | Exact completed-unit binding and prepared dispatch budgets; README_QUALIFICATION_DISPATCH, README_HOST_OPERATIONS_V3 |
| `test_late_labels.py`, `test_sparse_embedding.py` | Provisional-label timing and bounded sparse scheduler; README_LATE_LABELS, README_SPARSE_EMBEDDING |
| `test_native_benchmark.py`, `test_native_variant.py`, `test_native_selection.py`, `test_review_fixes.py` | Benchmark planning, reviewed native variant and selected source contracts; README_NATIVE_BENCHMARK, README_NATIVE_VARIANT |
| `test_native_storage_check.py`, `test_saved_replay.py`, `test_source_batch.py` | Prepared native fixture action, segmented saved input and exact source batching; README_NATIVE_STORAGE_CHECK, README_SAVED_REPLAY, README_SOURCE_BATCH |
| `test_optional_qualification.py`, `test_optional_refiner.py` | Optional permit/allocation/resource/protocol and fake-child lifecycle; README_OPTIONAL_QUALIFICATION, README_OPTIONAL_REFINER |
| `test_production_scope.py`, `test_production_scope_v2.py`, `test_production_scope_v3.py` | Versioned read-only census scope contracts; README_CURRENT_BACKUP_SCOPE and its selected version |
| `test_xvf_recovery.py`, `test_xvf_recovery_v2.py` | Prepared recovery sequence eligibility and bounded receipt contracts; README_XVF_RECOVERY and its selected version |

Save the following wrapper as a private `registered_host_test.py`. Set `PRIVATE` to the actual private `live-runtime-20261003` evidence directory before running. It pins CPU14 and persists the actual numeric process identity before any project import. The invocation supplies one explicit unittest target, for example `test_owned_export.ExportTests.test_real_read_only_export_shared_lease_blocks_deletion`. The wrapper is documentation, not a request to execute a test now.

```python
import ctypes, json, os, sys, unittest, uuid
from pathlib import Path
k = ctypes.WinDLL('kernel32', use_last_error=True)
k.GetCurrentProcess.restype = ctypes.c_void_p
h = k.GetCurrentProcess()
k.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
if not k.SetProcessAffinityMask(h, 16384):
    raise ctypes.WinError(ctypes.get_last_error())
t = [ctypes.c_ulonglong() for _ in range(4)]
k.GetProcessTimes.argtypes = [ctypes.c_void_p] + [ctypes.POINTER(ctypes.c_ulonglong)] * 4
if not k.GetProcessTimes(h, *(ctypes.byref(v) for v in t)):
    raise ctypes.WinError(ctypes.get_last_error())
PRIVATE = Path('G:/PRIVATE/live-runtime-20261003')  # replace with actual private root
out = PRIVATE / 'audit-preparation' / ('focused-host-' + uuid.uuid4().hex)
out.mkdir(parents=True, exist_ok=False)
with (out / 'REGISTERED_OWNER.json').open('x') as f:
    json.dump(dict(schema='just-peachy.host-registered-owner.v1', pid=os.getpid(),
        cpu=14, affinity_mask=16384, creation_filetime=t[0].value,
        create_time=(t[0].value-116444736000000000)/10000000), f)
    f.flush(); os.fsync(f.fileno())
source, target = sys.argv[1:]
if not target.startswith('test_') or '/' in target or '\\' in target:
    raise ValueError('One reviewed unittest target required')
sys.dont_write_bytecode = True
sys.path.insert(0, source)
os.environ['JP_BENCH_TEST_ROOT'] = str(out)
suite = unittest.defaultTestLoader.loadTestsFromName(target)
with (out / 'TESTS.log').open('x') as stream:
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    stream.flush(); os.fsync(stream.fileno())
with (out / 'RESULT.json').open('x') as f:
    json.dump(dict(target=target, tests=result.testsRun, passed=result.wasSuccessful(),
        failures=len(result.failures), errors=len(result.errors), native_executed=False), f)
    f.flush(); os.fsync(f.fileno())
raise SystemExit(0 if result.wasSuccessful() else 1)
```

PowerShell:

```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B 'G:/PRIVATE/registered_host_test.py' $N test_owned_export.ExportTests.test_real_read_only_export_shared_lease_blocks_deletion
```

CMD or Anaconda Prompt (use the explicit qualified interpreter, not a different environment):

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "G:\PRIVATE\registered_host_test.py" "%N%" test_owned_export.ExportTests.test_real_read_only_export_shared_lease_blocks_deletion
```

Use the test's own documented direct-run bootstrap when its README explicitly requires it, such as `test_audio_journal.py`; the generic wrapper does not override a stronger module-specific ownership/fixture contract.
