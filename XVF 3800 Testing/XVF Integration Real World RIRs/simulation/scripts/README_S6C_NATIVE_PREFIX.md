# Actual S6C paired native prefix proof

`s6c_native_prefix.py` runs two actual fixed-weight native sessions with the same
12-second paired audio prefix and different future samples. It uses one resident
Pyannote/ReDim/Sherpa bundle with fresh session/decoder/tracker state. The exact
registered N01 C085 O0-ASR/O1-identity profile has cues and naming disabled. No
audio hardware, private gallery, reference transcript or participant truth is
given to the runtime. This is a small causality check, not accuracy estimation.

Inputs are the frozen `EPOCH1_EXECUTION_MANIFEST.json`, its exact code/runtime/
asset bindings, C085 profile and canonical S6B INPUT_INDEX prepared audio. The
default whole S45_01_01 clip is retained: after second 12 only, each tap's suffix
is reversed and negated. No new gain is applied. Shared prefix float32 and native
PCM16 hashes are recorded. Changed FLOAT WAVs and explicit prefix PCM files live
under `G:\Just_Peachy_S6C\20260910T123540Z\native_prefix\v3`.

Outputs are `reports/S6C/20260910T123540Z/native_prefix/v3`: immutable MANIFEST,
STARTED process identity/resource receipt, original and changed NATIVE_RECEIPT,
COMMON_AVAILABILITY_REPLAY and RESULT (or preserved FAILURE), plus a replaceable
20-second heartbeat. Full native events, summaries, complete paired PCM journals
and `session_finalization_v3.json` remain in the G: session directory. A result
does not claim its still-running driver PID has exited; the caller records that
after process completion. Failed namespaces are preserved and are never resumed
or retried automatically.

Run from PowerShell, only after the parent admits the epoch and reserves a model
worker. Preparation does not load models. `run` validates code, versions, exact
inputs and assets before constructing the one bundle. Do not edit the script,
README or common helper between prepare and run; their hashes are admitted.

```powershell
$s6cScripts = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
$s6cPython = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
Set-Location -LiteralPath $s6cScripts
& $s6cPython s6c_native_prefix.py --mode check
& $s6cPython s6c_native_prefix.py --mode prepare --epoch epoch1 --version v3 --candidate C085 --case S45_01_01 --prefix-sec 12
& $s6cPython s6c_native_prefix.py --mode run --version v3
```

Equivalent Anaconda Prompt / CMD (explicit EDGE interpreter; no environment
installation or activation change required):

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
set PYTHONDONTWRITEBYTECODE=1
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" s6c_native_prefix.py --mode check
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" s6c_native_prefix.py --mode prepare --epoch epoch1 --version v3 --candidate C085 --case S45_01_01 --prefix-sec 12
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" s6c_native_prefix.py --mode run --version v3
```

All inner numeric pools are fixed to one before imports. Native closure must be
COMPLETED with no live lanes, retained lease or unclosed writers; both journals
must equal the expected full PCM and shared prefix; ASR must reach exact EOF.
The initial bundle constructor includes real model load, separately measured
from each native run. These are accelerated file runs, not paced desktop or CM5
latency measurements.

The comparison keeps evidence supports and identities, checks duplicate spans
and IDs, rejects nonfinite numerics, compares segmentation frames and actual
short/mature vectors at tolerance 1e-6, and compares raw ASR words/flags exactly.
Only observations whose source and receptive ends are at or before the cut are
included. Native cross-thread file order, measured compute durations/readiness
and native label histories are separate. Native labels are explicitly reported
even when timing differences make them differ.

After matching real observations, the same frozen incremental scheduler is fed
both prefixes using the maximum observed readiness for each matching event ID.
Future observations are held after that common checkpoint and then submitted;
the actual returned prefix record dictionaries (retained by reference) must stay immutable. Prefix decisions
and exports are compared independently of measured policy compute cost. This
declared common-availability replay checks forward-only behavior on actual
neural observations. It does not prove identical native latency, turn-level
accuracy, every profile's causality, or that future revisions cannot update the
latest view within its documented horizon.

Source/receptive spans, IDs and other observation fields compare exactly; only vector/frame numeric output arrays use 1e-6 tolerance. Every lane must have nonempty prefix evidence, with both short and mature roles. Common replay records/utterance snapshots compare exactly after removing separately measured costs.

The v1/v2 input-only preparations are retained without native invocation. Its comparison helper was corrected after independent review before execution; v3 is the separately admitted plan; it also retains exact segmentation receptive spans and left padding. No native outcome drove this change.
