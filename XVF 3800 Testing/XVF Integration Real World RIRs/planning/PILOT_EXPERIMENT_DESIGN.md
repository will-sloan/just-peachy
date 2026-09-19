# Pilot experiment and fixed-source policy

**Hardware update — 6 September 2026:** keep KRK volume, LF/HF EQ, ARC state/configuration, Windows/interface output level, software level and physical orientation fixed for formal measurements. Optional EMM-6 recordings are archived separately for later mismatch analysis. No speaker correction or deconvolution is required now. See [current project context](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/PROJECT_CONTEXT.md>) and [GUI guidance](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/MEASUREMENT_GUI_GUIDE.md>).

This continues workbook V4 sections 7–10 and its P1/P2 sequence. It does not change the original Word document. The user now uses the onboard four-microphone linear array, has removed all external microphone connections, and intends to keep the KRK GoAux 4 volume, bass and treble constant.

## Freeze the source, preserve the received differences

Record the exact speaker model label, one active cabinet, wired input, volume/bass/treble marks or photos, source WAV hash, application scalar and output path. Keep these fixed throughout a measurement series. The source emits the same waveform and level at every position; room, table, placement, orientation and propagation may change the received level and spectrum. Those changes are measurements. Do not equalize each seat, normalize individual microphones or align them separately.

A preliminary two-level check uses two software scalars 6 dB apart with the hardware dials unchanged. This is an excluded setup trial to identify compression and usable level. Then select one scalar and freeze it for the actual series. Without a calibrated microphone, the reference is relative and uncalibrated in SPL.

## Establish one usable reference setup

1. Identify the microphone openings and board forward arrow. Firmware coordinates are not automatically laboratory coordinates. The stock pitch is 33.3 mm; preserve the stock four-microphone linear firmware.
2. Define room origin and axes. Follow the workbook laboratory convention: +X forward, +Y device-left and +Z up; positive azimuth is counter-clockwise viewed from above. Photograph the board and source with those arrows visible.
3. Record source center XYZ, height, distance, facing yaw/pitch, array center XYZ, height, yaw/pitch/roll, surface/table, clutter and device pose. Mark measured versus estimated values. Unknown values stay blank/null, not zero.
4. Use the shared XVF playback clock through LINE OUT to one KRK GoAux 4 RCA input/cabinet. The default DAC duplicates the left reference on both output sockets; verify the other cabinet is silent. The app cannot verify the cable or cabinet acoustically by name.
5. Record a quiet baseline, then controlled speech from known front and side positions. Keep these separate from sweep measurements. Check native direction behavior, front/rear ambiguity, channel levels and telemetry timing; do not assume a sweep produces valid speech direction.
6. Complete the [relative speaker-level checklist](SPEAKER_CALIBRATION_CHECKLIST.md). Use raw Category 1 or amplified Category 3 consistently. Category 3 matches the workbook's injection-domain preference; retain its common gain and delay in the record.

## Small pilot before a full matrix

| Stage | Capture | What it establishes |
|---|---|---|
| Excluded setup | Quiet baseline; two-level sweeps at unchanged geometry | Noise, clipping/headroom, useful band, marker recovery and source compression check |
| Direction mapping | Fixed-position phone speech at measured front/side/rear positions, with board stationary | Native angle convention, ambiguity and response behavior; no absolute angular accuracy claim without measured truth |
| P1 first pair | Two identical front-position ESS takes, unchanged cabinet/pose/level | Repeatability of the four-channel acoustic path and common timing |
| P2 physical HIL | One to five utterances through accepted four-channel RIRs, then actual XVF injection | Reproducible RIR-to-XVF processing chain before H2 use |
| Expanded P1 matrix | Workbook source positions, FLAT/UPRIGHT poses, NAT/TOW facing and repeats | Effects of the intended experimental factors after the first pair passes |

Use the workbook trial labels, for example `JPXVF_P1_R01_T01_D01_S01_F00_NAT_C0_R01` and the corresponding `R02`. The software also assigns a unique timestamped take ID; the human trial label and take ID serve different purposes. Retakes get new take IDs and a note linking the failed attempt.

Hold speaker controls and signal level constant while varying the planned geometry factors. Keep unchanged repeats adjacent during initial qualification. For the larger campaign, balance/randomize condition order within practical placement blocks and revisit the same reference geometry at the start and end of a session. Record each movement and geometry revision. Do not mix an unnoticed geometry change into a claimed repeat.

## Acceptance before expansion

- All four microphone recordings must be nonzero and varying, free of clipping and zero windows. The native packed framing and known digital continuity signal must pass.
- Verify actual USB24 readback and 23-bit payload. A PCM24 file alone is not proof of genuine device precision.
- Review telemetry count, request/response intervals, gaps, errors and coverage over the audio. Host timestamps are not device sample timestamps; angle and energy reads are not a proved atomic pair.
- For acoustic takes, identify all three marker responses, verify end-marker separation and whole-take timing, and inspect multipath. Preserve common channel timing. Never correct an unexplained playback discontinuity with a blanket drift resample.
- Inspect frequency-dependent sweep SNR and decay. Establish numerical repeatability tolerances from repeated reference takes before accepting or rejecting the later condition matrix.
- Extract and inspect four common-time-base RIRs before accepting P1. Electrical-source deconvolution contains speaker + room/table/objects + microphone/board/capture response. Final RIR extraction, absolute calibration and HIL are subsequent qualification steps; the recorder's PASS label alone does not complete them.

The original recordings, failed takes, stimulus and setup records remain unchanged. Any later common trim, clock correction, gain-domain conversion or deconvolution is a separately saved derived artifact with its parameters and source hashes.
