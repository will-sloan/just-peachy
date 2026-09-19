# S6D CM5 preparation — PORT_REQUIRES_WORK

This maintained README covers `s6d_cm5_prepare_v1.py` and its copied preparation
package. The helper only reads/hashes files, copies small configuration/source
instruction files, and can relocate explicit gallery paths. It never loads
models, downloads/installs anything, enumerates audio devices, opens streams,
runs an app, or launches a supervisor.

The output is a **proposal, not a supported profile** for the intended CM5
2 GB RAM / 32 GB eMMC / CPU-only / no-wireless target. Exact board, OS,
glibc, wheel resolution, graph loading, memory, thermal/RTF, eMMC retention,
live audio, GUI callbacks and physical display scanout remain unverified.
Historical H2 classification stays PORT_REQUIRES_WORK. Its August 27 wheel
availability and predecessor Windows parity are historical evidence; neither
establishes current wheel availability or new S6D/ARM64 parity.

## Inputs and outputs

Input authority is the prospective accepted-source
`application/native_confirmation_predecl_v1/REPAIRED_GUIV3_MANIFEST.json`,
SHA256 `395dab640489f9e91545584fe17af60eb1b4e4332458c14ea1997da340769c8b`.
It binds GUIv3's 45 source files and original C065 anonymous / C088 A15 naming
profiles, with text_delivery=true, boundary_repair=true, T0/V0. Accepted source
does not mean those native configurations or this CM5 workload have been run.
The existing Windows native helper has C/G drive assumptions and is not the
CM5 launcher.

All eight actual asset files are bound: encoder/joiner INT8, decoder FP32,
ASR tokens, punctuation INT8 model and BPE vocabulary, ReDimNet FP32 and
Pyannote FP32. There are six ONNX graphs and two vocabulary/token files.
No graph is converted, quantized or substituted. ReDim
`5c1a8635cba0d4648463f3b6d30c5a6137bc38d1200ab00c5944400aaa7b5609`
and Pyannote
`b4b65085bbf2cc455565696604c87fedade1359aa6ddfac5d726d69124d5069a`
remain the existing exports.

`CM5_MANIFEST.json` records exact original source/model/config/gallery/PCM
bindings and a `transfer_map` of those files to target-relative paths.
`configs/` contains byte-identical C065/C088 O0 profiles and explicit S6D
settings. The original eight-pin Python 3.12 requirements are copied unchanged.
No model, gallery vector, audio or corpus payload is copied by preparation.
The manifest references the existing original A15 gallery and its thirty
metadata/vector files; it does not create a new enrollment.

The fixed small workload is three whole historical S6B PCM16 mono/16-kHz O0
files, selected from metadata rather than new outcomes:

| Case | Reason |
|---|---|
| S45_03_03 | Six declared subsecond whole replies |
| S45_02_10 | Three-person sequential switches and returns |
| S45_11_03 | Instrumental music-fma-0060_s00 interference, nominal 0 dB SNR |

Each file is 44.6954375 s. Run the same three files in C065 and C088 serially:
six separate jobs, 268.172625 source seconds, only 134.0863125 unique seconds.
This is a small resource/portability workload, not held-out efficacy evidence
or a full campaign. Historical O0 gain is already in its PCM; runtime gain is
unity, same ASR/identity tap and origin, no crop/normalization or extra +3 dB.

## Prepare or inspect on the existing Windows host

These are file-only commands. Use a fresh output suffix if deliberately
preparing another epoch; existing files are never overwritten.

PowerShell:

```powershell
$repo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$sim = "$repo\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
$r = "$sim\reports\S6D\20260913T195357Z"
& 'C:\Users\amiri\anaconda3\python.exe' -B "$sim\scripts\s6d_cm5_prepare_v1.py" prepare --repo $repo --report $r --output "$r\deployment_preparation_v1"
# Optional explicit later binding inspection; this does not load the app:
& 'C:\Users\amiri\anaconda3\python.exe' -B "$sim\scripts\s6d_cm5_prepare_v1.py" inspect --manifest "$r\deployment_preparation_v1\CM5_MANIFEST.json"
```

