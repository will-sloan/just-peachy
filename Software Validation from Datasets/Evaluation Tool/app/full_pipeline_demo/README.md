# Just-Peachy H2 Streaming Product Demo

## Purpose and boundary

This package is the common local desktop and command-line application for the
fixed H2 product architecture in `app/full_pipeline`. The product pair is
`AG-H2` (Sherpa Giga primary) and `AO-H2` (Original Sherpa fallback/reference),
both with Pyannote Segmentation 3.0 and one ReDimNet2-B2 speaker backend. It runs
microphone or incremental audio-file sessions, manages local ReDim enrollment
profiles, exposes user/research views, and exports completed sessions.

The three session-selectable speaker-label modes are `H2_KNOWN_ONLY`,
`H2_SESSION_ANONYMOUS`, and the primary
`H2_SESSION_MEMORY_ENHANCED`. The UI never imports a model implementation or
performs inference itself. File, microphone, enrollment, and inspector actions
all delegate to the shared runtime/services on background threads.

This application is the interactive surface for the separate H2 scientific
program; launching it does not itself run that campaign or retune a frozen
policy. Nothing is uploaded.

## Architecture

- `ui.py`: Tkinter/ttk desktop shell; all slow actions use background threads
  and results return through a bounded UI queue.
- `session.py`: immutable session creation, pause/resume/stop, verified H2 reset
  and anonymous-memory controls, reconnectable event cursors, and export.
- `presets.py`: presentation metadata generated from
  `full_pipeline_matrix.v1.yaml`; no component choice is duplicated in UI code.
- `h2_ux.py`: exact product modes and the primary/fallback H2 contract.
- `runtime_config.py`: strict, checksum-bound loading of the exact
  development-selected or frozen H2 tuning used by file and microphone
  builders.
- `state.py`: pure projection of locked events into transcript, active roster,
  memory state, and research evidence.
- `enrollment.py`: local WAV/microphone collection, technical quality checks,
  backend-bound profile creation, repeat/rebuild/remove/restore operations.
- `exports.py`: checksum-bound local session export with biometric-vector guard.
- `devices.py`: lazy microphone enumeration; importing the app never opens a
  device.
- `smoke.py`: retained legacy bounded application-mechanics smoke; it is not an
  H2 scientific result.
- `cli.py`: direct CLI used by `scripts/run_full_pipeline_demo.ps1`.

### Historical matrix compatibility

`PresetCatalog.payload()` and `presets --all-matrix` retain the former 18-row
research matrix for audit and older automation. The product UI and ordinary
`presets` command intentionally expose only AG-H2 and AO-H2. An older
checksum-bound catalog overlay may still be loaded for historical reproduction:

```powershell
$env:JP_FULL_PIPELINE_PRODUCTION_CATALOG = "C:\absolute\common_demo_production_catalog.yaml"
$env:JP_FULL_PIPELINE_PRODUCTION_CATALOG_SHA256 = "<64-lowercase-hex-sha256>"
```

`PresetCatalog` rejects a missing/mismatched hash, wrong bounded scope, unknown
pipeline, duplicate role, non-ready candidate, or default that is not PRIMARY.
It never changes the H2 product UI default: AG-H2 remains primary.

The model stacks remain in their isolated Prompt-1 worker environments. The
front end runs from the repository `.venv` and does not merge those stacks.

### Scientific runtime configuration

The application has two deliberately different configuration states:

- A supplied `h2-demo-runtime-binding.v1` bundle (multiple pipeline/mode
  entries) or controller-emitted `h2-frozen-product-configuration.v1` file is
  parsed as strict UTF-8 JSON. The loader rejects duplicate or unknown keys,
  unknown pipelines or modes, non-finite values, stale tuning hashes, mode
  conflicts, missing exact pipeline/mode entries, invalid canonical binding
  identities, and optional expected file-hash mismatches.
- If no binding is supplied, the app remains usable but reports
  `ENGINEERING_BASELINE_NOT_FINAL` in the UI, session status, durable identity
  manifest, and export. That run is not evidence that the final selected
  scientific configuration was demonstrated.

A multi-mode bundle declares `default_product_mode`; the app does not
hard-code over it. An explicit product-mode selection must have its own exact
entry. The app never changes the mode field on another entry, so all other
runtime axes remain selected and hash-bound. `FINAL_VALIDATED` is accepted
only with a `validation_identity_sha256`; an ordinary frozen development
configuration does not claim final demo validation.

## Inputs

