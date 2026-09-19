# Laptop playback marker investigation

Both original laptop pilots remain **RETAKE for scientific measurement**. Their four physical microphones contain the acoustic sweep and clear stop bursts. The first take has a well-supported start marker but an extra **95.875 ms** between start and first stop. The second take has clearer stop bursts but an unreliable start marker. Neither result supports correcting the capture clock or producing a final RIR.

This review reads immutable takes and writes only new files under `tmp/acoustic_marker_review`. SHA-256 values were checked before and after analysis for the microphone WAV, played excitation, capture/playback receipts, request and original quality report; all were unchanged. The original quality reports were not rewritten.

## Evidence and detector correction

The V2 pack generates its isolated 16 kHz and played 48 kHz markers separately. The played file also uses different random data for the start and repeated stop bursts. Matching all events against the isolated 16 kHz marker was therefore incorrect. The first repair used actual played 48 kHz samples, but its ±80 ms stop search excluded the first pilot's real stop pair, about 96 ms later than the start predicted.

[The new offline detector](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/measurement_app/markers.py>) derives each event from the exact played mono 48 kHz file, applies a 193-tap 7.2 kHz anti-alias FIR, and reduces the **template** by 3:1 to the microphone's 16 kHz rate. It retains filter tails and applies the same centered 129-tap 1.5–6 kHz FIR to templates and all four recorded microphones. The chosen band suppresses lower-frequency speech/room coloration and stays below the 8 kHz Nyquist edge. This band is a pilot-informed engineering choice, not a manufacturer specification.

Candidate confidence requires fused RMS normalized correlation ≥0.30 and at least two microphones with absolute correlation ≥0.30. Shape-qualified candidates are ranked by coherent matched amplitude, which prevents a much quieter isolated echo from outranking a stronger arrival solely because both have high normalized correlation. Competing qualified candidates must have amplitude prominence ≥1.15. Negative per-microphone correlation is retained as phase evidence; the channels are not summed with sign cancellation.

The start search uses host time only as a broad ±1 s hint. Stop searches use the start candidate plus documented event spacing, with ±300 ms windows. The selected stop events must be distinct and ordered; the algorithm does **not** force them 200 ms apart. It checks independently measured repeat separation against ±5 ms and the start-to-first-stop interval against ±20 ms. These are coarse acquisition review gates, not sample-accurate RIR or clock qualification. `REVIEW` still requires scientific review; no automatic alignment is accepted and no audio is resampled.

## Frozen pilot results

Times below are relative to each saved decoded four-microphone file. They refer to candidate matched peaks, not a calibrated direct acoustic path.

| Evidence | R1 | R2 |
|---|---:|---:|
| Take | `TAKE_20260905T223303_130671Z_cb7036` | `TAKE_20260905T224047_423999Z_f5997b` |
| Additional software playback gain | −18 dB | −12 dB |
| Played WAV duration | 17.22 s | 17.22 s |
| Host playback operation duration | 17.997008 s | 18.1715175 s |
| Start candidate | 4.1900625 s | 4.364625 s, **unreliable** |
| First stop candidate | 18.2859375 s | 18.43925 s |
| Second stop candidate | 18.4859375 s | 18.63925 s |
| Normalized fused start / stop 1 / stop 2 | 0.421 / 0.342 / 0.375 | 0.286 / 0.412 / 0.448 |
| Measured stop-repeat spacing | 0.200000 s | 0.200000 s |
| Candidate start-to-stop excess over 14 s | **95.875 ms** | 74.625 ms, **not a reliable interval estimate** |
| Outcome | RETAKE: global interval gate | RETAKE: start confidence and global interval gates |

R1's selected samples are 67041, 292575 and 295775 at 16 kHz. All three events pass the provisional shape and competing-candidate gates. The stop pair is outside the old ±80 ms search. Broad-band diagnostic checks also recover the sweep's expected increasing-frequency trace: this is not a zero-microphone or entirely absent-stimulus failure.

R2's start changes materially with reasonable diagnostic weighting/band choices. The strongest normalized candidate in an earlier 1.5–6 kHz FFT analysis was 4.251625 s with fused correlation 0.304; the implemented finite-FIR analysis selects 4.364625 s with 0.286, which fails confidence. This instability is why its start and global interval must remain unqualified. Raising playback by 6 dB improved the repeated stop bursts but did not establish a reliable start. Interfering speech or time-varying sound can reduce marker recoverability; the data do not isolate the acoustic cause.

Full per-microphone signed correlations, alternatives, filters, thresholds and source hashes are in:

- [R1 detector review JSON](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/tmp/acoustic_marker_review/TAKE_20260905T223303_130671Z_cb7036/marker_qc_v1.json>)
- [R2 detector review JSON](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/tmp/acoustic_marker_review/TAKE_20260905T224047_423999Z_f5997b/marker_qc_v1.json>)
- [Reanalysis script](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/tmp/reanalyze_laptop_markers_v1.py>) and [earlier multi-band diagnostic script](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/tmp/analyze_laptop_markers_independent.py>)

## What the timing does and does not establish

The initial playback implementation writes 4096-frame blocks through blocking Realtek WASAPI output. One block is 85.33 ms at 48 kHz. A software/driver feeding stall or another latency change is a plausible contributor to the long interval, but the observations do not prove it. Stream-open and drain time contribute to the host operation duration, so subtracting 17.22 s from that duration is not an acoustic gap measurement.

