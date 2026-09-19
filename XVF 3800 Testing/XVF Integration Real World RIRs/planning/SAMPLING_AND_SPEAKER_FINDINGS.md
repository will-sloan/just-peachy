# XVF3800 sampling, signal domains, telemetry and speaker setup

Research date: 2026-09-05. This is a read-only review of the supplied v3.2.1 manuals, source release and workbook, plus primary measurement and speaker documentation. Device results from the active measurement qualification are reported separately; specifications below must not be presented as completed hardware tests.

## Decisions for the measurement tool

- Record the four linear microphones synchronously at **16,000 samples/second per microphone**. The USB endpoint runs at **48,000 stereo frames/second**, with three consecutive stereo frames carrying one six-channel microphone collection. It does not provide four microphones with 48 kHz acoustic bandwidth.
- Prefer a verified **24-bit USB packed capture** for RIR work on Windows. Packing reserves one LSB, so 24-bit transport carries 23 audio bits; 16-bit transport carries 15. These are numerical transport widths, not measured microphone effective resolution or acoustic dynamic range.
- Prefer **Category 3 amplified/delayed microphones** for the workbook's canonical RIR-to-HIL path. Its common fixed gain is appropriate for linear transfer measurements when it does not clip. Category 1 is also a valid measurement domain if gain/delay conversion is explicit. Beamformed, noise-suppressed or AGC/limited processed audio is unsuitable as a four-channel linear acoustic-path substitute.
- Poll raw beam angles and speech energies using a persistent control connection. Keep the selected/smoothed direction as a separate derived field. Measure actual rates, host transaction intervals and audio integrity concurrently. The **62.5 Hz internal frame cadence is not a promise of 62.5 synchronized three-command observations/second**.
- The available Edifier can support repeatable relative-level measurement without a calibrated microphone. It cannot establish absolute SPL or remove its own acoustic response without an external reference/characterization.

## Rates and formats supported by the release

| Item | Documentation/source contract | Test or implementation consequence |
|---|---|---|
| Voice/microphone processing | 16 kHz; nominal acoustic range 80 Hz to 8 kHz | Workbook sweep 80-7500 Hz fits below Nyquist, but usable end-band SNR must be measured |
| USB UA / I2S host rate | 16 or 48 kHz; rate fixed by firmware build | Current `ua-io48-lin` is the correct build for six-channel packed capture |
| Packed capture | Six 16 kHz channels interleaved into stereo 48 kHz | Preserve raw packed transport, common phase and all LSB markers; never resample or apply host volume changes to packed audio |
| USB bits | Windows and macOS: 16 or 24; Linux: 16, 24 or 32 in the release's support table | An int32 array or PCM24 WAV alone does not prove extra device precision |
| USB bit-depth changes | `USB_BIT_DEPTH IN OUT` supports 16, 24 or 32 and reboots, resetting other parameters | Change with streams closed, rediscover endpoint, verify readback/descriptor, then reapply capture routing |
| Transport payload | The firmware writes 0,1,1 markers into each stereo channel's least significant transported bit | Effective payload bits are transport bits minus one; verify marker location before decoding |
| DSP frames | 256 samples at 16 kHz = 16 ms = 62.5 frames/s | Polling faster cannot create additional algorithm frames |
| Default linear geometry | Four microphones at X = -49.95, -16.65, +16.65, +49.95 mm in native firmware coordinates | 33.3 mm adjacent spacing; photograph/verify physical map and a separately defined laboratory forward arrow |

Sources: XMOS datasheet sections 3.4.1-3.5, printed pp.9-11; programming guide section 4.1.2, printed pp.48-50 and Table 4.1; user guide p.10 and section 10.2 p.79; supplied `packing.h` and `BeClearCommon.h` listed below. Relevant format tables, delay prose and direction figures were visually checked against their PDF pages. A general datasheet statement calls bit depth fixed at build time; the same-version user guide and actual command implementation explicitly document the rebooting `USB_BIT_DEPTH` override.

The bit-depth setter writes keyed values at RAM addresses `0xffff4` and `0xffff8`, then schedules a watchdog reboot after 50 ms. Getters use those keys before falling back to default bits. This is retained software-reboot state, not a flash write. A plain `REBOOT` should not be used as proof that bits returned to 16. Explicitly select and read back the desired bit depth, including after a power cycle; power-loss persistence is not promised. See `tile_common.c` lines 234-305 and `application_servicer.c` lines 173-177.