- `fullpipe_v1_ag_dr_ir` (primary) or `fullpipe_v1_ao_dr_ir` (fallback), plus
  one of the three exact H2 product-mode IDs.
- Optional scientific runtime binding JSON and its independently recorded
  expected SHA-256. A bundle must contain an exact entry for the chosen
  pipeline/mode. A single frozen per-mode file can run only its declared
  pipeline/mode.
- Live mode: a selected local input device, optional device-native sample rate
  and channel count, and a positive bounded session duration.
- File mode: a readable audio file, replay pace (`1.0` real time, `0` fastest,
  or `>1` accelerated), optional local playback, and an optional positive
  duration bound. The PowerShell wrapper processes the complete file when
  `-DurationSec` is omitted; Live mode retains its 30-second default.
- Enrollment: a display name plus exactly three prompted microphone takes or
  three explicitly labelled WAVs. The frozen enrollment target is about 10 s
  total; backend technical minimums and the additive demo QC gate also apply.
- Export: a completed run directory and a new destination directory. Input
  audio is excluded unless the user explicitly authorizes it.
- Bounded smoke: by default the portable single-speaker CMU Arctic asset at
  `JP_DATA_ROOT/Raw Datasets (Not formatted)/CMU Arctic/cmu_us_aew_arctic/wav/arctic_a0281.wav`
  (SHA-256 `c3ebf5bc3f4ecc92c99367e554c2bfae34e551655cc3415144bdc507566b0d36`).
  The asset remains external and is not copied into Git.

## Outputs

Canonical live runs are written below:

```text
JustPeachyResults/full_pipeline/demo_sessions/<session_id>/
```

They contain the Prompt-1 `result.json`, `session_state.json`, `status.json`,
durable event JSONL, transcript revisions/final transcript, speaker events,
telemetry, diagnostics, provenance, hashes, and worker identities. A user-chosen
local export adds:

```text
transcript/labelled_transcript.jsonl
transcript/labelled_transcript.txt
transcript/labelled_transcript.md
events/events.jsonl
evidence/identity_evidence.jsonl
telemetry/resource_samples.jsonl
manifests/pipeline_identity.json
manifests/component_identities.json
manifests/enrollment_profiles.json
manifests/scientific_runtime_configuration.json
diagnostics/failures.json
checksums.json
manifest.json
```

The three split identity manifests are authoritative export views. The older
combined `identities/pipeline_models_profiles.json` and `logs/failure.json`
paths are retained for compatibility. Labelled transcripts are classified
`private`; the complete event log, identity evidence, enrollment-profile
manifest, and copied session state are `biometric_sensitive`. They contain no
embedding/template vectors. Every file's classification, byte count, and hash
is recorded in `manifest.json`/`checksums.json`.

Each session also writes
`manifests/demo_runtime_configuration.json` before model loading. It records
the configuration status, absolute source path, actual and expected source
file hashes, canonical binding identity, product mode, and exact
`H2RuntimeTuning` identity. The same values appear in live session status,
pipeline identity, and the local export.

Local enrollment data defaults to:

```text
JustPeachyResults/full_pipeline/enrollment_profiles/
```

Normalized recordings and quality documents are local. Biometric templates are
checksum-bound protected NPZ artifacts and are never inlined in event logs or
normal exports. Profile removal is recoverable archival; rebuild creates a new
version before archiving the prior profile.
The small embedding-consistency matrix uses a formula-equivalent explicit dot
product reduction so repeated checks remain stable on Windows MKL and portable
to Linux ARM64.

## Desktop app

The desktop app has three input/management modes:

1. **Live microphone**: refresh/select an input device, inspect rate/channels,
   choose AG-H2 or AO-H2 and a speaker-label mode, then
   Start/Pause/Resume/Stop. Optional input recording is off by default and stays
   local.
2. **Audio-file simulation**: choose a file, choose real-time or accelerated
   engineering pace, optionally play it, then use the same runtime controls.
   Active-session seek is intentionally unavailable because it would invalidate
   native ASR, diarization, clustering, and identity state. Start a new immutable
   session at a scientifically declared boundary instead.
3. **Speaker enrollment**: enter a display name, record the displayed prompts or
   import labelled WAVs, review duration/RMS/peak/clipping/consistency, repeat a
   rejected take, then create a backend-specific profile. The app shows the
   ReDim backend/config/model/profile identities and supports list/remove/rebuild.

The speaker-label selector controls a distinct privacy/behavior contract:

- `H2_KNOWN_ONLY`: enrolled names or generic `Unknown`; no persistent
  `Speaker_N` identity for unenrolled people.
