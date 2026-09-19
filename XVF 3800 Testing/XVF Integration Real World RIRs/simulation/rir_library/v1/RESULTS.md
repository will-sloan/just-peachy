# Complete 121-record RIR library

**Completed:** EXTRACTED: 95; EXTRACTED_WITH_LIMITATIONS: 26; FAILED: 0. All 121 active IDs are accounted for. There is one canonical four-channel WAV per successful recording in C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\rir_library\v1. RIR_MANIFEST.json defines this library; S1 alternatives remain untouched historical evidence.

## Scope and checks

Five rooms, 51 metadata geometry groups; 121 active after six exact Loeb Caf exclusions, with 52 historical exclusions preserved. Upper Loeb is retained. Neither excluded audio nor its quiet windows was used. Original acquisition statuses remain unchanged. Effective distances span 0.46–4.07 m. Both bound 100 m → 1.00 m corrections, signed central angles, ±5° conservative user uncertainty, qualitative room context and unknown geometry remain in the manifest.

All final targeted controls passed (60/60); library validation passed 1586 checks, including exact ID coverage, consumed-input bindings, header/data/WAV hashes, finite nonzero four-channel outputs, retained early channel delays and one fresh real-record numerical regeneration. Same-sweep reconstruction is internal consistency, not independent validation. Per-record results and failures are in RIR_SUMMARY.csv and RIR_MANIFEST.json.

## Final practical policy

The tested S1 reverse-sweep ESS inverse and scaling are retained. The exact archived 48 kHz excitation is resampled with the existing antialias filter and uses the recorded −6 dB software scalar exactly once. The transfer maps numerical post-software-gain drive to Category 3 captured full-scale samples. Mic gain 10, SYS_DELAY −32 and unknown speaker/analog transfer are not undone or applied again. Cross-record gain is preserved; a half-amplitude synthetic recording recovered the expected −6.0206 dB energy-level change.

Timing now uses each record's multi-marker regression with an uncertainty interval and fractional-position marker-waveform coherence. The latter change only affects diagnostic snippets, never microphone alignment. Zero/±10 ppm controls recovered the injected clock within 0.04 ppm; integer-aligned coherence had incorrectly fallen near 0.495, and fractional comparison restores about 0.9985. The 3% concentration rule is removed as a mandatory gate: concentration is diagnostic, not independent clock truth. No blanket −10 ppm correction is used. Selected timing counts: {"PER_RECORD_MARKER_CLOCK": 102, "ZERO_WITHIN_MARKER_UNCERTAINTY": 10, "CONSERVATIVE_ZERO_FALLBACK": 9}. Inconclusive cases use zero and retain bounded sensitivity.

The one nominal output pass region is **110–7000 Hz**, with raised-cosine transitions **80–110 Hz** and **7000–7300 Hz**. A symmetric 2049-tap Kaiser FIR and source-only ridge attenuation form a bounded common weighting; weak source bins are never inverted/boosted. The filter-only ±0.1 dB region for the first record is about 116.3–7000.0 Hz. Individual supported intervals are reported separately from this chosen weighting.

The existing pilot supports expansion beyond S1's 160–6400 Hz cutoffs. Source self-transfer becomes irregular near 80 Hz and falls sharply above 7300 Hz; the existing 48→16 kHz antialias filter is about −14.1 dB at 7500 Hz. Claiming full 80–7500 Hz recovery would require unsupported edge inversion. Weak local bands flag that record rather than narrowing every output. This was one bounded edge assessment and one final filter design, not a parameter search.

Noise uses the verified 1.25-second pre-marker interval. Post-sweep audio is never labeled noise-only. Shared tail handling retains the last any-channel 20 ms block above four times a conservative floor, adds 40 ms margin and a 60 ms cosine taper. The floor may include weak real late decay; lost finite-core energy is quantified, and no clean tail is invented. The unused S1 consecutive-noise-duration config field was removed. Each output keeps about 50 ms before significant energy under one common origin; removed bulk latency is inseparable from device/propagation/capture offset. Do not add a guessed distance/c delay.

Durations are **0.5106–2.0507 s**. These are stored windows, not RT60. Maximum crop/taper energy removal was 0.0845% of the already weighted finite core; maximum relative interchannel energy-level change was 0.00165 dB. This does not quantify energy outside the chosen band or finite captured horizon.

## Specific limitations and next physical proof

Limitation counts (overlap allowed): {"LOCAL_FREQUENCY_INTERVALS_BELOW_SUPPORT_RULE": 19, "CLOCK_EVIDENCE_INCONCLUSIVE_ZERO_FALLBACK": 9, "CLOCK_UNCERTAINTY_MATERIALLY_AFFECTS_SPATIAL_METRICS": 1}.

120 outputs can proceed as inputs to a later HIL proof within their declared bands/tails/uncertainties. Physical replay itself has not been tested. The following outputs retain a material clock-sensitive spatial limitation and should first resolve that timing uncertainty before spatial HIL proof:

- JPXVF_P1_R02_T01_D01_S02_F00_NAT_CU_R13

These limited responses remain canonical exports for offline inspection/use within their stated scope; they were not fabricated or relabeled as fully spatially qualified. No H2/GUI/model/threshold changes, XVF access, conversation synthesis, training, CM5 work, commit or push occurred.

## Runtime, storage and reproducibility

Full extraction: 204.36 s with four CPU workers and one inner thread, approximately 35.53 records/min. Final controls: 30.94 s. Task elapsed through this report: 12.9 minutes including implementation, investigation and validation.

Observed 15-second-sampled process-tree RSS maximum: 0.668 GiB; minimum sampled available RAM: 32.90 GiB. These are sampled observations, not instantaneous peaks or OS-enforced hard caps. Owned workers exited. Canonical WAV storage: 20.97 MiB. Fresh free space: C: 82.13 GiB free; G: 449.30 GiB free; D: 1062.78 GiB free; F: 46.24 GiB free. All work remained on C: above the 50 GiB reserve; no data relocation was needed.

One source-power FFT truncation bug was caught by the expanded-band synthetic regression before policy freeze; it was fixed without changing the test threshold. A first small-clock policy also failed the coherence control. Failed development receipts and the successful final controls are preserved in the handoff evidence. No canonical RIR was produced under either failed policy.

Use library README.md and simulation/S2_README.md for exact PowerShell and Anaconda/Command Prompt commands. Rerun skips successful receipts only when inputs, code, config, scope and output hashes match. New methods/inputs require a new report and library version. The handoff includes canonical WAVs, the manifest/configuration, concise report, compact plots, small code/test evidence and a checked hash inventory; original captures, historical alternate WAVs, NPZ scratch, weights and vendors are excluded.
