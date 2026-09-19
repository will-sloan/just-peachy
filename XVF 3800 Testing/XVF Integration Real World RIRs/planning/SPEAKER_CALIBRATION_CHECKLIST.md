# Speaker setup and relative calibration checklist

**Hardware update — 6 September 2026:** keep KRK volume, LF/HF EQ, ARC state/configuration, Windows/interface output level, software level and physical orientation fixed for formal measurements. Optional EMM-6 recordings are archived separately for later mismatch analysis. No speaker correction or deconvolution is required now. See [current project context](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/PROJECT_CONTEXT.md>) and [GUI guidance](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/MEASUREMENT_GUI_GUIDE.md>).

Use this for the workbook's excluded setup/level trial before P1. The fixed campaign source is **KRK GoAux 4, wired**. **Dayton Audio EMM-6 is optional/reference-only**; normal XVF MIC0–MIC3 recording requires no external reference. Without a calibrated microphone or SPL meter, the outcome is a repeatable relative source setup, not an absolute SPL calibration or a flat loudspeaker response.

## Connect and document

- [ ] Verify/photo the model label, chosen cabinet, input socket and cable route.
- [ ] Use one wired cabinet. Prefer **XVF LINE OUT -> one KRK GoAux 4 RCA input**, with XVF WDM-KS playback selected. Confirm the unused cabinet is silent: XVF duplicates left audio on both analog outputs, so connecting both RCA channels can excite both cabinets.
- [ ] Record/photo the existing chosen bass/treble positions. The user will keep these and the speaker volume fixed throughout the campaign. If choosing an initial reference before a campaign, marked neutral/0 positions are a reproducible option; do not change the established settings between experimental conditions.
- [ ] Record speaker volume mark, Windows output level, application playback scalar, array gain/delay and USB bit depth. Disable optional playback enhancements/normalization where available; record any processing that cannot be disabled.
- [ ] Mark source/array centers, heights, source facing, board yaw/pitch/roll and room axes. Leave unmeasured values blank and label estimates. Save the setup profile.


## Find a usable level

- [ ] Pause phone speech and record a quiet baseline. Speech tests for direction/energy are separate runs.
- [ ] Select the primary 1-second-gap ESS. Start at low speaker volume and modest software level, such as the app's -18 dB default. This multiplies the existing WAV; it is not a dB SPL target.
- [ ] Capture a setup sweep. Inspect all four measurement microphones for clipping, noise, marker recovery and sufficient decay. Aim initially for at least 6 dB peak headroom, while checking usable sweep response above the noise floor. **Do not turn the speaker excessively loud merely to push raw microphone peaks near full scale.**
- [ ] Increase only one common playback control in small increments if required for signal-to-noise ratio. Do not independently normalize microphone channels, boost weak bands indiscriminately or change per-seat volume.
- [ ] If the marker has not decayed adequately before the sweep, use the documented 2-second-gap alternate and record the change.

The headroom value is a proposed pilot rule, not an XMOS guaranteed acoustic range. The correct level depends on noise, frequency response and distortion at the actual geometry.

## Check compression with a 6 dB pair

- [ ] At unchanged geometry and cabinet settings, record two otherwise identical sweeps with software levels **6 dB apart**, for example -18 dB and -24 dB.
- [ ] Retain both originals and their actual excitation scalars. A linear path produces an approximately 6 dB signal change where the sweep is adequately above noise.
- [ ] In subsequent analysis, divide each transfer estimate by its actual emitted excitation amplitude; the estimates should agree within a repeat-noise tolerance fixed from the pilot.
- [ ] If response level or shape changes beyond repeat noise, lower the louder level and investigate limiting/DRC, distortion or poor SNR. Do not label this automated analysis complete merely because capture passed.

## Freeze and repeat

- [ ] Freeze cabinet, tone/volume controls, software level, input socket and excitation hash. Save a calibration/reference label such as `RELATIVE_REF_01_UNCALIBRATED`.
- [ ] Keep source level fixed across measurement seats; received-level differences are part of the experiment. Revisit the same reference geometry at session start/end to check drift.
- [ ] Capture two unchanged front-position repeats with separate repeat numbers. Keep all failed takes and partial runs.
- [ ] Review marker timing, clock drift, all-channel repeatability and common delay before accepting P1. Realtek/phone and XVF use separate clocks; provisional marker estimates are not automatic correction. Prefer the shared XVF playback clock for the wired KRK GoAux 4 route.

## What this calibrates

This procedure fixes **repeatable relative playback level**. Report microphone dBFS and relative changes. An absolute pressure calibration needs a calibrated sensitivity/reference microphone, SPL meter or suitable acoustic calibrator; see [REW's SPL calibration procedure](https://www.roomeqwizard.com/help/help_en-GB/html/inputcal.html).

Deconvolving the electrical sweep records the combined **speaker + room/table/objects + board/port/microphone + capture path**. The workbook intentionally retains this path for its first simulator. Removing the KRK GoAux 4 response requires separate reference characterization; making the measured seat response flat would also remove room effects that the experiment needs. The current software retains capture/QC evidence and does not yet perform final RIR deconvolution or speaker-response removal.
