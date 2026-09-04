# XVF3800 future interface for H2

## Current status

XVF3800 evidence is not used by the current scientific configuration. The implemented `spatial-evidence-interface.v2` and `xvf3800-spatial-evidence.no-effect.v2` placeholder record availability and return an event-equivalent copy. All result-effect flags are false, including explicit flags proving that supplied values and absent/default evidence cannot change results.

No current accuracy, identity, latency, or hardware claim depends on energy, activity, angle of arrival (AoA), or processed XVF audio.

## Timestamp contract

Every future metadata frame must carry a finite non-negative session/source timestamp aligned to the same monotonic audio timeline used by ASR, segmentation, identity, and transcript events. Capture-clock to source-clock conversion, drift correction, missing-frame behavior, and maximum alignment error must be versioned and measured.

The canonical v2 evidence-frame fields are:

- `timestamp_sec`;
- `source_clock`;
- `aoa_deg`;
- `aoa_confidence` in `[0, 1]`;
- `speech_energy`;
- `speech_activity`;
- `direction_change_deg`;
- `beamformer_state`;
- `channel_state`;
- `available`;
- `quality_flags`.

The v1 constructor aliases `energy`, `angle_of_arrival_deg`,
`angle_confidence`, and `direction_change` remain accepted for source
compatibility, but canonical serialization emits only v2 fields. Conflicting
canonical and legacy values fail closed. The legacy boolean
`direction_change` is not silently converted into a numerical angle change.

Future processed-audio identity or any result-affecting use of these fields
requires a new, separately frozen schema and runtime identity. Merely supplying
a v2 frame never activates spatial fusion.

## Intended insertion points

| XVF signal | Future insertion point | Candidate use | Required safety gate |
|---|---|---|---|
| Processed/beamformed audio | before the common 16 kHz frame source | ASR, speech coverage, embeddings | matched raw-vs-processed development and untouched evaluation |
| Energy/activity | segmentation evidence adapter | reduce false alarms/misses or wake processing | timestamp parity and no missed-speech safety regression |
| AoA + confidence | anonymous cluster continuity and active roster | split/merge support, re-entry, seat continuity | confidence gate, missing-data fallback, identity safety study |
| Direction change | boundary/cluster transition evidence | inhibit a stale merge or trigger reconfirmation | causal timing and false-trigger analysis |
| AoA conflict | identity-memory guard | prevent stale-name inheritance/force release | must only make naming more conservative until separately validated |

Spatial evidence must be additive and independently gated. Audio-only behavior remains the fallback and a frozen comparator. AoA must never be treated as a person identity.

## Required future ablations

1. audio only;
2. audio + energy;
3. audio + AoA;
4. audio + energy + AoA;
5. XVF processed audio only;
6. XVF processed audio + metadata.

Use leakage-safe development/calibration/evaluation recordings from the actual device and room conditions. Do not infer real-device performance from synthetic metadata.

## Hardware handoff

Before enabling result effects, capture exact XVF firmware/settings, channel format, device clock, sample-rate conversion, transport latency, dropped metadata, and microphone geometry. Validate restart/reconnect, timestamp drift, continuous streaming, and absent/low-confidence metadata. Any policy that changes decisions receives a new runtime identity and reruns the frozen tests.
