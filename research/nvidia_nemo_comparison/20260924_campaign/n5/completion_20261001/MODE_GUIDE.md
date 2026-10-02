# Backend and mode guide

Status: five short microphone compositions passed normal recording/closure and complete local/PC backup. The current field-runtime-v8 has consumed its four recording slots and is idle. Final unconsumed release, saved-audio routes and offline startup are still being completed. Do not treat an exhausted candidate as the final handoff.

All choices retain Sherpa ONNX ASR/PnC. NeMo TitaNet reuses the original ONNX graph and frontend; ReDimNet remains available. Nemotron ASR is deferred. No downloads or enrollment occurred.

| Profile | Diarizer | Speaker representation | Availability |
|---|---|---|---|
| baseline | Baseline Pyannote | ReDimNet | Short native recording passed |
| baseline-titanet | Baseline Pyannote | NeMo TitaNet | Short native recording passed |
| d1-delayed | Nemotron-3 Delayed | ReDimNet | Short native recording passed |
| d1-delayed-titanet | Nemotron-3 Delayed | NeMo TitaNet | Short native recording passed in candidate7 |
| d1-anonymous | Nemotron-3 Delayed | Anonymous native slots | Short native recording passed |
| baseline-anonymous | Baseline Pyannote | ReDimNet anonymous continuity | Installed; focused mode check open |
| d1-streaming-saved | Nemotron-3 Streaming | ReDimNet | Saved source integration open |
| d1-streaming-titanet-saved | Nemotron-3 Streaming | NeMo TitaNet | Saved source integration open |
| d1-chunk52-saved | Nemotron-3 Chunk52 | ReDimNet | Saved source integration open |
| d1-chunk52-titanet-saved | Nemotron-3 Chunk52 | NeMo TitaNet | Saved source integration open |

## Current Pi entry and controls

Desktop labels spell out Sherpa, diarizer and encoder. Each starts the same versioned frontend idle with capture off; duplicate ownership is rejected. The profile list can select another combination before New. Only close an idle manager before opening another shortcut.

Current Pi terminal command (candidate8 is exhausted; final path will replace it):
~~~sh
/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v8-profiles/bin/launch-profile --profile d1-delayed-titanet
~~~
Substitute a supported microphone profile from the table. A shortcut selection never silently substitutes a model.

Recording sequence: select profile, New recording, broker New, create a consented audio draft in History/Developer Sessions, Start and consent, Stop, Save, Return to modes, then Close the broker. The manager verifies an independent local copy before enabling another recording. The current mandatory processed-audio draft is not yet the requested optional Off/Processed selector. Raw+processed remains unavailable until actual simultaneous MIC0–MIC3 routing and clocks are qualified.

Each policy reserves four recordings of at most120seconds,16manager/helper launches and a24hour idle lifetime. These are finite testing limits, not unlimited recording. Failed/consumed slots are retained. A fresh measured release is required after exhaustion; never edit a closed policy or delete files to obtain credit.

## Verified copy to PC

Purpose: copy a stopped successful recording and its separate Pi-local backup into a new private PC directory; preserve originals. Inputs are the actual install, latest owner/closure inspection, complete prior binding and a fresh bounded scope. Output includes both complete trees, hashes/readback, native closure and BACKUP.json. Current successful copies are listed in PATHS_AND_BACKUPS. No playback or deletion.

PowerShell, from the native source directory:
~~~powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B .\export_runtime_recording_v2.py --local LOCAL_ROOT --private PRIVATE_ROOT --prior-closure PRIOR_BINDING --previous-inspection LAST_INSPECTION --candidate-install ACTUAL_INSTALL --scope FRESH_SCOPE --slot recording-01 --output NEW_PRIVATE_OUTPUT
~~~
CMD / Anaconda Prompt:
~~~bat
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B export_runtime_recording_v2.py --local LOCAL_ROOT --private PRIVATE_ROOT --prior-closure PRIOR_BINDING --previous-inspection LAST_INSPECTION --candidate-install ACTUAL_INSTALL --scope FRESH_SCOPE --slot recording-01 --output NEW_PRIVATE_OUTPUT
~~~
See README_RUNTIME_RECORDING_OFFLOAD_V2.md for exact argument semantics. Reusable self-contained final operator offload admission remains part of completion; old expired scopes cannot be reused.

## Choosing a diarizer

Delayed uses264/1/1/0/264/188 geometry and about21.3seconds of source buffering. Streaming uses13/1/0/80/264/40; Chunk52 uses52/1/0/80/264/40. Retained44.7second component costs were about0.405/3.634/1.085RTF respectively. Those different geometries are not a quality ranking or an application speedup. Streaming/Chunk52 have historical saved application evidence, not general live availability. GPU is off; fixed exact native assets and one model thread are retained.

## Speaker identity and product modes

ReDimNet and TitaNet both produce192-dimensional vectors but use different spaces. Exact encoder/frontend/preprocessing/tap/gain namespaces are mandatory. Existing E0 personal references are preserved; TitaNet has an empty separate gallery and must remain Unknown without compatible references. Nothing was converted, enrolled or silently shared. The short quiet runs establish loading and recording, not nonempty embedding-query accuracy or improved recognition.

Named/Unknown, selected roster, anonymous continuity and spatial behavior are separate from backend composition. The installed shortcuts currently pin open-with-names or explicit anonymous. Selected/closed-roster/spatial choices require their own supported controller route and honest unavailable reasons; never infer a person from an anonymous number or empty gallery. No new physical touch, acoustic clock calibration, noisy-human accuracy or source-reference parity claim is made.

All26 completion items and all N1–N5/34-method research distinctions remain in FINISH_CHECKLIST, COVERAGE and MASTER_BACKEND_MODE_GUIDE. Only final F26 creates the condensed handoff ZIP.
