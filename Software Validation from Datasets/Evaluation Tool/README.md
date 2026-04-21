# Evaluation Tool

Local dataset-aware batch evaluation for normalized speech metadata.

This tool reads normalized metadata from the project-level `Normalized Metadata/`
folder and writes all run artifacts under `Evaluation Tool/runs/`. It does not
modify raw datasets and does not create a persistent augmented copy of a corpus.

## Plain-Language Summary

Pick a dataset, optionally filter it, optionally make clean single-speaker audio
sound like it was played in a room or mixed with noise, then send that audio to
a model. The tool compares the model transcript against the normalized
reference transcript and saves scores, plots, logs, previews, and a report.

AMI is different from CMU Arctic, LibriSpeech, and HiFiTTS: it is a
multi-speaker meeting corpus. AMI runs use the original meeting audio and add
speaker-attributed transcript checks instead of reverb/noise augmentation.

VOiCES is also different from the clean single-speaker datasets. It is already
recorded under far-field room, distractor, microphone, and distance conditions,
so VOiCES runs use the native distant WAV files and group metrics by those
recorded conditions instead of applying synthetic augmentation.

CHiME-6 is a conversational far-field dataset recorded around table-style home
sessions. It uses the original session audio, projects speaker-attributed
reference utterances onto close-talk or far-field streams, and groups results by
session, stream, device, microphone, location, and speaker.

Augmented audio is created only while a run is active. The tool saves small
preview WAV files when requested, but it does not duplicate entire datasets.

## Supported Phase 1 Datasets

| Dataset | Registry key | Evaluation unit | Reference tables |
|---|---|---|---|
| AMI Meeting Corpus | `ami` | one speaker-attributed meeting segment projected onto one WAV stream | `utterances.parquet`, `recordings.parquet` |
| CHiME-6 | `chime6` | one speaker-attributed conversation segment projected onto one WAV stream | `utterances.parquet`, `recordings.parquet` |
| CMU Arctic | `cmu_arctic` | one utterance WAV file | `utterances.parquet`, `recordings.parquet` |
| HiFiTTS | `hifitts` | one utterance FLAC file | `utterances.parquet`, `recordings.parquet` |
| LibriSpeech | `librispeech` | one utterance FLAC file | `utterances.parquet`, `recordings.parquet` |
| VOiCES DevKit | `voices` | one far-field single-speaker WAV utterance | `utterances.parquet`, `recordings.parquet` |

Optional context tables:

- AMI: `words.parquet`, `segments.parquet`, `meetings.parquet`, `participants.parquet`
- CHiME-6: `segments.parquet`, optional future `words.parquet` and `conditions.parquet`
- HiFiTTS: `readers.parquet`, `reader_books.parquet`, `book_bandwidth.parquet`
- LibriSpeech: `speakers.parquet`, `chapters.parquet`, `books.parquet`
- VOiCES: `conditions.parquet`, `speakers.parquet`, `source_map.parquet`

## Install

Use a Python environment with:

```bash
pip install -r requirements.txt
```

Required packages include `pandas`, `pyarrow`, `PyYAML`, `tqdm`, `matplotlib`,
`numpy`, `scipy`, and `soundfile`.

The verified interpreter on this machine is:

```powershell
& "C:\Users\amiri\anaconda3\python.exe" run_evaluation.py list-datasets
```

## Run The GUI

The easiest way to configure runs is the local tkinter GUI:

```bash
cd "Evaluation Tool"
python run_evaluation.py gui
```

With the verified interpreter on this machine:

```powershell
& "C:\Users\amiri\anaconda3\python.exe" run_evaluation.py gui
```

The GUI is a front end over the existing pipeline. It does not implement a
separate evaluator. When you click **Launch Run**, it serializes your selections
into one or more `run_evaluation.py` commands and runs them sequentially.

Plain-language flow:

1. Choose one or more datasets.
2. Pick subset values from compact dropdown-style multi-select filters, or
   leave them as `Any` to run the whole dataset.
3. Choose simulation or the external runner hook.
4. Choose augmentation, RIRs, noise, SNR, preview, and run limits.
5. Launch the run and watch the progress/output panel.

