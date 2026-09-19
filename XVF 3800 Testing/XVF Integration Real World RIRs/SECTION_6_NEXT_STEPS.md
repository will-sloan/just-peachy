# Section 6 completed: capture works; proceed to the controlled pilot

**Hardware update — 6 September 2026:** keep KRK volume, LF/HF EQ, ARC state/configuration, Windows/interface output level, software level and physical orientation fixed for formal measurements. Optional EMM-6 recordings are archived separately for later mismatch analysis. No speaker correction or deconvolution is required now. See [current project context](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/PROJECT_CONTEXT.md>) and [GUI guidance](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/MEASUREMENT_GUI_GUIDE.md>).

The zero-microphone blocker is cleared. All four onboard linear-array microphones record changing audio. Genuine USB24 capture, fixed gain/delay, fast telemetry, two played sweep rehearsals, stop/recovery and the final five-minute buffered recording have passed their implemented checks. The earlier transport and playback failures are preserved and explained in the [qualification report](planning/XVF_SAMPLING_AND_MEASUREMENT_REPORT.md).

The original Word workbook is unchanged. This guide continues its sections 7–10 and P1/P2 sequence. Functional tests found no failed microphone in the tested paths; they do not certify every electrical component or latent damage.

## Open the recorder

Double-click [Start-XVF-Measurement.cmd](Start-XVF-Measurement.cmd), or open the running [local recorder](http://127.0.0.1:8767/). Reopening the launcher reuses a recognized running app. The saved profile **KRK GoAux 4 — wired campaign setup** preserves your fixed volume/bass/treble policy and leaves unknown facts blank.

After a cold power cycle, check USB bit depth. If it is 16/16, stop streams and run [Prepare-XVF-24bit.cmd](Prepare-XVF-24bit.cmd), then reopen/restart the recorder to refresh audio endpoints. The documented USB24 command restarts firmware and resets other runtime parameters; the helper records the old state and restores microphone gain, reference gain and system delay. Verify your settings afterward. It does not flash firmware.

Use the unique XVF **Windows WDM-KS** input/output pair. Keep other XVF recording/control applications closed during a take. Use the app's Inspect devices button while idle.

## The sampling contract

| Item | Setting and meaning |
|---|---|
| Microphone audio | **16 kHz per microphone**, all four on one common time base |
| USB carrier | 48 kHz stereo carrying six packed 16 kHz channels; not 48 kHz acoustic sampling per mic |
| Precision | USB24/24 gives **23 audio payload bits** after the packing marker. Numerical width is not microphone effective resolution |
| Raw domain | Category 1, before fixed mic gain/delay |
| Amplified domain | Category 3, after shared gain/delay and before SHF/AEC. Current gain 10× (+20 dB), with 32-sample (2 ms) mic delay relative to raw |
| Direction/energy | Full four-beam arrays, approximately **60–62 readings/s per field** measured while recording; 16 ms median spacing, with host scheduling gaps retained (up to 475 ms in the final stress test) |
| Internal processing | 256 samples at 16 kHz = 62.5 frames/s. More polling cannot create fresher algorithm frames |
| Interpretation | Native angle frame, linear-array front/rear ambiguity, uncalibrated energy units; host transaction timestamps are not device sample timestamps |

Leave **Also log selected-output angles** off for the fastest default. Turning it on selects the slower official CLI backend and includes an additional smoothed/gated output. The live screen's roughly one-second refresh does not control logging speed.

Use **Amplified / Category 3** for the workbook's canonical injection-domain path, or Raw / Category 1 if you retain an explicit gain/delay conversion. Do not use beamformed/AGC/noise-suppressed processed audio as a replacement for four linear RIR channels. Do not normalize or time-align microphone channels independently. Later HIL must avoid applying already included gain/delay twice.

## Your next physical setup

1. Use the KRK GoAux 4 as the fixed wired source; photograph the cabinet and connection.
2. Keep your existing volume, bass and treble settings fixed. Record their marks/photos. Keep the software scalar and source waveform fixed across the actual measurement conditions too; received differences between positions are part of the experiment.
3. Prefer **XVF LINE OUT to one KRK GoAux 4 RCA input/cabinet**, then choose **Output (XVF3800 Voice Processor) / Windows WDM-KS** for playback. Default firmware duplicates LEFT on both analog outputs, so confirm the other cabinet is silent. This shares playback/capture clock. The actual KRK GoAux 4 cable, cabinet and acoustic path still need your physical check.
4. Enter room/table/placement IDs, source XYZ and facing, array XYZ/yaw/pitch/roll, heights, distance, surface/clutter and photos. Define the laboratory origin, +X forward, +Y device-left and +Z up. Verify the physical microphone map and board forward arrow before interpreting room directions. Leave unknown values blank, not zero.
5. Save the completed setup profile. Each take retains its own copy; editing a profile cannot change earlier evidence.

## Relative speaker setup, then the first pair

With no calibrated microphone, establish a repeatable **relative reference**, not absolute SPL or a flat speaker calibration. See the [speaker checklist](planning/SPEAKER_CALIBRATION_CHECKLIST.md).

Pause phone speech and record a quiet baseline. Start a setup sweep at a modest level. Check all four measurement channels for clipping, usable band/SNR, marker timing and sufficient decay. A proposed initial headroom target is at least 6 dB, not an XMOS calibration specification; do not drive the speaker excessively loud to push raw microphones toward full scale.

At unchanged geometry and hardware dial settings, use two software levels 6 dB apart for an **excluded setup/compression check**. Then choose one level and keep it fixed throughout the real series. This initial check does not require changing the hardware dials or changing levels between seats.

Select the primary one-second-gap excitation and press **Play & record**. It records before and after playback and saves the short timing bursts plus the ten-second 80–7500 Hz sweep. Use the documented two-second-gap alternative if marker decay contaminates sweep onset. The sweep is the main RIR excitation; the impulse-like bursts establish timing.

Take two unchanged front-position P1 repeats before expanding the workbook matrix. Inspect frequency-dependent repeatability, markers and all four common-time-base RIRs before acceptance. The recorder automates playback/capture/QC; final RIR extraction, source-response removal, physical HIL and H2 evaluation remain later stages. The measured transfer contains speaker + room/table/objects + microphone/board/capture response.

For direction tests, resume phone speech and use **Record only** at measured front/side/rear positions. Keep these separate from quiet sweep runs; a sweep need not generate reliable speech-gated energy or direction.

## Read the result and find your recordings

- **PASS:** record-only capture passed implemented audio/telemetry checks; no absolute or angular calibration is implied.
- **REVIEW:** sweep capture and implemented marker gates passed; geometry, calibration, acoustic arrival and repeatability still need scientific review.
- **RETAKE:** a stopped take or failed acoustic marker check with otherwise clean capture.
- **INVESTIGATE:** capture, control, playback, restoration or continuity failed. Read the failed checks before repeating.

The known digital continuity sequence is essential: testing caught a brief reordered segment even though packing markers and driver flags appeared clean. The final recorder requests 150 ms buffers and records actual negotiated latency, but every take still receives continuity QC. A pass on one take does not waive checks on the next.

The **Recent take archive** lists trial labels, dates, domains, results, room/placement, repeat and array pose, with report and JSON links. Original WAVs, actual source, source hashes, setup, firmware settings, telemetry and receipts live in separate timestamped folders under [experiments](XVF_MEASUREMENT_WORK/experiments). Keep failed takes. Do not play the packed carrier WAV as ordinary audio; use MIC0–MIC3 or microphones_4ch.wav.

Further reading: [recorder instructions](measurement_app/README.md), [pilot experiment design](planning/PILOT_EXPERIMENT_DESIGN.md), [sampling/source findings](planning/SAMPLING_AND_SPEAKER_FINDINGS.md), [full measured report](planning/XVF_SAMPLING_AND_MEASUREMENT_REPORT.md).
