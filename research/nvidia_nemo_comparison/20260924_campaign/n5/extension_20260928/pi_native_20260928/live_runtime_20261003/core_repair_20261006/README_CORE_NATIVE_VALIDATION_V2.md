# Focused core native validation v2

This version repairs the validation utility's package dependency loading. The first actual build29/live34 launch failed at `guard.load_pure(package, 'storage')` with `ModuleNotFoundError: storage_support`: the retained pure wrapper loads a file under an alias and does not insert its inventoried package into `sys.path`. That failure occurred before a native output directory, service, GUI or capture was created. Its exact utility PID38088/start811703 is closed; preserved dispatch evidence is `Q/operation-core-live34-launch-01/dispatch`. No successful native qualification is claimed from that attempt.

## Purpose and narrow change

`native_core_live_check_v2.py` and `native_core_saved_check_v2.py` are injected test helpers, outside the frozen runtime. Immediately after the unchanged `guard.inventory` validates the entire package, their launch functions call `bind_verified_package(package, manifest)` before loading the pure profiles/storage modules. That function inserts only the canonical, fully inventoried package at `sys.path[0]`, disables bytecode writes, refuses already-loaded project modules from other roots, verifies ordinary source loaders and each root Python file's canonical single-link/hash origin, and returns a checker for the actual loaded project graph. The checker runs after the pure imports and after Saved's lazy worker allocator. This makes `storage_support` reachable and binds it to the admitted package.

The helpers otherwise retain the original actual Tk driver, ownership/baseline guards, physical storage/FSIZE plan, finite70-second session policy, Stop/drain, explicit new-session Discard, chooser relaunch, Saved source lease/readback, service budget and independent native finalize logic. The package, runtime, original helper sources, galleries, calibration and existing recordings are not edited. The preparer v2 changes only helper names/SHA pins and its README reference.

| Versioned source | SHA256 |
| --- | --- |
| `native_core_live_check_v2.py` | `5c6eab13e00076aabf3f022f69410e1f330dc16a4cbad69b49b8fe016109e37e` |
| `native_core_saved_check_v2.py` | `01fc4288e8496a99eb318875e1aaebac51af8b2fca80b232798693d93cc27237` |
| `prepare_core_native_validation_v2.py` | `9ce35c03be3fad1f2fa53088e63f5af5613fe51735bcd33c66a95b3b55b9c42b` |

Immutable originals remain: live SHA`e10e1995aea7de52e4986348fb35817a4ecf1a63eab660a986646b2e660557e5`, saved SHA`5a438704d33e0c5d41965930b30153d0a6da1942ae1ab89100fe98c6b53eb9ae`, and preparer SHA`8a704db2ee5e1a9f38b67698c9401b01c612cf22b5e0b710717eddaa39d5f3cc`. The retained lower-level qualification wrapper remains unchanged in the package.

## Inputs and outputs

`prepare_core_native_validation_v2.py` is a Windows CPU14 host CLI. Inputs are the actual private build29 package, exact manifest SHA, observed current boot UUID, kind `live` or `saved`, one of the six ordinary operator IDs, an unused `classic-ui-check-34` through99 label, and operation `launch` or `finalize`. Live requires `--discard-session`. Saved requires one captured kept `session.json` and its exact SHA; all Saved rows use that same source. `--discard-session` removes only the new validation output after owner/source/worker closure.

The six operator IDs are `pyannote_redimnet`, `pyannote_titanet`, `delayed_redimnet`, `delayed_titanet`, `chunk52_2t_redimnet`, and `chunk52_2t_titanet`. Parallel/provisional refinement remains excluded. Live Stop is12source seconds; complete Saved input must fit the existing70-second qualification. No participant, seat, calibration, supported identity or Mode readiness is fabricated.

Host outputs are a fresh registered owner, exact source backups/restores, `ACTION.py`, fresh `PAYLOAD.json`, pure selection/allocation receipts and `SOURCE_CLOSED.json` under `Q/audit-preparation/live-check-payload-<label>-<UUID>`. `Q` is `G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003`. The host never opens a model/source/GUI/SQLite store or dispatches SSH. Root separately admits and dispatches the exact action/payload. Native helpers consume injected `PAYLOAD`/`BASELINE` and return `RESULT`; do not run them directly on the PC.

Each native launch and finalize needs a fresh preparation; payloads expire after590seconds. Native launch rejects an existing output directory or service. Host preparation rejects a launch label with preserved native monitor evidence. The failed first34 attempt created neither output nor service, so root may reuse the still-unused native label34 with a new host operation02 and a fresh private preparation. Preserve the original failed dispatch.

The commands below record the now-consumed Live34 workflow. Do not rerun that label; use a fresh reviewed operation for any future row.

## PowerShell

Run only in the coordinator's assigned host slot after the previous exact host owner closes. Use the existing interpreter, not the WindowsApps alias. This example binds the actual frozen build29 package and currently observed boot:

```powershell
$repairDir = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006'
$packageDir = 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/core-package-v1-389154acb3e04317b614c4311bb6de02/package'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' "$repairDir/prepare_core_native_validation_v2.py" --package $packageDir --manifest-sha256 '331b85974c33957917f524d0796d53df78f6154be557b10ecea55524d130939b' --boot-id 'e60e67c2-f3f5-4b8b-8eab-2613df2de37e' --kind live --operator-id pyannote_redimnet --label classic-ui-check-34 --discard-session
```

Review output/source pins and independently confirm the registered PID/creation FILETIME is absent after natural exit before releasing the host slot. Root must then separately review fresh native processes/leases, full accepted backup, staged package, capacity and the exact unused native label. After actual worker/main/unit closure, repeat the same preparation command with `--operation finalize`; the finalize helper publishes PASS only after independent native closure. No old measurements are relabeled.

For Saved, substitute `--kind saved`, the intended operator ID and a proven-unused label, and add `--saved-metadata-file 'ACTUAL_CAPTURED_KEPT_SESSION.json' --saved-metadata-sha256 ACTUAL_SAVED_SHA --discard-session`. Root's captured candidate is session`c24b685b2bd34d6bb04172965d712c0f`,966400processed samples/60.4seconds; its2581-byte metadata SHA is `7da45b76193d3ddd1e2aa29bbc6792b019643c8a945edd3959d9458db4fc6c69`. Use the actual captured file location rather than inventing a path. Finalize each row before starting another.

## CMD and Anaconda Prompt

The existing environment works in CMD or Anaconda Prompt without installing or activating another environment:

```bat
set "JP_REPAIR_DIR=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\core_repair_20261006"
set "JP_PACKAGE_DIR=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\audit-preparation\core-package-v1-389154acb3e04317b614c4311bb6de02\package"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%JP_REPAIR_DIR%\prepare_core_native_validation_v2.py" --package "%JP_PACKAGE_DIR%" --manifest-sha256 331b85974c33957917f524d0796d53df78f6154be557b10ecea55524d130939b --boot-id e60e67c2-f3f5-4b8b-8eab-2613df2de37e --kind live --operator-id pyannote_redimnet --label classic-ui-check-34 --discard-session
```

Use the same future Saved/finalize argument substitutions described above. These are sequential examples, never a concurrent batch.

## Retained guards and status

Host preparation retains2MiB/600seconds and50GiB/C plus75GiB/G free-space floors. Native trial output and independent PC mirror reservations remain256MiB; actual per-file FSIZE follows filesystem capacity minus the5GiB physical reserve. Ownership, bounded queues, transactions, working sets and short test timing remain. The SQLite/cumulative text-writer logical corpus caps removed in build29 are not reintroduced.

## Actual Live34 v2 result - bounded finalized PASS

After the preserved attempt01 dependency-loading failure, the corrected
inventoried-package binding produced the actual Live34 functional trial.
Q/classic-ui-check-34-monitor-01/closed-output/COMPLETE.json SHA256 is
8fc9bcecaad317301fa65d7802ace7469056473484498b05bc4b5b6836b3cbe8.
The independent finalizer is Q/operation-core-live34-finalize-01/dispatch/RESULT.json,
SHA256ba0ef542e1541cfc3e5105d24599a1123147fe91f1f17029b05342902ca2ddb5.
Its exact manifest/current-boot proof is PASS: workers closed, main exact owner
gone, recursive unit empty and independent finalize true. Utility 39940/start869136
was independently absent. Finalized full mirror
Q/classic-ui-check-34-finalized-monitor-01 is pending completion.

Actual portrait Pyannote/ReDimNet captured 196,799 processed samples/ 12.2999375 s,
with source closure and restored route. Normal SessionStore recovered the native
35,889,152-byte database/41,552-byte journal to 36,171,776 bytes/no journal,
quick_check ok/new projection columns, without manually clearing a journal.
Explicit UI Discard purged selected content from nine tables; directory absent,
audio/caption retention false. Chooser and app actually reopened idle, current
caption rows 0. Eleven Mode controls were observed: five selected intents,
four participant prerequisites and two seat prerequisites.

One indexed/nonempty caption row and ASR accept 123/ finish 1/ reset 4 were recorded;
speaker embedding/name accuracy is not qualified. No physical touch, 300 s,
production GUI lifetime, sustained real time or acoustic BPE/PnC quality follows.
Six matched Saved rows and independent calibration/evaluation remain pending.
Build29 is staged only and not activated. Activation must use this actual proof
and completed independent mirror plus current guards, never the old build28 proof.

Do not rerun consumed Live34 launch/finalize labels or the historical commands
above. Future rows require new preparations/fresh labels and exact same kept
source admission. The v2 fix is only in validation helpers outside the frozen
runtime; source/package/galleries/calibration remain unchanged. Historical
failed utility 38088/start811703 closed before any native output/service/capture.