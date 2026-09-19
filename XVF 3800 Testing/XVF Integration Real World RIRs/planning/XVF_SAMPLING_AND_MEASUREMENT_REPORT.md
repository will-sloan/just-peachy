# XVF3800 measurement qualification — 5 September 2026

The four onboard linear-array microphones are functional in the tested recordings. The zero-microphone blocker remains cleared after removal of all external connections. This work establishes genuine 24-bit transport, distinguishes raw and amplified signals, measures the fastest implemented direction/energy logger, and builds a local recorder with source/pose records and per-take integrity checks. It does not certify every electrical component or latent damage.

The original Word workbook is unchanged. This report and the revised Section 6 guide record what has actually been tested; the supplied documents are technical references, not authority to perform unrelated actions.

## Device contract and measurements

| Property | Documentation / interpretation | Observed evidence |
|---|---|---|
| Firmware and topology | Official 3.2.1 `ua-io48-lin`, four-mic linear geometry | Identity readback before every take; physical-input mode and normal array selection checked |
| Microphone rate | **16,000 samples/s per microphone** | Six 16 kHz channels decoded from stereo 48 kHz carrier with 0,1,1 framing |
| USB width | 24-bit transport uses one marker bit, leaving **23 numerical audio payload bits** | Explicit USB24/24 readback; independent byte decoder equals saved audio; low audio bytes vary. This is not a claim of 23-bit acoustic effective resolution |
| Geometry | 33.3 mm adjacent pitch; native X coordinates −49.95, −16.65, +16.65, +49.95 mm | Firmware geometry readback agrees. Physical label/room-axis verification still needs a measured setup/photo |
| Raw Category 1 | Before common mic gain and system delay | Captured with all four channels; unchanged relative timing retained |
| Amplified Category 3 | Fixed gain/delay before SHF/AEC processing | Simultaneous MIC0–2 raw/amplified pairs fit approximately **10× gain and 32-sample (2 ms) delay**; independent affine gain fits 10.000028, 9.999996, 9.999983. All four amplified channels additionally exercised in long captures |
| Processing cadence | 256 samples / 16 kHz = **16 ms, 62.5 frames/s** | Fast queued full-array angle and energy queries each approach this rate during capture |
| Direction semantics | Beam angles are native radians; linear array has front/rear ambiguity | Full four-value arrays retained. No measured laboratory-angle accuracy or guaranteed new estimate on every reply is claimed |
| Energy semantics | Vendor speech-energy values | Retained without relabeling as SPL, power or distance. Quiet/sweep segments can legitimately give zero or held estimates |

The selected-output DoA is additionally gated/smoothed. The source requires more than ten qualifying frame changes before accepting a jump, then applies an EWMA factor of 0.825. Faster host polling cannot remove that algorithmic response delay. The default tool therefore logs the full beam-angle and speech-energy arrays; the optional selected-angle mode uses the slower official CLI backend.

## Telemetry speed

The ordinary persistent official CLI measured about **31.25 replies/s per field** for two AEC fields. A queued adapter using the official 32-bit XMOS transport/command-map libraries measured **62.27 angle arrays/s and 62.25 energy arrays/s** concurrently with a clean 60-second PCM24 recording. Median intervals were approximately 16 ms; 95th-percentile intervals were 16.64/16.65 ms. Worst gaps in that test were 65.9/105.3 ms.

Each array has four beam values. These rates describe successful host reads, not four independent sound sources, a uniform sample clock, an atomic angle/energy snapshot or guaranteed fresh algorithm estimates. Every transfer has host request/response bounds and raw bytes; the documented replies contain no device frame counter or sample timestamp. The UI refreshes about once a second independently of acquisition.

The first 300-second stress run returned 18,850 complete pairs at 62.04 Hz per field with no protocol errors, but its audio continuity failed. A telemetry pass alone is insufficient to accept a recording.

## Capture and playback findings