Smart-control behavior:

- Simulation choices appear when the simulation runner is selected.
- RIR controls appear for `reverb` and `reverb_noise`.
- The RIR selector is a fixed-height scrollable multi-select list, so selecting
  reverb does not make the window grow to fit every RIR file.
- The overall GUI form is vertically scrollable, so all controls remain
  reachable on smaller screens while nested lists keep their own scrolling.
- Noise controls appear for `noise` and `reverb_noise`.
- Dataset filters are grouped by dataset, so a HiFiTTS-only filter is not shown
  as a LibriSpeech setting.
- If AMI, VOiCES, or CHiME-6 is selected, augmentation controls are disabled
  with an explanation. If any of those datasets are part of a multi-dataset GUI
  batch, the whole batch uses original audio because augmentation is only
  supported for the clean single-speaker datasets.
- Subset filters are populated from the normalized metadata. Click a filter to
  open a short scrollable value list, select one or more values, then click
  **Done** or click away to close it.
- Leaving every subset filter as `Any` means a full-dataset run. In that case,
  the scorer automatically writes all relevant grouped metric summaries for the
  dataset.
- Invalid configurations are blocked before launch, such as no dataset selected,
  reverb without an RIR, or noise without SNR values.

### Preview Audio From The GUI

Preview audio is now a separate workflow from full runs. Use **Choose Preview
Source Audio File...** to preview any WAV or FLAC file directly, or enter a
normalized `recording_id` in the preview field. If neither is provided, the
preview uses the first source recording matched by the selected dataset and
filters.

Click **Generate Preview Audio** to create preview WAV files using the current
augmentation settings without launching inference, scoring, plots, or reports.
This works for pink noise, white noise, reverb, and reverb + noise.

Preview output is saved in a preview-only run folder:

```text
runs/<timestamp>_<dataset>_preview_<run_name>/
  augmentation_config.json
  dataset_selection.json
  dataset_selection_source_records.jsonl
  preview_audio/
    preview_manifest.json
    <condition_id>/
      <dataset>__<recording_id>__<condition_id>.wav
```

The condition folder and filename include identifying details such as
augmentation mode, RIR label, noise type, and SNR.

### Multi-Dataset GUI Runs

The internal evaluator runs one dataset per run folder. When multiple datasets
are selected in the GUI, the GUI acts as a batch launcher. It creates one CLI
command per selected dataset, applies only that dataset's filters, and runs the
commands sequentially. This keeps the existing run structure simple while still
letting a user configure a multi-dataset session once.

For example, a GUI batch selecting CMU Arctic and HiFiTTS with run name
`my_batch` launches two runs with dataset-specific run-name suffixes:

```text
... --dataset cmu_arctic --run-name my_batch_cmu_arctic
... --dataset hifitts --run-name my_batch_hifitts
```

### GUI Configuration Mapping

The GUI maps selections to the same CLI options documented below:

- selected datasets -> one `--dataset` command per dataset
- per-dataset filter selections -> repeated `--subset key=value1,value2`
- simulation runner -> `--runner simulation --simulation-mode ...`
- external runner -> `--runner external-stub`
- augmentation mode -> `--augmentation ...`
- selected RIRs -> repeated `--rir-paths ...`
- selected noise types -> repeated `--noise-type ...`
- SNR field such as `5, 10, 20` -> repeated `--snr-db 5 --snr-db 10 --snr-db 20`
- preview toggle -> `--preview`
- preview recording field -> `--preview-recording-id ...`
- max recordings -> `--max-recordings ...`
- run name -> `--run-name ...`

## Run The CLI

Run commands from inside `Evaluation Tool/`:

```bash
cd "Evaluation Tool"
python run_evaluation.py list-datasets
```

The module entry point also works:

```bash
python -m app.cli.main list-datasets
```

## Prediction Contract

The minimum prediction file is:

```text
predictions/utterances.jsonl
```

Each line must contain:

```json
{
  "recording_id": "string",
  "utt_id": "string",
  "start_sec": 0.0,
  "end_sec": 1.23,
  "speaker_label": "speaker-or-null",
  "text": "predicted transcript"
}
```

