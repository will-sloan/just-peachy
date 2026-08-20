# Frozen speaker enrollment-duration protocol

Protocol ID: `speaker_enrollment_duration_v1_8ee8b2aa42d1`
Source protocol ID: `commonvoice_60plus_v1_27e72793b4c0`

This package contains only deterministic manifests, provenance, feasibility evidence, and checksums. It contains no audio, embeddings, model assets, or identity reverse map. The source is Common Voice prompted/read speech; every duration is available waveform duration beginning at the source-file start, not measured voiced-speech duration.

The primary paired cohort contains 221 known speakers, 47 calibration Unknown speakers, and 92 evaluation Unknown speakers. Each retained speaker supplies three independent source probe parents per applicable partition, and every parent supports all nested prefixes through 5.0 seconds. Known speakers also support all five source enrollment clips and 20.0 seconds of accumulated enrollment audio.

The proposed optional 10-second probe is not in v1 because no known speaker supports three 10-second calibration parents, three 10-second evaluation parents, and the 20-second enrollment requirement simultaneously. It remains visible in `feasibility_audit.json`. Phase D requires an explicit reference enrollment configuration chosen after earlier-phase analysis. Phase E requires an explicit operator decision gate; no product threshold or duration is selected automatically.

Use `app/speaker_enrollment/README.md` and `scripts/run_speaker_enrollment_study.ps1` for Anaconda Prompt, Command Prompt, PowerShell, inputs, outputs, and restart-safe execution.