- **True PCM24 domain-pair test:** independent decoding, framing, gain/delay fit and unclipped samples passed. Merely requesting an int24 stream while the board was still USB16 had earlier widened 16-bit data; that failed attempt remains preserved.
- **60-second PCM24 concurrent capture:** all four raw microphones varied; framing, driver flags and the complete 58-second active digital sequence passed. No internal sample repair was applied.
- **Stop/recovery:** a deliberately stopped 300-second request retained approximately 5.36 seconds, reported RETAKE, restored settings and allowed a new take. Its incomplete continuity sequence correctly failed completion QC.
- **First 300-second PCM24 amplified stress run:** all four channels stayed nonzero and unclipped, but 2,942 continuity samples were wrong in one interval beginning at decoded 77.6764 seconds. Alignment moved by ±640 samples (40 ms) and then recovered. Driver callback flags remained clear. An 84.4 ms callback gap exceeded the 40 ms buffer margin, while telemetry continued normally. This is evidence of a host/transport scheduling problem; it is not evidence of a failed microphone. The take remains INVESTIGATE.
- **Playback detector correction:** the V2 pack generates distinct start/end bursts and separately generated 16/48 kHz marker assets. The detector now derives templates from the exact played 48 kHz file, uses four-channel evidence and checks both short and whole-take intervals. It never treats ambiguous peaks as a valid drift correction.
- **Initial Realtek sweeps:** microphone capture passed digital checks, but acoustic timing did not. R1 had a clear 200 ms end pair with approximately 95.9 ms extra start-to-end interval. R2's start remained ambiguous. Both originals remain RETAKE.
- **Realtek writer correction:** the installed WASAPI blocking writer does not report output underruns, so an empty error list did not prove uninterrupted playback. The replacement uses buffered callback playback with frame/timing/status receipts. Any startup or continuity failure is retained visibly.

The recorder now requests **150 ms** WDM-KS audio buffering and records the actual negotiated value. This trades monitoring latency for resilience to host scheduling delays; it does not change microphone rate or DSP cadence. Final retest results are recorded below when complete.

## Final integration retests

Two unchanged Realtek sweep rehearsals passed every implemented capture and marker gate: `TAKE_20260905T230151_422945Z_75f86c` and `TAKE_20260905T230252_188661Z_4a7b88`. Both captured all four amplified microphones with genuine USB24 and exact digital continuity. Both submitted and drained all 826,560 stimulus frames. The actual Realtek callback buffer was 160 ms; worst callback gaps were 21.04 and 20.95 ms. COM initialization and cleanup succeeded on the playback thread. Both recovered all three marker candidates with a **−0.125 ms whole-interval difference** from the nominal 14 seconds, and passed the end-pair gate.

These takes are deliberately **REVIEW**, not final calibrated RIRs. Their agreement verifies the revised integration and coarse timing checks at the laptop setup; it does not qualify Edifier geometry, frequency response, direct-path timing or absolute SPL. Earlier failed takes remain untouched. R3's playback startup failure was traced to missing per-thread COM initialization; a later preflight attempt encountered a transient command-log lock before recording. The latter now has bounded log-open retries that never repeat a board command.

The final **300-second buffered recording passed**, including an independent byte-level audit: `TAKE_20260905T230356_986366Z_0732ec`. It contains 14,400,000 native PCM24 frames and 4,795,127 decoded frames after the explicitly retained 304.56 ms startup exclusion. All four microphones varied, with no clipping or fully silent one-second windows. Every saved decoded/microphone WAV equals independently decoded native bytes. There were **zero framing errors and zero continuity mismatches across 4,792,422 compared samples**, covering the complete 298-second active test sequence. Actual WDM-KS input/output buffering was 150/150 ms. A 245 ms post-startup host callback gap occurred with intact sample continuity; a late callback alone does not prove sample loss.

The independent telemetry audit also passed: **18,237 complete angle/energy pairs, 59.726 Hz per field**, no protocol/cleanup errors and at most two pending read groups. Median intervals were approximately 16.02 ms; 95th percentiles were 20.58/20.49 ms and worst gaps 464.17/474.97 ms. Therefore the demonstrated readout range is **about 60–62 Hz per field, not a uniform real-time sample clock**. Keep these actual gaps in subsequent analysis. Only two energy arrays were positive in this quiet soak; it qualifies sustained transport, not continuous active-speech tracking or angular accuracy.

All **74 automated tests passed** against the final application source: 54 acquisition/marker/HTTP/archive/receipt tests, 12 callback/COM playback tests and 8 telemetry tests. Browser actions verified profile loading/saving, explicit source selection, capture, cancellation/recovery, visible result states and the archive. USB24 preparation also passed with the board already at 24/24, without a reboot or flash write.