## Raw versus amplified RIR domain

Category 1 sources 0-3 are decimated raw MIC0-3 before microphone gain and system delay. Category 3 sources 0-3 are those same signals after the shared system-delay operation and **one common fixed linear gain**, immediately before SHF/AEC. `AUDIO_MGR_MIC_GAIN` is a linear multiplier: 10 means +20 dB, not +10 dB.

`AUDIO_MGR_SYS_DELAY > 0` delays the reference. A negative value delays every microphone by its magnitude. The current default -32 therefore adds **32 microphone samples = 2 ms** to Category 3 relative to Category 1. It does not alter relative inter-microphone delays. Test the domain by capturing raw and amplified versions of the same microphone simultaneously, aligning by 32 samples, then fitting the common gain while allowing for quantization.

For the same quiet acoustic scene, recording Category 3 can preserve more useful digits through a finite-width USB interface because the gain occurs before conversion for output. Amplifying an already quantized Category 1 WAV offline cannot recover discarded information. Neither operation improves the microphone's underlying acoustic SNR. Higher gain also consumes headroom; inspect all four channels with the loudest planned excitation and freeze the gain for the campaign.

When replaying a Category 3-derived vector, use `AUDIO_MGR_MIC_GAIN 1`, `AUDIO_MGR_REF_GAIN 1`, `AUDIO_MGR_SYS_DELAY 0` if that vector already contains the capture-domain gain/delay. Keep its reference convention explicit: normal reference input has a fixed 6 dB attenuation, skipped in packed injection. The programming guide instructs a 0.5 reference gain when injecting an external reference that does not already include that attenuation. For near-end-only synthetic speech, the far-end reference is zero.

Do not normalize or time-align microphones independently. Preserve an untouched recording and untrimmed RIRs. Any removal of host/playback latency must be one common shift, recorded in samples. The sweep's inverse filter must use the actual emitted excitation samples, not just nominal frequency parameters.

Sources: user guide sections 4.2.2 and 4.2.4 pp.30-32; programming guide sections 4.1.2-4.1.3 pp.49-52; `audio_task.c` lines 618-628 and 917-946; workbook sections 7.1, 8.4 and 13.6.2.

## Direction/energy semantics and fastest useful logging

| Native command | Values, in order | Interpretation |
|---|---|---|
| `AEC_AZIMUTH_VALUES` | Four float radians: focused beam 1, focused beam 2, free-running scan, auto-select | Host text also prints degrees. These are beam directions, not four independent people |
| `AEC_SPENERGY_VALUES` | Four floats in the same beam order | Uncalibrated speech-energy indicators; nonzero suggests speech, larger can mean louder/closer, but noise/echo/reverb can reduce values. Not dB SPL, watts or source distance |
| `AUDIO_MGR_SELECTED_AZIMUTHS` | Two float radians: smoothed speaker DoA, auto-select beam DoA | First can be NaN when speech gating is inactive; preserve NaN and validity separately |

The raw commands independently query `SHF_Get_azimuths`; there is no frame counter or device timestamp in their documented replies. AEC control is serviced between audio frames. A sequential angle read followed by an energy read may observe different frames. Do not merge their line timestamps into a claimed atomic device observation. Repeated equal values can be a steady scene or held tracking state; they do not prove a stale transport. A missing reply is a transport event, while NaN/zero energy can be valid algorithm output.

The supplied source computes DoA smoothing once per 256-sample frame. `doa_smoothing.c` restricts selection to focused beams, uses an approximately 5-degree jump threshold, requires a counter greater than 10 before accepting a persistent jump during speech, then applies an exponential smoothing factor of 0.825. Under sustained qualifying conditions this implies about 176 ms before jump acceptance plus an approximately 83 ms smoothing time constant; actual event latency is state-dependent. Energy gating uses smoothing/decay and a ten-frame hold. These explain why fast polling cannot remove selected-direction lag. They are source-derived behavior, not an acoustic latency calibration.