Optional future files:

- `predictions/words.jsonl`
- `predictions/segments.rttm`

The scorer works when only `utterances.jsonl` exists. For AMI and CHiME-6,
`utterances.jsonl` is used for speaker-attributed transcript scoring. If
`segments.rttm` is also present, the tool runs a first-phase speaker segment
overlap check by matching each reference segment to the predicted RTTM segment
with the largest time overlap.

## External Inference Integration

The evaluator calls a model runner one selected item at a time. For augmented
runs, the runner receives a temporary WAV path in `inference_audio_path`. That
temporary file is valid during the call and is removed after inference unless a
preview was explicitly requested.

The current external stub is:

```text
app/model_runner/external_stub.py
```

Real integration means replacing `ExternalStubRunner.predict_one()` with a call
to another ASR system and returning `UtterancePrediction(...)`.

Example stub run:

```bash
python run_evaluation.py run --dataset hifitts --reader-split 6097_clean --max-recordings 25 --runner external-stub --run-name hifitts_real_stub
```

## Augmentation Options

Augmentation is available only for the clean single-speaker datasets:

- CMU Arctic
- LibriSpeech
- HiFiTTS

AMI uses original meeting audio. VOiCES uses its native far-field recordings.
CHiME-6 uses its native close-talk and far-field session recordings. Reverb,
noise, SNR sweeps, and augmentation preview audio are blocked for AMI, VOiCES,
and CHiME-6 runs.

Supported modes:

- `none`
- `reverb`
- `noise`
- `reverb_noise`

RIR files are expected under:

```text
Raw Datasets (Not formatted)/MIT 271 RIRs/Audio/
```

You can pass either a project-relative path or a filename from that RIR folder.

Noise types:

- `white`
- `pink`

SNR values are in dB and can be repeated for sweeps.

Technical behavior:

- Audio is loaded with `soundfile`.
- RIRs are mono-converted, resampled to the source sample rate, and convolved
  with `scipy.signal.fftconvolve`.
- Noise is generated deterministically from a run seed, condition id, and
  recording id.
- Noise is scaled to the requested SNR relative to the current signal.
- Peak protection scales output to avoid clipping.
- Augmented inference audio is written as temporary WAV files during the run.
- Preview WAVs are saved only when `--preview` is used.

The reference transcript always comes from the original normalized metadata.
The model is evaluated on its transcript after hearing the augmented audio.

## Augmentation Examples

No augmentation simulation:

```bash
python run_evaluation.py full --dataset cmu_arctic --max-recordings 10 --simulation-mode perfect --run-name cmu_clean_smoke
```

White-noise simulation:

```bash
python run_evaluation.py full --dataset librispeech --subset split=dev-clean --max-recordings 10 --augmentation noise --noise-type white --snr-db 20 --simulation-mode noisy --run-name libri_white20
```

Pink-noise HiFiTTS preview:

```bash
python run_evaluation.py full --dataset hifitts --reader-split 6097_clean --max-recordings 10 --augmentation noise --noise-type pink --snr-db 15 --preview --simulation-mode noisy --run-name hifitts_pink15_preview
```

Reverb preview using one MIT RIR:

```bash
python run_evaluation.py full --dataset cmu_arctic --max-recordings 3 --augmentation reverb --rir-paths h001_Bedroom_65txts.wav --preview --simulation-mode perfect --run-name cmu_reverb_preview
```

Combined reverb and noise:

```bash
python run_evaluation.py full --dataset cmu_arctic --max-recordings 5 --augmentation reverb_noise --rir-paths h001_Bedroom_65txts.wav --noise-type white --snr-db 20 --simulation-mode noisy --run-name cmu_reverb_noise
```

Sweep multiple SNRs:

```bash
python run_evaluation.py full --dataset hifitts --reader-split 6097_clean --max-recordings 20 --augmentation noise --noise-type white --noise-type pink --snr-db 10 --snr-db 20 --simulation-mode noisy --run-name hifitts_noise_sweep
```

## Simulation Mode