- `H2_SESSION_ANONYMOUS`: session-local `Speaker_N` continuity plus safely
  confirmed enrolled names.
- `H2_SESSION_MEMORY_ENHANCED`: the primary behavior, adding active roster,
  tentative/confirmed names, bounded memory, warm reacquisition, and expiry.

The **User view** shows readable labelled transcript, known/`Speaker_N`/Unknown
labels, simple tentative/confirmed wording, and an active session roster. It
never presents a raw cosine score as a confidence percentage. **Reset Session**
clears volatile anonymous profiles and identity mappings only after the runtime
confirms the operation; permanent enrolled profiles are never touched. The user
chooses whether reset preserves or deletes the transcript. **Clear Anonymous
Memory** keeps permanent enrollment and visible transcript.

The **Research view** includes an embedding inspector backed by the latest
runtime `IdentityEvidenceEvent`: closest enrolled identity, raw Top-1 and Top-2
cosine scores, margin, evidence duration, quality gate, ReDim backend/model,
checkpoint hash, cluster, decision, and warnings. “Probability” is never used.
Import/record inspector buttons prepare the ordinary file/live H2 path, so the
UI does not duplicate embedding inference. The view also shows partial/final
ASR, segmentation, RTF, CPU/RAM, queue state, latency, and ordered events.

H4, H5, and the other historical matrix rows are not selectable in the product
UI. Use `python -m app.full_pipeline_demo presets --all-matrix` only for a
read-only compatibility inventory.

## PowerShell commands (repository root)

Launch the desktop demo:

```powershell
powershell -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_demo.ps1" `
  -Action Demo
```

Launch with the exact checksum-bound scientific configuration (use the
expected hash published in the H2 result package's separate
`h2_configuration_registry.yaml`; do not recompute the expected value from the
binding being trusted):

```powershell
$Config = "C:\path\to\h2_demo_runtime_binding.json"
$ExpectedConfigSha256 = "<64-character-expected-sha256>"
powershell -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_demo.ps1" `
  -Action Demo `
  -H2RuntimeConfig $Config `
  -H2RuntimeConfigSha256 $ExpectedConfigSha256
```

Omitting both configuration arguments is allowed only as the visibly labelled
engineering baseline.

List presets and input devices without loading models:

```powershell
powershell -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_demo.ps1" `
  -Action Presets

powershell -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_demo.ps1" `
  -Action Devices
```

Direct 30-second AG-H2 live CLI in the primary memory-enhanced mode; add
`-RecordInputAudio` only with local authorization:

```powershell
powershell -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_demo.ps1" `
  -Action Live `
  -PipelineId "fullpipe_v1_ag_dr_ir" `
  -ProductMode "H2_SESSION_MEMORY_ENHANCED" `
  -H2RuntimeConfig "C:\path\to\h2_demo_runtime_binding.json" `
  -H2RuntimeConfigSha256 "<64-character-expected-sha256>" `
  -DurationSec 30 `
  -Device "0"
```

Incremental real-time file simulation through the exact live path, with local
playback and a completed-session export:

```powershell
powershell -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_demo.ps1" `
  -Action File `
  -PipelineId "fullpipe_v1_ag_dr_ir" `
  -ProductMode "H2_SESSION_MEMORY_ENHANCED" `
  -H2RuntimeConfig "C:\path\to\h2_demo_runtime_binding.json" `
  -H2RuntimeConfigSha256 "<64-character-expected-sha256>" `
  -InputPath "C:\path\to\speech.wav" `
  -Pace 1.0 `
  -PlayAudio `
  -ExportRoot "C:\path\to\new_session_export"
```

Add a positive `-DurationSec` to bound file processing. The legacy wrapper
value `-DurationSec 0` also means the complete file. `-IncludeAudio` is valid
only with `-ExportRoot`; Live mode additionally requires
`-RecordInputAudio`, keeping microphone recording and export explicit opt-ins.

Create a ReDimNet2 profile from three labelled WAVs:

```powershell
powershell -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_demo.ps1" `
  -Action EnrollImport `
  -PipelineId "fullpipe_v1_ag_dr_ir" `
  -DisplayName "Alice" `
  -Wav1 "prompt_1=C:\enrollment\alice_1.wav" `
  -Wav2 "prompt_2=C:\enrollment\alice_2.wav" `
  -Wav3 "prompt_3=C:\enrollment\alice_3.wav"
```