Anaconda Prompt / CMD:

```bat
set "REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "SIM=%REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "R=%SIM%\reports\S6D\20260913T195357Z"
"C:\Users\amiri\anaconda3\python.exe" -B "%SIM%\scripts\s6d_cm5_prepare_v1.py" prepare --repo "%REPO%" --report "%R%" --output "%R%\deployment_preparation_v1"
"C:\Users\amiri\anaconda3\python.exe" -B "%SIM%\scripts\s6d_cm5_prepare_v1.py" inspect --manifest "%R%\deployment_preparation_v1\CM5_MANIFEST.json"
```

The manifest also binds the unchanged historical H2 package and handoff docs.
Do not run H2's installer, service or export-pi from this preparation, and do
not treat their previous parity as current S6D validation.

## Target staging and inspection — future operator actions only

Nothing below was executed in preparation. Root must review/admit the exact
target and workload first. Transfer only the manifest's explicitly listed
files into a fresh target root, for example `/opt/just-peachy-s6d`. The
`transfer_map` gives source byte hashes and target paths. Use an approved
offline transfer; no wireless, runtime model download or whole corpus copy
is needed. Transfer this helper/README/manifest separately as small metadata.
Record the actual target-root, manifest hash, transfer map and wheelhouse hash
inventory. Any file change requires a new binding/review.

Prepare Python 3.12 from the selected target image and an offline wheelhouse.
These commands are actual future inspection/setup syntax, not evidence of
installation or current wheel availability:

```bash
uname -a
uname -m
getconf GNU_LIBC_VERSION
python3.12 --version
free -b
df -B1 /opt/just-peachy-s6d /var/lib/just-peachy-s6d
python3.12 -m venv /opt/just-peachy-s6d/venv
/opt/just-peachy-s6d/venv/bin/python -m pip install --no-index --find-links /media/s6d-wheelhouse --only-binary=:all: -r /opt/just-peachy-s6d/requirements-linux-arm64.txt
/opt/just-peachy-s6d/venv/bin/python -m pip freeze
/opt/just-peachy-s6d/venv/bin/python -m pip check
/opt/just-peachy-s6d/venv/bin/python -B /opt/just-peachy-s6d/s6d_cm5_prepare_v1.py inspect --manifest /opt/just-peachy-s6d/CM5_MANIFEST.json --staged-root /opt/just-peachy-s6d
```

Fail if the exact pins cannot resolve or load; do not silently compile a
replacement, relax versions, substitute a model or claim ARM64 ready.
The pins are numpy2.2.6, scipy1.15.3, PyYAML6.0.3, soundfile0.13.1,
sounddevice0.5.5, psutil7.2.2, onnxruntime1.29.0, sherpa-onnx1.13.4.
No native Torch/reference stack belongs beside the lean runtime.

The original gallery JSON contains absolute Windows paths. Stage the original
JSON and exact fifteen metadata/vector pairs under the transfer map, then
create a **separately hashed path-relocated gallery** on the target:

```bash
/opt/just-peachy-s6d/venv/bin/python -B /opt/just-peachy-s6d/s6d_cm5_prepare_v1.py relocate-gallery --manifest /opt/just-peachy-s6d/CM5_MANIFEST.json --staged-root /opt/just-peachy-s6d --output /opt/just-peachy-s6d/gallery/GALLERY_RELOCATED.json
```

This verifies every template byte and changes only manifest path fields,
preserving the gallery ID, identities, thresholds and backend. The new gallery
hash must enter target-run receipts. It is not byte-identical to the original
JSON and has not yet passed a target native loader test.

## Exact small file workload commands — future, serial and admitted

The manifest holds all six literal argument templates. `@STAGE@` and `@DATA@`
are path substitutions only; model/profile/settings bytes remain fixed.
Use one app process at a time, fresh output per job, and all inner pools one.
C065 must use its fresh empty ordinary profile directory; C088 uses the
explicit isolated A15 gallery. Never launch six resident pipelines or one
pipeline per speaker/beam.