Simulation mode is fully runnable through the same selection, augmentation,
prediction, scoring, plotting, and reporting flow.

Modes:

- `perfect`: writes the selected reference transcript exactly.
- `noisy`: applies small deterministic transcript corruptions.
- `drop_some`: skips about one in twenty selected files to test missing output.

Simulation lets you verify the pipeline without a real external ASR system. The
augmentation step still materializes augmented audio when augmentation is
enabled for clean single-speaker datasets, so the audio-processing path is
tested too. For AMI, VOiCES, and CHiME-6, simulation still tests selection,
prediction, scoring, grouping, plotting, and reporting, but keeps augmentation
disabled.

Missing predictions are expected in `drop_some` mode. They are written to
`metrics/missing_predictions.csv`, counted in aggregate metrics, excluded from
transcript-error aggregates, and shown as warnings in GUI batch runs. A dataset
with missing predictions still finishes, and a multi-dataset GUI batch continues
to the next dataset unless there is a hard command failure.

## Subset Filters

In the GUI, subset filters are dropdown-style multi-select controls. The values
come from the selected dataset's normalized metadata, so users choose from real
available values instead of typing them. A filter left as `Any` is not applied.

In the CLI, use generic filters as repeated `--subset key=value` arguments. A
single filter can also accept comma-separated values:

```bash
python run_evaluation.py full --dataset librispeech --subset split=dev-clean,test-clean --max-recordings 10
```

AMI supports:

- `meeting_id`
- `recording_id`
- `stream_type`, such as `headset` or `array`
- `stream_id`, such as `Headset-0` or `Array1-01`
- `meeting_type`
- `visibility`
- `seen_type`
- `agent`
- `speaker_global_name`
- `speaker_role`
- `gender`

CHiME-6 supports:

- `split`, such as `train`, `dev`, or `eval`
- `session_id`, such as `S02` or `S03`
- `stream_type`, such as `participant_close` or `farfield_array`
- `speaker_id_ref`, such as `P05`
- `recording_speaker_id_ref`, for participant close-talk streams
- `device_id`, such as `U01`
- `channel_id`, such as `CH1`
- `microphone_id`, such as `U01_CH1` or `P05`
- `ref_device`, such as `U02`
- `location`, such as `kitchen`, `dining`, or `living`
- `location_hint`
- `recording_id`

CMU Arctic supports:

- `speaker_id`
- `speaker_code`
- `gender`
- `accent`
- `accent_group`
- `speaker_variant_group`

LibriSpeech supports:

- `split`
- `subset_group`
- `speaker_id`
- `chapter_id`
- `book_id`
- `gender`

HiFiTTS supports:

- `reader_id`
- `reader_split`, such as `6097_clean` or `11614_other`
- `split`, such as `train`, `dev`, or `test`
- `clean_vs_other`
- `audio_quality`
- `book_id`
- `gender`

VOiCES supports:

- `split`, such as `train` or `test`
- `room`, such as `rm1`
- `distractor`, such as `musi`, `babb`, `tele`, or `none`
- `mic`
- `device`
- `position`, such as `clo` or `far`
- `degrees`
- `speaker_id`
- `speaker_id_padded`
- `gender`
- `chapter_id`
- `segment_id`
- `query_name`
- `distance_foreground_class`
- `stoi_class`
- `pesq_wb_class`
- `srmr_class`

Single-value example:

```bash
python run_evaluation.py full --dataset librispeech --subset split=dev-clean --max-recordings 10
```

Convenience flags:

```bash
python run_evaluation.py full --dataset ami --meeting-id IS1000a --stream-type headset --max-recordings 25
python run_evaluation.py full --dataset ami --stream-type array --stream-id Array1-01 --seen-type training --max-recordings 25
python run_evaluation.py full --dataset chime6 --split dev --session-id S02 --stream-type participant_close --max-recordings 25
python run_evaluation.py full --dataset chime6 --split dev --session-id S02 --stream-type farfield_array --microphone-id U01_CH1 --max-recordings 25
python run_evaluation.py full --dataset voices --split test --room rm1 --distractor none --position far --max-recordings 25
python run_evaluation.py full --dataset voices --subset room=rm1,rm2 --subset position=clo,far --max-recordings 25
python run_evaluation.py full --dataset hifitts --reader-split 6097_clean --max-recordings 25
python run_evaluation.py full --dataset hifitts --reader-id 6097 --split dev --max-recordings 25
python run_evaluation.py full --dataset hifitts --clean-vs-other other --max-recordings 25
```