`-Wav1`, `-Wav2`, and `-Wav3` are scalar wrapper parameters because Windows
PowerShell does not reliably bind an array across `powershell.exe -File`. When
calling the script directly inside an existing PowerShell session, the original
`-Wav @("prompt_1=...", "prompt_2=...", "prompt_3=...")` form also remains
supported. `RebuildProfile` accepts the same two forms.

Record the three built-in prompts from a microphone:

```powershell
powershell -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_demo.ps1" `
  -Action EnrollRecord `
  -PipelineId "fullpipe_v1_ag_dr_ir" `
  -DisplayName "Alice" `
  -Device "0"
```

Run the retained bounded legacy application smoke (not the H2 scientific campaign):

```powershell
powershell -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_demo.ps1" `
  -Action Smoke
```

This command remains available only for regression compatibility with the
pre-pivot common demo. It must not be interpreted as current H2 model selection
or scientific evidence.

## Anaconda Prompt / direct command line

The common front end uses the repository `.venv`. The runtime launches each
model in its own recorded environment automatically.

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy"
call ".venv\Scripts\activate.bat"
cd /d "Software Validation from Datasets\Evaluation Tool"
python -m app.full_pipeline_demo launch
```

Checksum-bound launch from Anaconda Prompt or Command Prompt:

```bat
python -m app.full_pipeline_demo launch --h2-runtime-config "C:\path\to\h2_demo_runtime_binding.json" --h2-runtime-config-sha256 "<64-character-expected-sha256>"
```

Direct live, file, and enrollment equivalents:

```bat
python -m app.full_pipeline_demo live --pipeline-id fullpipe_v1_ag_dr_ir --product-mode H2_SESSION_MEMORY_ENHANCED --h2-runtime-config "C:\path\to\h2_demo_runtime_binding.json" --h2-runtime-config-sha256 "<64-character-expected-sha256>" --duration-sec 30 --device 0
python -m app.full_pipeline_demo file --pipeline-id fullpipe_v1_ag_dr_ir --product-mode H2_SESSION_MEMORY_ENHANCED --h2-runtime-config "C:\path\to\h2_demo_runtime_binding.json" --h2-runtime-config-sha256 "<64-character-expected-sha256>" --input "C:\path\to\speech.wav" --pace 1 --play-audio
python -m app.full_pipeline_demo enroll-record --pipeline-id fullpipe_v1_ag_dr_ir --display-name "Alice" --device 0
python -m app.full_pipeline_demo enroll-import --pipeline-id fullpipe_v1_ag_dr_ir --display-name "Alice" --wav "prompt_1=C:\enrollment\alice_1.wav" --wav "prompt_2=C:\enrollment\alice_2.wav" --wav "prompt_3=C:\enrollment\alice_3.wav"
```

Programmatic callers provide the same independent path/hash pair to the
manager; file and microphone starts then resolve an exact entry through the
same loader:

```python
from pathlib import Path
from app.full_pipeline_demo.session import DemoSessionManager

manager = DemoSessionManager(
    runtime_config_path=Path(r"C:\path\to\h2_demo_runtime_binding.json"),
    runtime_config_expected_sha256="<64-character-expected-sha256>",
)
```

## Reliability and operating rules

- Model loading/inference never runs on the Tk event thread. UI overflow is
  surfaced and can resynchronize from the durable JSONL cursor.
- Microphone/file errors, unsupported formats, worker failures, slow-consumer
  drops, invalid/missing profiles, duration gates, disconnects, and user stop
  become status/failure artifacts rather than a frozen UI.
- File pause preserves the pacing epoch. Live pause discards captured samples
  deliberately and resumes with an explicit discontinuity/reset boundary.
- Model switching creates a new immutable session and output root. Adapters are
  never hot-swapped inside a session.
- A stopped session is finalized as `stopped`, not misreported as successful
  end-of-input.
- File playback and microphone input recording are explicit opt-ins. No network
  upload is implemented.
- Do not treat the demo smoke, prompted enrollment, raw cosine score, or a frozen
  research anchor threshold as production Beaker evidence.

## Focused developer checks

From the Evaluation Tool root:

```bat
"..\..\.venv\Scripts\python.exe" -m pytest tests\full_pipeline_demo tests\full_pipeline\test_demo_runtime_controls.py -q
"..\..\.venv\Scripts\python.exe" -m ruff check app\full_pipeline_demo tests\full_pipeline_demo app\full_pipeline\audio.py app\full_pipeline\factory.py tests\full_pipeline\test_demo_runtime_controls.py
"..\..\.venv\Scripts\python.exe" -m app.full_pipeline_demo presets
```
