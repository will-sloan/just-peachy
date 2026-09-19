# Optional KRK GoAux 4 reference archive with Dayton EMM-6

The campaign source is **KRK GoAux 4 with wired playback**. The **Dayton Audio EMM-6 is optional/reference-only**: it may be used once to archive the KRK response and establish a reference playback level, then removed. This session can be skipped; normal measurements never require the EMM-6 or its calibration file. Routine room measurements use only the XVF’s four **Category 3 amplified microphone channels**, with gain **10** and system delay **−32 samples**, checked before and after recording.

The separate reference workflow preserves source audio, stimulus and configuration for later use. **No speaker correction or deconvolution is required now or applied automatically.** Revisit source-response correction only if synthetic-versus-real mismatch suggests it would be useful. The EMM-6 model is known; its serial-specific file, interface and physical operation still need to be supplied/verified if this optional workflow is used.

## 1. Why Category 3 matches the intended live device

The [Word workbook](C:/Users/amiri/Downloads/Just_Peachy_H2_XVF3800_Master_Workbook_and_Experiment_Plan_V4.docx) §7.1 identifies Category 3 as the canonical RIR/HIL domain; §13.6.2 explicitly captures four amplified microphones with system delay applied. These are four physical microphone signals immediately before SHF voice processing. They do not contain beamforming or post-processing AGC. Processed-auto audio may be retained for diagnostics but cannot replace the four microphone RIRs.

Current simultaneous raw/amplified pair tests confirmed approximately:

```
amplified[n + 32] = 10 × raw[n]
```

The common gain is +20 dB; the 32-sample microphone delay is **2 ms at 16 kHz**. Exported raw and amplified samples have small separate quantization differences, so an offline multiplication and delay is not a bit-exact substitute for an actual Category 3 capture. Existing raw24 recordings remain an archive for hardware QC and other analyses; routine campaign capture need not repeat a raw pass. See [independent domain evidence](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/planning/TRUE_PCM24_INDEPENDENT_REVIEW.md>).

Fixed common gain preserves relative microphone levels. Common delay preserves relative arrival times between microphones. Neither adapts to sound level. Digital gain raises microphone signal and microphone noise together; it does not improve acoustic SNR, although gain before USB quantization can preserve finer transported detail. It also reduces headroom, so all four Category 3 channels must pass clipping checks.

System delay adjusts microphone/reference timing for acoustic echo cancellation. A negative value delays all microphones. The configured −32 is **not a measurement of room propagation time**, an individual microphone alignment, or a calibration of source distance. Do not independently shift the four channels.

For later physical HIL, gain and delay must be applied **exactly once**. A synthesized vector already representing Category 3 is injected with microphone gain 1 and system delay 0; the workbook also specifies reference gain 1 for a vector whose reference gain is already embodied. Near-end-only tests use a zero far-end reference. HIL is a separate operating mode; restore and verify gain 10 / delay −32 before returning to live microphone acquisition. Preserve a common timing correction and documented global level scale, never separate per-microphone normalization.

All four microphone signals remain **16 kHz**. Packed USB’s **48 kHz stereo** stream carries six 16 kHz channels; it is not 48 kHz audio from each microphone. Source documentation: [XMOS programming guide](C:/Users/amiri/Downloads/xvf3800_programming_guide_v3.2.1.pdf), §§4.1.1–4.1.3, pp.46–52; [XMOS user guide](C:/Users/amiri/Downloads/xvf3800_user_guide_v3.2.1.pdf), §§4.2.2 and 4.2.4, pp.30–32.

## 2. If speaker correction becomes useful later

The aim is to characterize the repeatable speaker’s relative spectral response under a defined source-measurement geometry. It is not to flatten every room seat. A reference microphone beside the array measures a different **speaker-plus-room** path; dividing the array response by that recording can remove desired room information, mix spatial differences and magnify spectral nulls.

Workbook §13.1 intentionally preserves the complete speaker → room/table → enclosure/port → microphone path for the first simulator. §13.6.4 permits a separately designed source-correction method later. Therefore:

