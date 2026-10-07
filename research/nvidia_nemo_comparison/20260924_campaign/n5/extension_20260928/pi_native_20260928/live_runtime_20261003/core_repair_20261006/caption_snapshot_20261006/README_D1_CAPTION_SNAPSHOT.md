# Focused D1 caption snapshot candidate — 2026-10-06

## Purpose and current scope

This source candidate reduces caption identity work in the existing D1 path. It
does not introduce a backend, model, speaker decision, calibration or word
alignment. Immutable build30 remains preserved. No new native throughput or
hour pass is claimed. Registered host fixtures passed 11 with zero errors, failures or skips.

Closed build30 hour01 failed its configured backlog gate after 312 processed
source seconds. Independent numeric analysis identifies the speaker lane:
310.1 seconds of published source minus 190.0799957514 analyzed seconds gives
120.0200042486 seconds of lag. Nearby ASR publication lag was 11.3 seconds.
This identifies the failed lane; it does not isolate every contributing cost.

The pinned N2 method copied every active presentation row before filtering for
one requested parent. Those rows include text, duplicate segments and speaker
histories. Native hour01 retained 16 parents; full ASR dispatch increased from
17.45 seconds in its first source minute to 40.52 in source minute four, while
native decode changed from 9.31 to 11.49 seconds. This is consistent with added
publication/revision work, not an exclusive causal attribution. The maximum
cached display payload was 299,531 bytes. Presentation remains capped at 512
parents, and per-word speaker history at 32 entries; there is no claim of an
unlimited native transcript in RAM.

The old signature cache keyed `(span_id,text_revision_id)` but retained obsolete
revisions whenever the span ID remained active. Stable prefixes preserve span
IDs. Its 16,384 threshold could repeatedly trigger cleanup without removing
those obsolete revisions. Actual hour cache length was not recorded. The
candidate retains only exact current `(span_id,text_revision_id)` pairs when
the existing threshold is crossed, preserving current expired-evidence labels.

PnC is separate: hour01 recorded one spoken boundary at Stop/source 312, one
punctuation worker job, ten bounded windows and 371.6 ms of model punctuation.
That post-stop job cannot explain the earlier backlog gate. ASR-ledger reads
remain exact-parent reads, and punctuation writes remain window transactions.

## Files, inputs and outputs

- `d1_caption_snapshot.py` provides `selected_identity_rows(presentation,
  utterance_id=None)`. It reads the existing canonical rows under the existing
  presentation lock. It returns detached, ordered dictionaries containing only
  existing `utterance_id`, `text_revision_id`, `source_start_sec`,
  `source_end_sec`, and each word span's existing `id`/source coordinates.
  Missing fields remain absent. Requested-parent reads do not project or copy
  unrelated rows. Global identity updates still inspect all active parents.
- `bind_revision(Parent, expected_source_path, expected_sha256)` returns a
  callable `(engine, utterance_id=None, blocking=True)` and is bound once at
  engine construction. It reads the already admitted N2 source, verifies its
  exact SHA256 and loaded method origin/AST, and derives only the approved
  snapshot and cleanup changes. It imports no native module or model.
- `installed_engine.py` and `d1_spatial_policy.py` in this folder are root-owned
  candidate integrations copied from preserved30 inputs. The engine binds the
  helper for D1, records revision call cost and reports the individual lane
  clocks. The spatial path uses the same minimal snapshot/current-pair cleanup.
- `check_d1_caption_snapshot.py` runs synthetic no-model checks against the
  actual pinned pure S7 presentation and a compiled copy of the original N2
  method. It compares emitted native revision payloads, selected identity
  values/order, repeated-prefix cleanup, placeholder/missing-parent behavior,
  source/AST drift rejection and the actual candidate engine wrapper.
- `run_host_snapshot_checks.py` registers its exact Windows owner and CPU14
  affinity before project imports, backs up/restores/readbacks source inputs,
  runs the fixtures, checks fixture closure and unchanged inputs, and writes
  bounded receipts. It starts no child, capture, GUI, model or network activity.

All source coordinates and span IDs remain exactly supplied by the pinned
runtime. `ASR_REVISION_WINDOW_NOT_PHONETIC_ALIGNMENT` is still coarse timing;
no word onset is fabricated. Labels, thresholds, calibration, embeddings,
event payloads and ordinary model/runtime capacity profiles are unchanged by
the derived method. Final native behavior still requires its own check.

## Exact derivation and integration

The admitted `app/n2_pipeline.py` SHA256 is
`6312c12f80b67183faf93b6ca83502b47f0e7bca62d124a170a58a6a51000491`.
The original `_revise_supported_spans` occupies lines 272–321. The loader checks
the whole source hash, class/method region and loaded origin before binding.

Only these AST regions change:

1. First `snapshot_rows()` iteration becomes the selected minimal identity row
   snapshot, before the native parent filter.
2. Cleanup `snapshot_rows()` becomes the global minimal snapshot; its retained
   set becomes current `(span_id,text_revision_id)` pairs.
3. Cleanup dictionary membership tests the full pair rather than its span ID.

Restoring those three regions must reproduce every other original AST node.
Exactly two snapshot calls must be substituted; shape/hash drift fails closed.
The resulting callable exposes `caption_snapshot_provenance` with its pin,
line region and narrow derivation assertions. Source bytes are never edited.

```python
from d1_caption_snapshot import bind_revision
revise = bind_revision(N2Engine, installed_release/'app/n2_pipeline.py',
                       manifest['app/n2_pipeline.py']['sha256'])
revise(engine, utterance_id, blocking)
```

This is a production integration API, not an application launch command. Use
only the root-reviewed package builder/launcher for deployment. Do not modify
the active release or replay consumed native operations from this directory.

## Host prerequisites and commands

Use the already installed Python 3.10+ interpreter. The checks require the
standard library only. No package or model installation is needed. The pinned
original release must already exist at the `SOURCE_ROOT` in the checker; only
its pure S7 modules and the N2 method AST are loaded. Inputs are the six local
candidate source/README files, preserved parent source files and four pinned
original method/presentation files. The root-owned integrations must exist
beside the helper before the registered runner is used.

A registered run requires a fresh nonexistent `--output` directory. Coordinate
the CPU14 host slot first; do not overlap another registered fixture on it.
Output is capped at 128 MiB and checks at 120 seconds. Source files/receipts are
at most 256 KiB, and test output at 64 KiB. Actual free-space floors are checked
for C: 50 GiB and G: 75 GiB. Those are host-test safeguards, not recording limits.

PowerShell:

```powershell
Set-Location -LiteralPath 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\core_repair_20261006\caption_snapshot_20261006'
$snapshotLabel = 'snapshot-host-' + [guid]::NewGuid().ToString('N')
$snapshotOutput = Join-Path 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\audit-preparation' $snapshotLabel
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' .\run_host_snapshot_checks.py --output $snapshotOutput
```

Windows Command Prompt:

```bat
cd /d "G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\core_repair_20261006\caption_snapshot_20261006"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" run_host_snapshot_checks.py --output "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\audit-preparation\snapshot-host-REPLACE-WITH-FRESH-LABEL"
```

Anaconda Prompt, using an existing Python 3.10+ environment:

```bat
conda activate base
cd /d "G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\core_repair_20261006\caption_snapshot_20261006"
python run_host_snapshot_checks.py --output "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\audit-preparation\snapshot-host-REPLACE-WITH-FRESH-LABEL"
```

Replace the output label with a new one each run. `python
check_d1_caption_snapshot.py` is an ordinary no-model development test command,
but does not create a registered acceptance receipt or prove process closure.

## Receipts and interpretation

The runner exits 0 on fixture PASS or 1 on failure. It writes
`REGISTERED_OWNER.json`, `HOST_SCOPE.json`, exact source backup/restore files,
`SOURCE_CLOSED.json`, `TEST_OUTPUT.txt`, `RESULT.json` and `HOST_EXIT.json`.
The result schema is `just-peachy.caption-snapshot-host-check.v1`; it contains
test counts, fixture closure, source readback status and no transcript content.

After natural return, independently read the typed owner PID/creation FILETIME
and verify that exact OS process is absent. Save a separate `HOST_CLOSED.json`
from that independent check. The runner's own exit receipt is not proof that
its process is gone. Source closure pins include all three replacement runtime
Python files, checker, runner, README and original pinned reference inputs.
Host PASS establishes this narrow no-model contract, not native latency,
sustained throughput, calibration, speech quality or an hour PASS.

## Executed host evidence

The single registered CPU14 run at
`Q/audit-preparation/caption-snapshot-host-b338043a6358469d86ace1a31bb53414`
passed 11 checks in 0.641 seconds. Python PID 38760 / creation
FILETIME 134357877265399478 naturally returned 0 and was independently absent.
`HOST_CLOSED.json` records that exact owner, natural return and OS absence.
All 12 source inputs were backed up, independently restored/read back and
unchanged through test closure. Synthetic fixtures were closed; no model,
GUI, capture, native action or network call ran.

The actual candidate engine wrapper and compiled pinned native method both
ran in the fixture. Exact native revision payloads/current cache results,
selected/global ordering and coordinates, repeated stable-prefix cleanup,
placeholder/missing parent behavior and source/AST drift rejection passed.
This does not qualify native throughput or change hour01's FAILED result.
This evidence paragraph was added after the process closed; runtime/helper,
checker and runner bytes remain those captured in the host source receipt.