## Commands

### `list-datasets`

```bash
python run_evaluation.py list-datasets
```

### `gui`

Launches the local GUI.

```bash
python run_evaluation.py gui
```

### `run`

Runs inference only.

```bash
python run_evaluation.py run --dataset cmu_arctic --max-recordings 5 --augmentation none --simulation-mode perfect
```

### `score`

Scores an existing run folder that already contains `predictions/utterances.jsonl`.

```bash
python run_evaluation.py score --run-dir "runs/20260416_181346_cmu_arctic_full_cmu_reverb_noise_smoke"
```

### `report`

Builds plots and a Markdown report from existing metrics.

```bash
python run_evaluation.py report --run-dir "runs/20260416_181346_cmu_arctic_full_cmu_reverb_noise_smoke"
```

### `full`

Runs selection, augmentation, inference, scoring, plots, and report generation.

```bash
python run_evaluation.py full --dataset hifitts --reader-split 6097_clean --augmentation noise --noise-type pink --snr-db 15 --max-recordings 10 --simulation-mode noisy
```

AMI close-talk simulation:

```bash
python run_evaluation.py full --dataset ami --stream-type headset --meeting-id IS1000a --max-recordings 25 --simulation-mode perfect --run-name ami_headset_smoke
```

AMI far-field simulation:

```bash
python run_evaluation.py full --dataset ami --stream-type array --stream-id Array1-01 --max-recordings 25 --simulation-mode noisy --run-name ami_array1_noisy
```

AMI real-run stub path:

```bash
python run_evaluation.py run --dataset ami --stream-type headset --max-recordings 25 --runner external-stub --run-name ami_external_manifest
```

CHiME-6 close-talk simulation:

```bash
python run_evaluation.py full --dataset chime6 --split dev --session-id S02 --stream-type participant_close --max-recordings 25 --simulation-mode perfect --run-name chime6_s02_close
```

CHiME-6 far-field microphone simulation:

```bash
python run_evaluation.py full --dataset chime6 --split dev --session-id S02 --stream-type farfield_array --microphone-id U01_CH1 --max-recordings 25 --simulation-mode noisy --run-name chime6_s02_u01ch1
```

CHiME-6 real-run stub path:

```bash
python run_evaluation.py run --dataset chime6 --split dev --session-id S02 --stream-type farfield_array --max-recordings 25 --runner external-stub --run-name chime6_external_manifest
```

VOiCES native far-field simulation:

```bash
python run_evaluation.py full --dataset voices --split test --room rm1 --distractor none --position far --max-recordings 25 --simulation-mode perfect --run-name voices_rm1_none_far
```

VOiCES room/distractor sweep:

```bash
python run_evaluation.py full --dataset voices --subset room=rm1,rm2 --subset distractor=musi,babb,tele,none --max-recordings 50 --simulation-mode noisy --run-name voices_condition_sweep
```

VOiCES real-run stub path:

```bash
python run_evaluation.py run --dataset voices --room rm1 --position far --max-recordings 25 --runner external-stub --run-name voices_external_manifest
```

## Run Folder Contents

Each run creates:

```text
runs/<timestamp>_<dataset>_<command>[_run_name]/
  run_config.yaml
  dataset_selection.json
  dataset_selection_records.jsonl
  dataset_selection_source_records.jsonl
  augmentation_config.json
  predictions/
    utterances.jsonl
    runner_summary.json
    <condition_id>/
      utterances.jsonl
  metrics/
    aggregate_metrics.json
    per_recording_metrics.csv
    gender_metrics.csv
    <dataset_group>_metrics.csv
    speaker_label_confusion.csv
    segment_speaker_metrics.csv
    segment_speaker_summary.json
    augmentation_condition_id_metrics.csv
    augmentation_mode_metrics.csv
    snr_db_metrics.csv
    rir_label_metrics.csv
    noise_type_metrics.csv
    missing_predictions.csv
    <condition_id>/
      aggregate_metrics.json
      per_recording_metrics.csv
  plots/
    wer_histogram.png
    substitutions_histogram.png
    worst_recordings.png
    worst_recordings_by_substitutions.png
    speaker_label_confusion_summary.png
    <dataset>_<group>_summary.png
  logs/
    evaluation.log
  report/
    report.md
    summary.json
  preview_audio/
    preview_manifest.json
    <condition_id>/
      *.wav
```

Some files are conditional. For example, `preview_audio/*.wav` appears only
when preview audio is generated, and `snr_db_metrics.csv` appears only for
noise runs. Root-level `predictions/utterances.jsonl` and root-level metrics are
kept for backward compatibility, while condition-specific copies make
multi-condition runs easier to inspect.

Temporary augmented inference files are created under condition-specific folders
inside `temp_audio/` during a run and removed automatically after each inference
call.

## GUI Validation Harness

The GUI state and command serialization can be tested without opening a window:

```bash
python -m app.gui.validation_harness
```

That checks:

- smart-control visibility for augmentation choices
- the RIR selector height constant stays bounded
- the subset dropdown height constant stays bounded
- the main GUI form uses a scrollable container
- subset options are populated from real normalized metadata
- cleared subset dropdowns can be validated without stale Tk widget crashes
- multi-select filter serialization uses comma-separated `--subset` values
- grouped metrics include all valid observed values for CMU Arctic gender,
  LibriSpeech split, HiFiTTS reader_split, and augmentation conditions
- AMI filter option loading and AMI augmentation blocking
- VOiCES filter option loading and VOiCES augmentation blocking
- CHiME-6 filter option loading and CHiME-6 augmentation blocking
- `drop_some` missing prediction handling
- multi-dataset GUI batches continuing when runs finish with missing-output warnings
- SNR parsing and validation
- invalid input blocking
- multi-dataset command generation
- simulation command generation
- per-dataset filter serialization

To also prove the GUI batch launcher goes through the real evaluation pipeline,
run the optional smoke test:

```bash
python -m app.gui.validation_harness --run-smoke
```

The smoke test launches a one-record, two-condition CMU Arctic `full`
simulation through the same subprocess path used by the GUI, verifies
`predictions/<condition_id>/`, `metrics/<condition_id>/`, and full-dataset
grouped metric files such as `gender_metrics.csv` and `accent_metrics.csv`,
then generates preview audio independently from a full run and verifies
`preview_audio/<condition_id>/`. It also launches tiny AMI, VOiCES, and
CHiME-6 simulations with augmentation disabled and verifies their
dataset-specific group outputs. Finally, it launches a two-dataset `drop_some`
batch and verifies that both runs finish, save `missing_predictions.csv`, write
missing-prediction counts into aggregate metrics, and still build plots and
reports.

## Metrics

Per-recording metrics include:

- WER
- substitutions
- insertions
- deletions
- reference word count
- hypothesis word count
- duration
- augmentation condition fields
- reference and predicted speaker labels where available
- speaker label agreement where available

Aggregate and grouped metrics include:

- file count
- total duration
- aggregate WER
- substitutions
- insertions
- deletions
- missing prediction count
- missing prediction rate
- processed prediction count
- speaker label accuracy when speaker labels are present

Grouped summaries are written when fields exist, including:

- AMI: `stream_type`, `stream_id`, `meeting_id`, `meeting_type`, `visibility`, `seen_type`, `speaker_global_name`, `speaker_role`, `agent`, `gender`
- CHiME-6: `split`, `session_id`, `stream_type`, `speaker_id_ref`, `recording_speaker_id_ref`, `device_id`, `channel_id`, `microphone_id`, `ref_device`, `location`, `location_hint`
- CMU Arctic: `gender`, `accent`, `accent_group`, `speaker_variant_group`
- LibriSpeech: `split`, `subset_group`, `gender`, `speaker_id`, `chapter_id`, `book_id`
- HiFiTTS: `split`, `reader_split`, `clean_vs_other`, `gender`, `reader_id`, `audio_quality`, `book_id`
- VOiCES: `split`, `room`, `distractor`, `mic`, `device`, `position`, `degrees`, `gender`, `speaker_id_padded`, `chapter_id`, `segment_id`, `distance_foreground_class`, `stoi_class`, `pesq_wb_class`, `srmr_class`
- augmentation condition
- augmentation mode
- SNR
- selected RIR
- noise type