The linear figure gives **0 degrees at the MIC3 end, 180 at MIC0, and 90 on both perpendicular sides**. Preserve native coordinates. A laboratory 0-degree forward arrow may correspond to native 90 degrees, and front/rear are ambiguous. Do not advertise unique 360-degree direction from this linear build. See user guide Fig.3.3, printed p.18 / PDF p.22.

Benchmark a single raw command, alternating angle+energy, and angle+energy+selected. Report commands/s total and each field's rate separately; include median, p95, maximum interval, errors and timeout/retry behavior. Use one serialized persistent USB owner. Each field needs a sequence, raw reply, request start/completion if instrumented, parsed values and validity. Official batch stdout supports host line-arrival times only. Keep timestamps on a monotonic clock; calibrate the audio-to-telemetry offset with recorded known speech events and moving-source tests later. A smooth UI display can run slower than acquisition. Claim the highest **tested** rate/profile, not an absolute device maximum.

Sources: user guide sections 3.5.1 and 10.1/10.3; supplied `aec_cmds.yaml`, `audio_cmds.yaml`, `shf_wrapper.c` lines 129-139, 337-372 and 548-594; `BeClearCommon.h` lines 67-68; `doa_smoothing.c`; `post_shf_dsp.c`.

## Practical Edifier setup without a calibrated microphone

The user reports **"edifier bt1800"**. The plausible product is **R1800BT**, but confirm the label before recording that exact model as verified. Edifier's [R1800BT page](https://www.edifier.com/us/p/bookshelf-speakers/r1800bt) lists wired RCA inputs and internal DSP/DRC. Its [official manual](https://new-edifier-us-oss.edifier.com/files/20231215/b3f9420c95e6827156dd19e2a031873b.pdf), English pp.3-7, identifies bass/treble/master controls and green Line In versus blue Bluetooth indication. The published 60 Hz-20 kHz (+/-6 dB) response is a broad specification, not this cabinet's calibration curve. Internal DRC makes level-linearity checking useful; there is no verified DRC-bypass procedure here.