- Preserve an **uncorrected RIR library** and all original speaker-reference recordings.
- Derive a candidate source correction only over a justified frequency range, with bounded gain and regularization. Do not boost deep room nulls.
- Validate the candidate with a new reference measurement and level/repeatability checks.
- Store any corrected RIR as a versioned derivative with the original RIR hash, filter hash, method, band limits, gain and timing treatment.
- If correction is later applied during physical sweep playback, treat it as a new protocol revision. Log the exact filtered stimulus and freeze the qualified filter and gain for that series. Do not mix corrected and uncorrected source conditions silently.

No automatic EQ, blind array/reference division or source-filter application is part of the initial recording step.

## 3. Prepare the optional Dayton EMM-6

The EMM-6 has an XLR output and requires +15 to +48 V phantom power. Use a microphone preamp/audio interface and select its input/channel in the GUI; EMM-6 is not a USB microphone or the KRK ARC microphone. Record serial number, interface, gain and OS input level. Obtain the matching Dayton calibration file and archive its original bytes/hash. [Dayton EMM-6 documentation](https://www.daytonaudio.com/product/911/emm-6-electret-measurement-microphone)

For relative spectral characterization, **absolute SPL calibration is not required**. A valid microphone frequency-response correction and its orientation are still important. A file containing relative magnitude does not automatically contain phase or absolute sensitivity. The generic software archives calibration files; model-specific parsing and response correction require validation. It must not infer SPL or apply EQ merely because a file was selected. [REW calibration-file documentation](https://www.roomeqwizard.com/help/help_en-GB/html/calfiles.html)

Document the EMM-6 orientation used for the reference and preserve the calibration file's stated convention. The file is archived without altering the original recording; analysis-specific correction can be applied later to a derivative.

An acoustic calibrator is an **optional initial level-calibration step**, useful if absolute pressure is wanted. Fit a compatible calibrator to the reference microphone, enter its actual stated level and frequency, and confirm the fit. Do not assume 94 dB or fit it to the XVF board ports. The optional calibration button records about 10 seconds and analyses seconds 2–8 for tone, clipping and stability before estimating `pa_per_fs`. Explicitly using an accepted sensitivity record links it to later captures. It remains valid only for the same microphone/interface/input gain and establishes a level scale at the calibration tone, not frequency-response correction. Otherwise retain relative units. [REW SPL calibration](https://www.roomeqwizard.com/help/help_en-GB/html/inputcal.html)

XVF speech-energy metrics remain uncalibrated algorithm outputs; this reference calibration does not turn them into SPL.

## 4. Make a controlled source-reference measurement

Use one wired **KRK GoAux 4** cabinet as the fixed campaign source. Record and photograph cabinet, input, height/facing/tilt, speaker volume, LF/HF EQ, ARC state/saved configuration and Windows/interface output level. Keep them and the software level fixed during formal measurements. Do not rerun ARC between experimental positions. KRK's ARC processing, if on, belongs to the physical source response and is distinct from this software's unapplied correction. [KRK documentation](https://www.krkmusic.com/products/goaux-4-portable-powered-studio-monitors)

Prefer the intended XVF USB → LINE OUT → single speaker input route. With the present left-duplicated LINE OUT configuration, use one RCA input. A different playback endpoint is a different source-chain configuration and must be documented.

Place the speaker and reference on stable supports in a quiet, open arrangement, away from nearby reflecting surfaces as practical. Record the capsule’s exact distance, height and angle relative to the cabinet. The distance should permit the cabinet’s drivers to combine; a microphone extremely close to one driver is not a full-cabinet measurement. Choose and photograph the geometry before recording.

Room reflections still exist. A gated direct-sound analysis is useful only above frequencies supported by the available reflection-free time window: a window of duration T has frequency resolution on the order of 1/T. It cannot establish reliable deep-bass response from a very short gate. Extending bass characterization may need separate near-field driver/port measurements and a justified merge; that is additional work, not an automatic interpretation of the first sweep. These are measurement-design constraints.

In the API 3 **speaker-reference** workflow:

1. Select the reference input/channel and explicit speaker playback endpoint; enter the microphone/calibration and geometry information.
2. Pause phone speech and other intentional playback. The reference recording begins before playback and retains a short quiet lead-in; a longer independent background recording can be made during the microphone pilot if needed.
3. Use the separate speaker-reference button to play the logged sweep and record the reference. This creates a `SPEAKER_REF_*` run, not a room-array trial.
4. Run one candidate level and a second sweep **6 dB lower in software**, holding every physical control and geometry fixed. Compare after accounting for that one known scale change; inspect clipping, noise, distortion/compression and repeatability.
5. Archive the source settings, reference playback level and all original evidence. No correction or deconvolution is needed now. If useful later, derive a versioned correction without altering these originals.
6. Remove the reference microphone before the room campaign.

The reference archive is tied to that KRK cabinet, route, controls, measurement direction and level range. Changing those conditions requires a new configuration revision; keep the archived reference available when assessing later model mismatch.

## 5. Reference files and timing

The separate reference recorder starts before playback and retains the full sweep and tail. It saves all opened reference channels and the selected channel at **48 kHz in FLOAT WAV storage**. Float storage does not establish 32 bits of acoustic precision; actual precision depends on microphone, interface and driver.

The current workbook excitation sweeps **80–7,500 Hz**, matching the XVF experiment band. A 48 kHz reference recording does not extend that excitation to 20 kHz; it is not a full-range speaker calibration. Any source correction must stay within the frequency range supported by the excitation, microphone calibration, signal-to-noise ratio and reflection-free analysis window.

```
SPEAKER_REF_<unique_id>/
  request.json
  reference/
    reference_original.wav
    selected_reference.wav
    capture.json
    quality.json
    calibration/                 # original supplied calibration evidence
  ...                            # exact stimulus and playback receipt
  result.json
  REPORT.txt
  SHA256SUMS.txt

REFERENCE_CAL_<unique_id>/        # optional fitted-calibrator recording
  request.json
  reference/...
  calibration.json               # only for an accepted sensitivity estimate
  result.json
  REPORT.txt
  SHA256SUMS.txt
```

A USB reference microphone and playback device have separate sample clocks, even at the same nominal rate. Host start/end timestamps do not establish sample-accurate alignment. Preserve native files and qualify timing/clock mismatch before phase-sensitive analysis or deconvolution. Never use this process to independently resample the four XVF microphone channels. [REW timing guidance](https://www.roomeqwizard.com/betahelp/help/html/makingmeasurements.html)

REW can provide an independent source check. Its file-playback mode requires its own generated sweep/timing-reference contract; the workbook’s V2 file is not automatically interchangeable.

## 6. Campaign progression and evidence

**P0 source preparation:** document and fix the KRK controls, output level and orientation. Optionally collect the EMM-6 reference archive, then remove it. Skipping the reference step does not block normal capture. Record `source correction not applied`.

**P0 array setup:** verify Category 3 gain 10 / delay −32, four live channels, PCM24 transport and continuity; make an excluded level/setup capture with the actual speaker. Preserve original recordings and failures.

**P1:** obtain two accepted front-position four-channel RIR repeats with unchanged geometry and source settings. Follow workbook §§8.4 and 12: common sweep interval, common timing treatment, relative microphone levels preserved, and repeat comparison.

**P2:** convolve a clean utterance with the four accepted RIRs and prove the physical XVF HIL path at unity microphone gain / zero system delay.

**P3:** expand to six source positions and repeats only after the previous gates pass. Formal repeats are separated in run order. Speaker facing, device pose and obstruction remain separate metadata. Routine room trials require no external reference recording. Enter the prior speaker-reference run ID/path in the saved setup’s Reference notes and record `source correction not applied` in Calibration label until a correction is independently qualified; these fields preserve the source evidence link and correction state without applying a filter.

Keep original recordings, settings, stimulus and hashes immutable. Corrections create new derived versions, never replacements of the evidence.

## Validation evidence

**API 3 software checks completed:** 164 offline tests pass, including 23 reference capture/calibration tests and 19 separate reference-workflow tests. Browser checks confirmed amplified defaults, a separate reference button requiring input/geometry/output, and routine recording independent of reference availability. A fresh 15-second amplified-only XVF recording passed with fixed gain 10 / delay −32 before and after, all four microphones nonzero, zero continuity mismatches and independently verified PCM24 files. See the [version-3 validation report](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/validation/GUI_V3_20260906T020708Z/VALIDATION_REPORT.md>).

**The actual KRK/EMM-6 acoustic setup still needs its pilot.** Earlier software/XVF checks do not qualify the reference interface, source level or ARC state. Source correction remains optional later work; it is not a readiness gate for the main recording workflow. See the updated [GUI guide](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/MEASUREMENT_GUI_GUIDE.md>) for the latest hardware-update validation.
