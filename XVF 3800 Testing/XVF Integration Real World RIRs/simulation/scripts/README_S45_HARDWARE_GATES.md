# S4.5 hardware attempt and restoration gates

These changes strengthen the existing finite single-owner capture tool. The packed waveform, converter, XVF recipe, endpoints, capture callback and telemetry policy are unchanged. `s45_hardware.py` remains the sole hardware owner during a batch; `s45_campaign.py` sequences the run. The completed tagged transport regression and its original code snapshot remain intact.

Every new batch takes the existing hardware lease, then verifies all prior batches known from `initial_state.json`, `owner_acquired.json` or the global physical ledger. Each acquired/charged batch must have an exact restoration receipt, matching its original settings/identity/observe-only readback, with packed input disabled and audio/telemetry/lease handles closed. A missing receipt, unresolved STARTED ledger row, altered failure recovery binding or bare PASS with incorrect readback blocks further hardware. A recovery may be used only when cryptographically bound to its preserved original failure. An unacquired NOT_NEEDED receipt is harmless only if no acquisition/initial/ledger evidence exists.

Per-scene attempt counts are checked across all batches while holding the lease. A prior PASS prevents a new physical replay; two previous attempts prevent a third. Case receipts and charged ledger attempts both count. A compatible completed request in its original batch is reused without opening hardware. An acquired/closed batch cannot be reopened for new pending cases: use a distinct batch name so initial state, restoration and failure history stay intact. Explicit diagnostic tagged regression uses its separate historical identity; every actual pass, including diagnostics/references/failures, remains charged against the global 320-pass and 16,200-second limits.

An exception after a physical STARTED row closes only that batch/case's row as FAIL, records the exception and available captured-frame count, and keeps the full conservative playback charge. Cleanup continues despite progress-write failure. If a telemetry owner cannot be confirmed closed, restoration commands remain withheld and the receipt fails. No competing hardware owner is launched to force cleanup.

## Manifest routing and inputs

- Canonical IDs use the active `scene_bank/s45_v2_20260909T031300Z/SCENE_MANIFEST.json`. Superseded v1 inputs remain preserved and are not a capture source.
- A batch containing only `S45_REF_*` IDs uses `REFERENCE_SCENE_MANIFEST.json`. These optional development naming-reference inputs stay outside the 240 canonical scenes and never become ordinary H2 sentinels merely because they were captured.
- Mixed canonical/reference batches are rejected. The historical `transport_regression` diagnostic must run alone.
- The established speaker-safety, transport-regression, frozen output/initialization policies, fixed hardware recipe, deadline and SSD gates still apply. No PC default audio device is changed.

## Model-free verification commands

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\anaconda3\python.exe' "$sim\scripts\test_s45_hardware_gates.py"
```

Anaconda Prompt or Command Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\anaconda3\python.exe" test_s45_hardware_gates.py
```

The test extracts the actual pure gate functions using Python AST and runs them on temporary JSON fixtures. It does not import/open hardware APIs or execute models. It covers separate manifest routing, duplicate/mixed rejection, two-attempt limits, accepted reuse, missing restoration detection, exact readback/close flags, bound recovery, orphan STARTED records, exception charge preservation and global budgets.

## Coordinator-controlled capture commands

Only the coordinator should launch hardware after the existing release/safety checks. In PowerShell, use the established recorder environment:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$py = 'C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py "$sim\scripts\s45_hardware.py" --help
# Example of a unique canonical batch, when not already captured:
& $py "$sim\scripts\s45_hardware.py" --batch canonical_unique_name --cases S45_01_01 --recipe limiter_and_agc_headroom --final
# Optional references use a separate unique batch and only reference IDs:
& $py "$sim\scripts\s45_hardware.py" --batch reference_unique_name --cases S45_REF_01 --recipe limiter_and_agc_headroom --final
```

Equivalent Anaconda/Command Prompt example:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" s45_hardware.py --help
REM Coordinator only, for a not-yet-accepted case and a new batch name:
"C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" s45_hardware.py --batch canonical_unique_name --cases S45_01_01 --recipe limiter_and_agc_headroom --final
```

Outputs remain under `G:/Just_Peachy_S4_5/20260909T031300Z/hardware/<batch>`: source snapshots, owner acquisition/initial state, case capture/configuration/telemetry files and exact restoration. Global progress and charged ledger remain in `reports/S4_5/20260909T031300Z`. The pre-review source, diff and model-free test receipt are under `staging/s45_hardware_review/v1`. No hardware capture is executed by the model-free verification command.