1. **Use one cabinet and a wired input.** Prefer XVF USB playback -> XVF LINE OUT -> one Edifier RCA input, with the other input/cabinet silent. The XVF's default DAC duplicates the left reference on both analog outputs, so feeding both RCA inputs would excite two cabinets. Physically connect only the chosen input, or otherwise verify that the unused cabinet is silent. Record active/passive identity, input socket and wiring. Phone speech and laptop speakers are useful functional stimuli; they do not calibrate the Edifier.
2. **Fix the physical setup.** Put that cabinet at the marked source position and height, record its facing direction and tilt separately from position, and mark the board orientation/array center. Use the same source configuration for every location. Set bass and treble to their marked neutral/0 positions if present; otherwise photograph and record the chosen repeatable positions. Neutral knobs do not make the speaker acoustically flat. Leave them fixed.
3. **Establish a quiet level trial.** Stop the phone speech during the actual sweep measurement. Capture ambient noise first, then the workbook's 80-7500 Hz, 10-second ESS at a low emitted level. Increase only a common playback scalar in small steps while inspecting all four required microphone channels. A practical initial engineering target is no clipping and at least 6 dB peak headroom in the measurement channels at the loudest planned setup; this is a proposed pilot rule, not an XMOS acoustic specification. Capture enough decay and inspect frequency-dependent SNR, not just overall peak.
4. **Check level linearity.** At unchanged geometry, capture two sweeps separated by a known 6 dB digital level difference. After dividing by the actual excitation amplitude, their transfer estimates should agree within a tolerance set from repeat noise. A shortfall from a 6 dB captured change or a changing response shape suggests compression/limiting, distortion or inadequate SNR. Lower the level and repeat if needed. Store both takes and the scalar. Do not drive louder to fix a frequency band the speaker cannot reproduce cleanly.
5. **Freeze a relative reference.** Save the source file/hash, output endpoint/rate, Windows and application level, actual digital scalar, cabinet volume and tone photos, geometry, capture gain/delay, and the reference trial's per-microphone dBFS/RMS/peak. Revisit that same reference geometry at session start/end. Keep source level fixed across seats instead of adjusting each seat to the same received level; the level differences are experimental evidence.
6. **Absolute SPL is a separate calibration.** Without a calibrated sensitivity/reference microphone, SPL meter or acoustic calibrator, report dBFS and relative level. Neither XVF beam energy nor neutral speaker knobs provides an absolute pressure reference. If one becomes available, measure the same reference position/noise signal, record weighting and averaging time, and calibrate the measurement path's sensitivity at unchanged gains. [REW's SPL calibration procedure](https://www.roomeqwizard.com/help/help_en-GB/html/inputcal.html) explains the required external reference; its [level-meter documentation](https://www.roomeqwizard.com/help/help_en-GB/html/levelmeters.html) distinguishes dBFS from calibrated units.

Do not try to EQ the whole measured seat response flat for this experiment: that would compensate away room/table/enclosure effects the RIR is meant to contain. Deconvolving the known electrical sweep yields **speaker + room + table/objects + board/port/microphone + fixed capture electronics**, not the room alone. The workbook deliberately accepts the Edifier as a repeatable surrogate in the first pilot (sections 13.1 and 13.6.4). Separating the speaker needs a separately measured reference transfer/known speaker characterization, with matching orientation, distance and valid frequency range; regularized division is then a derived experiment, not automatic speaker calibration from four unknown microphone signals.

## Sweep timing, reconstruction and staged next steps

The workbook's primary file is 17.22 s: 2 s initial silence; a 20 ms marker at 2 s; ESS from 3 to 13 s; decay through 16 s; end markers at 16 and 16.2 s. The marker is for timing, while the ESS is the main RIR signal. Exclude the marker and end-marker responses from the ESS deconvolution, retain the sweep's post-decay, and use the 2-second-gap alternate only if marker decay intrudes. [Farina's original swept-sine paper](https://angelofarina.it/Public/Papers/134-AES00.PDF) describes linear deconvolution and time-separated harmonic responses; a simple frequency division must not be advertised as validated harmonic-distortion separation.

Separate Realtek/phone playback and XVF capture have separate clocks. Start/end markers can estimate an affine clock-rate correction over one take when robustly detected; use one correction shared by all four channels and retain the original. Nominally equal sample rates alone do not establish sample synchronization. REW's [measurement documentation](https://www.roomeqwizard.com/betahelp/help/html/makingmeasurements.html) explains why separate clocks can distort long-sweep impulse/phase estimates and why timing references matter. XVF-clock playback avoids this particular two-device-clock issue, but actual analog-path delay still needs measurement.

Proceed in workbook order: finish section 7's format/domain/telemetry timing contract; section 8 level/interface proof; sections 9-10 geometry/orientation/source registry; then P1 two front-position repeats and P2 one physical HIL case. The first integration captures remain setup/pilot evidence until speaker identity, physical microphone map, one-cabinet route, geometry, actual emitted signal, drift and repeatability are verified. Log speech-direction trials separately from sweeps: a sweep is not speech and should not be expected to produce reliable speech-gated direction/energy.

## Local source links

- [Supplied datasheet](C:/Users/amiri/Downloads/xvf3800_datasheet_v3.2.1.pdf), [user guide](C:/Users/amiri/Downloads/xvf3800_user_guide_v3.2.1.pdf), [programming guide](C:/Users/amiri/Downloads/xvf3800_programming_guide_v3.2.1.pdf).
- [Workbook extraction](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/tmp/reference_text/workbook.txt>); original Word was not modified.
- [Audio task gain/delay implementation](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/tmp/hardware_research/sources/modules/fwk_xvf/modules/xvf/src/data_plane/audio_task.c:618>).
- [USB bit-depth persistence implementation](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/tmp/hardware_research/sources/modules/fwk_xvf/modules/xvf/src/tile_common/tile_common.c:234>).
- [Packing implementation](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/tmp/capture_audit/sources/modules/fwk_xvf/modules/xvf/src/data_plane/packing.h:24>).
- [256-sample frame definitions](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/tmp/sampling_docs_source/precompiled/xshf/inc/BeClearCommon.h:67>).
- [DoA smoothing implementation](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/tmp/sampling_docs_source/sources/modules/fwk_xvf/modules/doa_smoothing/src/doa_smoothing.c:13>).

No hardware calls, driver changes, firmware flashing, original-document edits or frozen-evidence modifications were performed for this review.