## Software and experiment workflow

Open [Start-XVF-Measurement.cmd](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/Start-XVF-Measurement.cmd>) or the running [local recorder](http://127.0.0.1:8767/). The page supports raw/amplified four-mic capture, verified V2 impulse-marker-plus-ESS playback, fast telemetry, source XYZ/facing, array XYZ/yaw/pitch/roll, room/table/placement IDs, repeat labels, clutter, notes, photo references and saved profiles. Unknown geometry stays null. Each take has its own settings/source snapshot, original transport, decoded WAVs, command/telemetry receipts, quality results and SHA-256 manifest. Failed takes are kept.

The impulse-like burst is a timing marker; the 80–7500 Hz, ten-second exponential sweep is the primary RIR excitation. The two choices use a one- or two-second marker-to-sweep gap. This version automates capture and QC, not final calibrated RIR extraction or HIL generation.

USB24 preparation is a documented runtime command that restarts firmware, not a flash write. Use [Prepare-XVF-24bit.cmd](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/Prepare-XVF-24bit.cmd>) with streams stopped after a cold restart if the device reports USB16. It records the old configuration and restores mic gain, reference gain and system delay; other runtime parameters reset to firmware defaults. Rediscover audio devices after the restart and check settings before a campaign.

## Edifier setup and the next acceptance gates

The reported model is **Edifier bt1800**; the exact label remains unverified. The user will keep volume, bass and treble fixed. Record those existing marks/photos and hold the software scalar, output route and source WAV fixed as well. Received level/spectrum differences between positions are experimental results and must not be normalized away.

With no calibrated microphone, perform **relative level/reference setup**, not absolute SPL calibration. First use one wired cabinet at a measured reference placement; record a quiet baseline, a usable-level sweep and an excluded two-level compression check with hardware dials unchanged. Then freeze one digital level for all actual conditions. If the cabinet is R1800BT, its built-in DSP/DRC makes the linearity check especially relevant; neutral tone controls do not prove a flat or unprocessed speaker.

Prefer XVF LINE OUT into one Edifier RCA input. Official firmware uses only USB LEFT for its single AEC reference and duplicates that left signal onto both DAC sockets. The USB RIGHT continuity signal stays separate under the checked firmware/routing conditions. Verify that only one physical cabinet plays. This shares playback/capture clock; it still needs actual analog route, marker, level and repeatability checks with the Edifier connected.

Complete the [speaker checklist](SPEAKER_CALIBRATION_CHECKLIST.md) and [pilot design](PILOT_EXPERIMENT_DESIGN.md): establish microphone labels and laboratory axes, record real geometry, take two unchanged front-position P1 sweeps, inspect four common-time-base RIRs and repeatability, then proceed to the workbook's P2 physical HIL proof. Deconvolution includes speaker + room/table/objects + board/microphone/capture response. No absolute pressure, room-only response, calibrated angular accuracy, RT60/AEC accuracy or end-to-end H2 result is claimed by these transport tests.

## Sources and audit trail

- [Supplied-document/source findings](SAMPLING_AND_SPEAKER_FINDINGS.md), with precise manual sections and source lines.
- [Independent PCM24 review](TRUE_PCM24_INDEPENDENT_REVIEW.md).
- [Realtek playback implementation review](REALTEK_PLAYBACK_REVIEW.md), [marker review](LAPTOP_MARKER_REVIEW.md), [right-reference routing review](RIGHT_REFERENCE_ROUTING_REVIEW.md).
- Primary speaker and measurement sources: [Edifier R1800BT](https://www.edifier.com/us/p/bookshelf-speakers/r1800bt), [REW SPL calibration](https://www.roomeqwizard.com/help/help_en-GB/html/inputcal.html), [REW timing reference](https://www.roomeqwizard.com/betahelp/help/html/makingmeasurements.html), [Farina swept-sine paper](https://angelofarina.it/Public/Papers/134-AES00.PDF).
- Main capability session: `CAPABILITIES_20260905T221801_419147Z`. Failed and successful integration takes are separately sealed; the final evidence index links their manifests. Earlier POST_DESOLDER evidence remains unchanged.
