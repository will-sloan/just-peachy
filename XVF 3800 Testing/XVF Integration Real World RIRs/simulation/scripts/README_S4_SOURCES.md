# S4 Common Voice source adapter

`s4_sources.py` discovers and prepares a bounded Common Voice cohort for the S4 RIR scene bank. It is offline software and never opens the XVF, changes H2, downloads audio, regenerates a corpus index, or normalizes an RIR. Run the scene generator only with sources whose `split` is `development` and `usage` is `probe`.

The adapter reads the existing Common Voice 26.0 (2026-06-12), English, older-age materialization under `Software Validation from Datasets\Raw Datasets (Not formatted)\Common Voice\cv-corpus-26.0-2026-06-12\prepared\en`. The native `README.md` supplies release identity, native field descriptions, and the CC0/no-identity-determination terms. The existing SQLite index provides candidate transcripts, contributor IDs, upstream split and prior source-byte hashes; `verify` independently checks every selected record against native `validated.tsv`.

Before audio quality checks, the adapter freezes three downstream-reserve contributors and a deterministic priority list of development contributors. It excludes all 413 contributors in the pre-existing frozen `commonvoice_60plus_v1` protocol, protecting its known/calibration/evaluation assignments. Stable contributor IDs are hashed in a release-independent namespace; raw IDs are not exported. This metadata grouping does not determine real-world identity, prove that accounts are different people, or prove the pretrained models have never encountered the data.

The completed shortlist contains six development contributors, each with four whole-clip probes and one separate enrollment candidate, plus three reserve contributors with three clips each. It decodes 40 short MP3 clips and accepts 39. Six development contributors alone meet the requested overall cohort size, so no supplemental corpus is used. Actual scene contribution is reported by the downstream scene manifest, not implied by inclusion here.

## Inputs and outputs

Inputs are the named existing source root, its read-only `state\common_voice_phase3.sqlite3`, native release metadata and materialization receipt, the frozen historical `source_selection.tsv`, and only the selected MP3 files. Paths derive from this script's location; no environment installation is needed.

Outputs live in `simulation\staging\s4_sources`:

- `SOURCE_AND_SPLIT_MANIFEST.json`: source IDs, pseudonymous contributor IDs, roles, source bytes/hashes, native decoded characteristics, transcripts, level/activity estimates and decoded WAV bindings.
- `SPLIT_FREEZE_BEFORE_AUDIO_QC.json`: original assignment time, priority and protected historical protocol binding.
- `decoded_16k\*.wav`: mono 16 kHz FLOAT32 clips at original numerical amplitude after one rational resample. Gain is exactly 1 here.
- `SHORTLIST_QUALITY.json`: accepted clips and the rejected candidate with reasons/metrics.
- `SOURCE_ADAPTER_TESTS.json` and `SOURCE_NATIVE_METADATA_VERIFICATION.json`: reproducible regression and native-row verification receipts.
- `SOURCE_CALIBRATION_QC.json` and `SOURCE_CALIBRATION_WAVEFORMS.png`: bounded envelope/end-margin review for the first two probes of the initial A/B contributors. These are local QC artifacts, not an acoustic dryness certificate.

The source interface is `sources[]`: `source_id`, `identity`, `split`, `usage`, `decoded_16k_binding.path`, `decoded_16k_binding.sha256`, `samples`, `duration_sec`, `transcript`, and `quality.active_rms`, `quality.peak`, `quality.active_ranges_samples_estimated`. Entire clips and transcripts stay together. Enrollment/reserve clips must never be scheduled as S4 probes.

## Run in PowerShell

```powershell
$s4SourceScript = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s4_sources.py'
& 'C:\Users\amiri\anaconda3\python.exe' $s4SourceScript test
& 'C:\Users\amiri\anaconda3\python.exe' $s4SourceScript prepare
& 'C:\Users\amiri\anaconda3\python.exe' $s4SourceScript verify
& 'C:\Users\amiri\anaconda3\python.exe' $s4SourceScript calibration-qc
```

## Run in Anaconda Prompt or Command Prompt

```bat
"C:\Users\amiri\anaconda3\python.exe" "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s4_sources.py" test
"C:\Users\amiri\anaconda3\python.exe" "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s4_sources.py" prepare
"C:\Users\amiri\anaconda3\python.exe" "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s4_sources.py" verify
"C:\Users\amiri\anaconda3\python.exe" "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s4_sources.py" calibration-qc
```

`prepare` resumes a completed compatible shortlist by rechecking every selected source and decoded-file hash. It refuses changed bytes. If preparation was interrupted before final manifest completion, rerunning uses the same frozen contributor ledger and deterministic candidate order. Do not remove or overwrite the freeze to chase recognition results; result-affecting selection changes require a new versioned staging location and explicit preservation of this manifest.

## Quality and dry-level policy

The activity estimator computes non-overlapping 20 ms frame RMS, then accepts frames at or above the larger of −50 dBFS RMS and the 95th-percentile frame RMS minus 25 dB. Active RMS is the RMS of those full frames. The trailing partial frame is excluded from the estimator, but preserved in the audio. Activity ranges are estimates for preparation/scoring, not phonetic boundaries and not H2 metadata.

Shortlist checks reject clips outside 2.7–6.6 s after decoding, less than 1.2 s estimated activity, active RMS below −36 dBFS, numerical overrange or more than three samples at absolute amplitude ≥0.999 (or a run longer than two), absolute DC above 0.01, or frame p95/p10 contrast below 12 dB. These are fixed source usability checks selected before S4 device/model results. They do not certify absence of all background voices or strong pre-existing echo; no listening review, denoiser, quality model, or independent acoustic calibration is claimed. MP3 codec, recording-device and source-domain limitations remain visible in the manifest.

This adapter does not freeze/apply the final dry-source level policy. The coordinator's calibration proposal is one preconvolution gain `min(10**(-24/20)/active_rms, 0.5/peak)`, with uncapped RMS boost above 12 dB rejected, followed by declared relative scene contrasts. A peak-limited source may fall below the RMS target. No source-by-source or microphone normalization happens after convolution. The coordinator must freeze `SOURCE_LEVEL_POLICY.json` and record the applied scalar in final scene/source manifests before final capture.

All 39 selected sources have unique source-byte and decoded-PCM hashes; this is a bounded exact-duplicate check, not a whole-corpus near-duplicate search. Development and reserve contributors do not overlap. Self-reported age/accent fields describe this small selection only. Native metadata does not provide dependable session/microphone separation or exact spoken-word timestamps.