The installed PortAudio WASAPI blocking `WriteStream` implementation at revision `147dd722548358763a8b649b3e4b41dfffbcfbb6` does not return `paOutputUnderflowed` from that routine. Consequently, the pilot receipt's `underflows: []` cannot establish uninterrupted acoustic playback. See [the exact PortAudio source, WriteStream](https://raw.githubusercontent.com/PortAudio/portaudio/147dd722548358763a8b649b3e4b41dfffbcfbb6/src/hostapi/wasapi/pa_win_wasapi.c). This is separate from the XVF capture's digital continuity/framing evidence, which tests the capture transport.

A 95.875 ms start-to-stop excess is **not automatically clock drift**. In particular, the close stop pair has the expected 200 ms separation and R2's start is ambiguous. Candidate mismatch, changing arrival paths, playback timing changes and constant clock-rate mismatch need different remedies. Fitting a sample-rate correction to these pilots would risk hiding a discontinuity or a wrong marker match.

The root implementation replaces blocking chunk feeding with callback playback and records callback timing/status. Subsequent repeats R4/R5, recorded after that change and the larger XVF capture buffer, pass the implemented acoustic gates as described below. The combined changes and room conditions do not isolate one original cause. For the experiment, prefer the XVF LINE OUT route and one wired Edifier cabinet on the XVF shared playback/capture clock, pause phone speech, and inspect unchanged repeats before deconvolution. Laptop playback remains an integration route rather than Edifier calibration.

## Subsequent callback playback repeats

Later takes `TAKE_20260905T230151_422945Z_75f86c` (R4) and `TAKE_20260905T230252_188661Z_4a7b88` (R5) each pass all implemented marker gates and retain **REVIEW**, because final RIR/scientific qualification is still separate. Their start-to-stop intervals are both **13.999875 s**, only −0.125 ms from the nominal 14 s; their stop repeats are exactly 200 ms at 16 kHz. Start/stop fused correlations are 0.513/0.439/0.431 for R4 and 0.473/0.460/0.443 for R5. Each marker has at least two supporting microphones above the per-channel threshold. This repeat consistency is materially better than R1/R2; it is not an absolute acoustic-latency or clock-rate calibration.

The separate [independent PCM24 auditor](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/tmp/audit_pcm24_take.py>) imports no acquisition, control, soundfile or application decoder code. It uses WAV bytes to reconstruct signed PCM24 words and six-slot packing, then compares the saved decoded files exactly. Both R4/R5 audits pass: 1,066,560 native frames, 350,647 decoded frames, zero phase-marker errors, zero digital-sentinel mismatches, exact agreement with all six-channel/four-channel/per-microphone files, all four microphones nonzero without rails or silent full seconds, and unchanged frozen SHA-256 manifests. Reports: [R4 byte audit](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/tmp/audit_callback_sweep_r4_independent.json>) and [R5 byte audit](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/tmp/audit_callback_sweep_r5_independent.json>).

As an adversarial check, that auditor also reproduced the earlier 300-second take's **2,942 mismatched sentinel samples in one 183.875 ms interval**, despite clean packing and exact decoded-file consistency. It retained FAIL for that old take rather than equating valid framing with continuous data. Its [failed-take audit](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/tmp/audit_failed_300s_pcm24_independent.json>) records callback-gap context without attributing the failure to a specific hardware or software component.

The subsequent **300-second take with the 150 ms buffer**, `TAKE_20260905T230356_986366Z_0732ec`, also passes the independent audit. It contains 14,400,000 native frames and 4,795,127 decoded frames (299.6954375 s after an explicitly retained 304.5625 ms startup exclusion), with **zero marker errors and zero sentinel mismatches over 4,792,422 exact comparisons**. The full 298-second active sentinel is present. Every decoded WAV matches the native bytes, all frozen hashes remain valid, and all four microphones are nonzero without rails or silent full-second windows. MIC0–3 peaks are 14,574 / 21,042 / 19,916 / 18,692 PCM24 counts; peak headroom is 55.20 / 52.01 / 52.49 / 53.04 dB. These values characterize this acoustic run, not the microphone's maximum achievable SNR.

The largest host callback gap after the startup crop (also after the first native second) is 245.0036 ms at native data time 25.8 s, versus a preceding 150 ms block. The exact sentinel remains intact through it. Host callback spacing must therefore be treated as scheduling evidence, not equated directly with lost samples or calibrated acoustic timing. See the [final 300-second byte audit](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/tmp/audit_buffer150_300s_pcm24_independent.json>) and [explicit post-startup timing calculation](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/tmp/audit_buffer150_300s_timing_detail.json>).

## Offline validation

Eight tests in [test_markers.py](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/measurement_app/tests/test_markers.py>) pass. They include independently generated band-limited 48 kHz bursts through four delayed, colored microphone paths with noise and reflection; exact silence; a missing stop; an actual 260 ms stop separation; a 96 ms inserted start-to-stop gap with an otherwise correct 200 ms repeat; competing starts; input format rejection; and the real V2 pack's different 16/48 kHz markers. The 96 ms case remains RETAKE without any resampling. These tests replace the older ideal single-channel correlation tests and do not qualify room-specific acoustic performance.