When no subset filters are selected, the run is treated as a full-dataset run
and all relevant grouped summaries above are produced automatically wherever
the corresponding metadata columns exist. If subset filters are selected, the
same grouping logic runs on the filtered selection.

### AMI Metrics In This Phase

AMI support is intentionally transparent and incremental:

- `utterances.jsonl` is scored against normalized AMI segment text using the
  same WER-style transcript comparison as other datasets.
- `speaker_label` in `utterances.jsonl` is compared against the normalized AMI
  reference speaker label, producing speaker label accuracy and
  `speaker_label_confusion.csv`.
- If `predictions/segments.rttm` exists, each reference segment is matched to
  the predicted RTTM segment with the largest time overlap. The tool saves
  `segment_speaker_metrics.csv` and `segment_speaker_summary.json`.

This is not yet full diarization error rate. It is a robust first AMI pass for
speaker-attributed transcript and segment-overlap checks, with the files laid
out so DER-style scoring can be added later.

### CHiME-6 Metrics In This Phase

CHiME-6 support projects each normalized session-level utterance onto concrete
audio streams. Far-field array streams receive all utterances for the session.
Participant close-talk streams receive only the reference utterances for the
matching participant.

The scorer compares `utterances.jsonl` text against normalized CHiME-6
utterance text, compares predicted `speaker_label` against `speaker_id_ref`,
and writes speaker label accuracy plus `speaker_label_confusion.csv`. If
`predictions/segments.rttm` exists, the same largest-overlap segment speaker
check used for AMI is run.

Grouped CSVs and plots are produced for split, session, close-talk vs far-field
stream type, reference speaker, participant-close recording speaker, device,
channel, microphone id, reference device, and location. This is a transparent
first pass for speaker-attributed conversational scoring, not full diarization
error rate yet.

### VOiCES Metrics In This Phase

VOiCES support treats each row as one native far-field, single-speaker
utterance. The inference input is the normalized `distant_audio_path`; the clean
`source_audio_path` is preserved in manifests for traceability, but no synthetic
augmentation is applied.

The scorer uses the same transcript comparison as the clean datasets and writes
condition grouped CSVs and plots for room, distractor, mic, position, angle,
gender, speaker, and derived quality/distance classes. These groups are meant
for native robustness analysis, such as comparing WER across rooms or
distractor conditions.

## Path Rebasing

Normalized parquet files may contain absolute paths from the computer that
created the metadata. The tool rebases paths through stable project anchors:

- `Raw Datasets (Not formatted)`
- `Normalized Metadata`

RIR paths also use project-root-relative resolution, so commands can be moved to
another machine with the same project layout.

## Extending Datasets

To add another clean single-speaker transcription dataset later:

1. Add a `DatasetDefinition` in `app/dataset_registry/registry.py`.
2. Point it at normalized `recordings.parquet` and `utterances.parquet`.
3. Declare reference transcript columns and speaker/gender columns.
4. Declare subset filters and group metric columns.
5. Validate `--augmentation none`, then `noise`, then `reverb`.
6. Validate `--simulation-mode perfect`, `noisy`, and `drop_some`.

For another meeting or diarization-style dataset, start from the AMI registry
entry: set `supports_augmentation=False`, define speaker-attribution group
columns, and keep `utterances.jsonl` plus optional `segments.rttm` as the first
prediction contract.

For another native robustness dataset, start from the VOiCES registry entry:
set `supports_augmentation=False`, point `audio_path` at the recorded condition
audio, and declare condition columns as group metrics.

Full DER scoring and corpus-scale persistent augmentation are not part of this
phase.
