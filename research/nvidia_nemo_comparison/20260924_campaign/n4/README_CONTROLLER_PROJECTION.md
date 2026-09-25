# Actual Controller display-event consumption and label projection

Purpose: execute the unchanged application's Controller initialization, backend
selection, mode switch, real caption-consumer thread and `snapshot()` projection
with the already sealed N4 modeled display events. This closes the downstream
consumer/projection test gap. It does not run upstream source/model/publication
code, Tk, source pacing or complete Controller inference parity.

Inputs: a complete verified component_mode_replay result; explicit tap from its
verified audio-only parent; the bound fixed GALLERIES.json; existing N2/N3 runtime
metadata bindings; a fresh isolated private data directory. The real constructor
receives saved_audio_only=True and an empty NO_MODEL_PAYLOAD model root. A
read-only E-roster view supplies names/IDs; it never writes personal profiles.
The application's actual engine constructor admits the correct gallery. No
engine Start runs. The upstream completion marker represents sealed replay
input, not a completed neural session. Model/enrollment acquisition and ONNX
construction must be forbidden with `forbid_inference()` for every call.

`ObservedDrainQueue` preserves ordinary get/empty behavior and records a snapshot
only when the real Controller asks for its next event, after finishing the last
one. Every modeled display is consumed once by the actual caption-consumer
thread. The actual consumer writes its normal closure receipt and the normal
Controller close path releases its thread and application lock. Epoch handling,
raw-row storage, final text-assistance hook (disabled) and label projection are
unchanged. All primary caption fragments must remain visible, reconstruct exact
raw text, and preserve every bound upstream field. Per-display snapshots retain
real projected labels, assumption flags, revision/span IDs and final formatting.

Outputs: private per-display projected rows and final raw/projected Controller
rows, real consumer closure binding, exact event census and cleanup/model-load
checks. Source timestamps remain the parent's modeled values. Host consumer
timestamps only measure this replay's execution and cannot supply actual caption
latency or first-visible metrics. No global clock or source file is patched.
Integrated acceptance stays zero. Actual upstream publication and coupled
Controller inference parity, GUI delivery, global activity, full-bank scoring
and resource checks remain separate requirements.

Bounds: at most 100,000 input displays, 512 retained application rows, 24 MiB
serialized history per projected cell, 32 MiB total expanded artifact in the
production probe, finite consumer/command joins. Failures are explicit. The
caller verifies all source/result/expanded gzip bytes before using this API.
Detailed transcript/roster/evidence files stay private and must not enter Git.

`test_controller_projection.py` uses sealed development replays and existing
research E gallery metadata (no model, microphone, playback, human enrollment
or desktop). It exercises baseline/N2 assumptions, constant/numbered label
projection, raw/final text preservation, altered inputs, queue acknowledgements
and real thread/owner closure. Tests create only isolated temporary data roots.

The selected-focus test documents an existing product discrepancy: snapshot()
uses anonymous numbered fallback in this mode, although MODE_METADATA describes
one constant Unknown. Do not replace actual projected labels with the mode
description when scoring. This is evidence of existing behavior, not a fix or
acceptance of the described product semantics.

`probe_controller_projection.py` derives all 160 complete parents from
COMPONENT_MODES_CHECK_V1.json and its bound private receipt. It rechecks every
source file, parent code/result/full gzip, exact source tap and gallery/runtime
binding, then consumes all displays through separate actual Controller owners.
Outputs include actual closure receipts, projected rows and cleanup/model counts,
private controllers/ roots, verified gzip files and RESULT.json or FAILED.json.
The 512-MiB run cap, C50/G75-GiB floors and packaging cutoff are checked per cell.
The shared inventory plus 6 GiB conservative ASR/D1/contingency/helper reserves
must remain below the admitted limit (at most 50 GiB). CPU14 below normal and
single-thread math leave the CPU4 model unchanged. No shared ledger mutation,
hardware enumeration, visible window or personal-data access occurs.

PowerShell tests from the campaign worktree:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
& $jpPython -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_controller_projection.py','-v']; runpy.run_module('unittest',run_name='__main__')" $jpCode
& $jpPython -B "$jpCode\probe_controller_projection.py" --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\controller-projection-v1'
```

Command Prompt / Anaconda Prompt (existing interpreter, no installation):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
"%JP_PY%" -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_controller_projection.py','-v']; runpy.run_module('unittest',run_name='__main__')" "%JP_CODE%"
"%JP_PY%" -B "%JP_CODE%\probe_controller_projection.py" --output "G:\Just_Peachy_N1\20260924_campaign\local\n4\controller-projection-v1"
```

Tests default to local/n4; set JP_N4_LOCAL only for an equivalent verified private
evidence root. Production probes must use passed receipts, not arbitrary fixture
JSON. A successful consumer projection is not a full pipeline parity claim.
