# S7 projection copy reduction

Purpose: remove two discarded initial deepcopy operations from the exact installed S7 project method. In supported_prefix_v2 and timestamped_spans_v3, the original method copies the complete segments list and accepted_identity_snapshot into the initial result, then replaces both values with separate final copies. This helper substitutes temporary None values at those two keys, retaining their insertion order. The existing final segment and snapshot copies, visibility/mode policy, source clocks, labels, columns, lock, and every other method AST node remain unchanged. Conservative ownership retains its original initial copies.

Current status: the registered 19 focused HOST fixtures passed (15 S7 cases plus four status cases), with zero skipped/failures/errors, unchanged sources and closed fixtures. Exact CPU14 owner PID70516/creation FILETIME134357967152061657 returned naturally0 and was independently absent before the slot was released. Native integration/throughput and sustained operation remain unqualified. This is a proven redundant-copy removal in source, not a measured root cause of hour06's backlog failure. No immutable vendor/build33 file or frozen ASR cache is edited by this folder.

Closed evidence is the private s7-projection-copy-host-8e7001cfab2e41398b141ba6e22ee50b output under the existing local audit-preparation root. RESULT SHA d6492c0804ccb005c1ed6ed2e062e598179b25f790d24805c475ac63d339e664 and independent HOST_CLOSED SHA8e3afb8970c9de95c09689b37473ae9459fc86ea3409e120a4911ccb92f9e36d agree on that owner. SOURCE_CLOSED and SOURCE_UNCHANGED cover 19 admitted inputs plus independent backup/restore readbacks. The actual checks made 186 valid mode comparisons and 40 successive revisions. Direct deepcopy calls for a canonical segments list changed1→0 and accepted snapshot2→1 in the two supported modes; final per-segment copies and conservative-mode counts were unchanged. These are operation-count/output observations, not a native timing benchmark.

Runtime/check/runner bytes are frozen after that run: helper dcc6716da3992f511895f06cdff365a6712f36ca2a0caa3cd04b328cc645a795; frontend07cd9585cbd7ba27c72fe4d6617b434c0d0d2a2c330fbee60749a975eb5d944e; checks753aa479d670a2dcd699972769a95d3a95777616065e18612138235d14905f98; runner43bf398db65b23b74d06063a93f8e01a1121617f8bd75e0c8a52900cb69e1736. This README alone receives the present evidence update. Its tested original32367e45ab6e21ddc808a357fe3f23b702ce509b0204a8793aa898a47fe85d76 remains independently preserved/restored under preserved/README_S7_PROJECTION_COPY.host19.md. Packaging must pin the current documentation separately without pretending it was the pre-test README byte sequence.

The separate classic_frontend.py candidate displays actual text and speaker cursor delay while listening/replaying. Missing/nonfinite/negative/boolean values stay unavailable; they do not become zero. Positive delay is labelled analysis behind. Advanced diagnostics explicitly say real-time unqualified. This changes the RUNNING notice and adds numeric diagnostic fields; it adds no controls and preserves STARTING, STOPPING, error, playback, tabs, layout and capture semantics.

## Inputs and outputs

- Runtime input: the already admitted S7PresentationState class, its original vendor source path, and exact SHA a6229a1cc1f967012de2b79780ab92029e63dc3a64e52bf56b563d7e44f18f10. The class/source originate from original installed release manifest 274e6de279264f89642e3857c64bf164c699b600cd99e922429020b548bf55f0. Vendor source bytes and that manifest agree. Original project region is lines 377–418.
- bind_project returns a derived callable and method provenance. It admits one exact class/method origin, source hash and AST region. Reversing its one assignment substitution must restore the entire original method AST.
- install_project attaches that callable to one exact S7 instance under its existing RLock. It preserves other instances and the vendor class. Repeating the same install is idempotent; another instance override or changed class method is rejected.
- The contract covers canonical plain JSON-compatible presentation rows produced by the admitted runtime. It does not claim to preserve side effects from custom Python objects with user-defined deepcopy methods. Optional/missing keys, unknown identity, malformed ordinary segment shapes, output key order, source values and detached nested histories are checked.
- Host input: one fresh private output directory plus the helper, frontend candidate, fixtures, runner, README, original installed pure S7 dependencies, build33 integration references, preserved source/restores, and the actual merged disk_capacity_policy_20261006/installed_engine.py at f6c5ebd4dfa725baa738aa70d36d86bf7937d7030080ce61f25dee5f83fba25a. Host output: registered owner/scope, source backup/independent restore pins, focused RESULT, TEST_OUTPUT, SOURCE_UNCHANGED and HOST_EXIT. HOST_EXIT does not certify process absence; the supervising PowerShell shell must independently check owner closure.
- No audio, person/vector data, models, native worker, network, database or GUI is loaded by the focused fixture. Only the actual pure pinned S6D/S7 classes are imported. Model imports are rejected.

The private preserved original and independent restore are research_s7_presentation.installed.py and its .restore twin. They have the same original vendor SHA above. classic_frontend.build33.py and its restore preserve the unchanged original frontend SHA 0e8b0db1b9e227a7a5a9dea61b298d7d28984aad8c2a5dd299a5d1024aa59aaf. Neither preserved pair is a replacement source or publication input.