Example for the declared short-reply C065 job:

```bash
set -euo pipefail
STAGE=/opt/just-peachy-s6d
DATA=/var/lib/just-peachy-s6d
export PYTHONPATH="$STAGE/app"
export EDGE_SPEECH_ASSET_ROOT="$STAGE"
export EDGE_SPEECH_DATA_ROOT="$DATA/C065_S45_03_03_O0_CM5_PROPOSAL"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1
mkdir -p "$EDGE_SPEECH_DATA_ROOT"
test -z "$(ls -A "$EDGE_SPEECH_DATA_ROOT")"
timeout --signal=INT --kill-after=60s 300s "$STAGE/venv/bin/python" -m edge_speech_pipeline file "$STAGE/workload/S45_03_03/O0.wav" --research-profile "$STAGE/configs/C065_O0_PROFILE.json" --s6d-settings "$STAGE/configs/S6D_SETTINGS.json" > "$EDGE_SPEECH_DATA_ROOT/stdout.log" 2> "$EDGE_SPEECH_DATA_ROOT/stderr.log"
```

For C088 set a new `EDGE_SPEECH_DATA_ROOT` matching its manifest job ID, use
`C088_O0_PROFILE.json` and append
`--research-gallery "$STAGE/gallery/GALLERY_RELOCATED.json"`. Apply the same
literal changes for the other two declared case IDs; do not alter PCM, taps,
gain, thresholds or pacing. No `--accelerated` flag is used. A timeout or
incomplete drain is a failed attempt with retained outputs, never a pass.
These CLI runs are headless; they do not measure Tk callback or screen scanout.
The 300+60 s bound is a proposed guard, not a CM5 performance estimate.

## 2 GB memory and 32 GB eMMC architecture proposal

Use one PipelineEngine with CPU Sherpa ASR/punctuation and shared ReDim/Pyannote
sessions; reuse embeddings/templates within that engine. C065/C088 have
one-thread model settings. Keep the original bounded worker queues and
120-second capture reserve; do not retune them to fit an unmeasured target.
A reviewed cgroup may adopt the historical 1650 MiB soft /1850 MiB hard guards,
zero swap and bounded tasks, but these are design limits, not measured fit.
Record OS available RAM, whole process-tree peak RSS/PSS, startup peak,
model-load time, source/progress counters, RTF, CPU, throttling/temperature,
queue ages and overflow/closure. Target supervisor/resource enforcement is
still required; the file-only helper implements none of those runtime guards.

Keep model/source trees read-only. Proposed eMMC storage envelope:
512 MiB per session, 32 MiB each stdout/stderr, 3 GiB for the six closed
workload sessions, and at least 4 GiB free before a target admission.
OS/venv/wheelhouse/install peaks and filesystem overhead remain unmeasured;
32 GB nominal capacity is not proof of sufficient space.

Operational diagnostics may use a 128 MiB ring with 16 MiB chunks, under a
separately reviewed supervisor/journal policy. The app's scientific event
streams, transcripts, raw spool, settings, source/model hashes, resource
samples, stderr, termination reason and final consumer/worker receipts must
remain intact through review/export. Never rotate/truncate active scientific
files or silently delete adverse/failed sessions. Once a closed session is
reviewed and its retained artifact archive/hash manifest is verified, an
explicit retention action may reclaim that session; no automatic deletion
is implemented or authorized here. If a limit is reached, stop cooperatively,
retain partial evidence and classify failure.

A production 2 GB fit, sustained no-swap operation, ARM64 numerical/E2E parity,
service restart/shutdown, eMMC log enforcement, ALSA/PipeWire permissions and
reconnect, microphone/expanded XVF qualification, Tk rendering and physical
scanout are all separate pending gates. The original Windows 0.1 s block-before-
sleep convention and headless publication timing do not prove any of those.
No CPU accelerator, live hardware support, CM5 speed or default promotion is
claimed by the manifest.