## Production integration for the root-owned installed_engine candidate

runtime_support itself has no AST/module binding facility. installed_engine.load_reference already verifies the installed release and reference sources; d1_caption_snapshot provides the existing hash-bound AST derivation pattern. Bind once adjacent to its current N2 binding, after load_reference admission:

```python
from edge_speech_pipeline.research_s7_presentation import S7PresentationState
from s7_projection_copy import bind_project, install_project
s7_project = bind_project(S7PresentationState,
    base/'vendor/edge_speech_pipeline/research_s7_presentation.py',
    manifest['vendor/edge_speech_pipeline/research_s7_presentation.py']['sha256'])
```

Within the existing Engine facade add the following override, retaining all existing Engine methods:

```python
def _begin_session(engine, mode):
    super()._begin_session(mode)
    if type(engine._s6d_presentation) is S7PresentationState:
        engine.s7_projection_copy_receipt = install_project(
            engine._s6d_presentation, s7_project)
```

The original field_native_binding _begin_session wrapper remains in the super chain. Original runtime.py287–383 constructs S7 at333–336 and emits configuration events; those event kinds do not project caption rows. PrototypeEngine.begin calls _begin_session at pipeline.py322 before continued policy setup/worker launch. Thus the instance hook is installed before first caption processing, with no global vendor-class replacement. Non-S7 presentation uses the original path. The actual merged Engine at the pin above contains this exact override. A focused fixture compiles only that source method/class shell and exercises it with actual pinned S7 instances, preserving inherited setup and the non-S7 branch without importing the native graph. This does not claim deployment or a full Engine/native lifecycle test.

## Focused checks and commands

The 15 S7 cases compare every valid M0–M7 × three ownership modes × T0/T1/T2 selection/all-enrolled/full-view branch using actual pinned classes. They also cover optional/missing/unattributed rows, exact serialized key order, nested history/token/snapshot mutation isolation, public aliases/per-segment copy independence, stateful two-column assignment, exact direct copy counts, lock ownership, malformed ordinary segments, one-assignment AST reverse proof/drift rejection, SHA/origin/class drift, isolated/idempotent instance installation, the actual merged Engine override, and 40 successive synthetic revisions. Four status cases cover live/saved measured delay, ever-growing numeric delay, unavailable invalid values, explicit unqualified diagnostic scope, and exact AST reversal to the unchanged original frontend outside the two helper definitions, one RUNNING notice assignment and one diagnostic field. No fixture text is a recording transcript.

Run only when root assigns the CPU14 host slot. The runner registers PID plus creation FILETIME/CPU affinity before project imports, checks C:50GiB and G:75GiB actual free-space floors, admits source files before bounded reads, and reserves a finite 16MiB/300s receipt scope. These limits apply to this diagnostic utility, not product recording/gallery counts.

PowerShell (uses the existing approved interpreter; no environment installation):

```powershell
$source = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006/s7_projection_copy_20261006'
$evidence = 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/s7-projection-copy-host-' + [guid]::NewGuid().ToString('N')
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' "$source/run_host_s7_projection_copy.py" --output $evidence
$naturalExit = $LASTEXITCODE
$owner = Get-Content -LiteralPath "$evidence/REGISTERED_OWNER.json" -Raw | ConvertFrom-Json
$stillRunning = Get-Process -Id $owner.pid -ErrorAction SilentlyContinue
if ($stillRunning) { throw 'Registered PID is still present; do not certify closure or reuse the slot' }
if ($naturalExit -ne 0) { throw 'Focused fixture failed; preserve all output before repair' }
$closed = @{owner=$owner; natural_exit_code=$naturalExit; os_process_absent=$true}
$closed | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath "$evidence/HOST_CLOSED.json" -Encoding utf8NoBOM
Get-Content -LiteralPath "$evidence/RESULT.json" -Raw
```

If a PID has been reused, verify its new creation time differs from the registered FILETIME before declaring the exact old owner absent; the simple command above rejects any still-present PID conservatively. Never synthesize successful closure while the exact registered owner remains alive.

CMD (replace FRESH_UUID with a fresh 32-character lowercase hexadecimal UUID; coordinate the same host slot first):

```bat
set SOURCE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\core_repair_20261006\s7_projection_copy_20261006
set EVIDENCE=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\audit-preparation\s7-projection-copy-host-FRESH_UUID
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%SOURCE%\run_host_s7_projection_copy.py" --output "%EVIDENCE%"
```

Anaconda Prompt: use those same CMD commands and the explicit approved interpreter. Activating/installing another environment is unnecessary. After CMD/Anaconda execution, use PowerShell to independently verify the registered owner and write HOST_CLOSED as above. Preserve failed output and its source pins; use a new label for any authorized rerun.

Acceptance is 19 tests, zero skipped/failures/errors, source unchanged, exact fixture closure, and independent exact owner absence. Byte/output equivalence and eliminated direct copies establish the focused change only. They do not establish native ASR/speaker latency, microphone quality, biometric accuracy or an hour pass.
