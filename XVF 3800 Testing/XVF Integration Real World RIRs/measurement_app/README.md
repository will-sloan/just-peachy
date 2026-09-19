# XVF Measurement

**Version 2:** use [MEASUREMENT_GUI_GUIDE.md](../MEASUREMENT_GUI_GUIDE.md) for the current controls and folder layout. The GUI now has room, position, distance, angle, Flat/Upright and independent obstruction, with one Play & record button. Both performs two sequential passes: four raw microphones, then four amplified microphones. New trial groups use the workbook folder structure; the older technical notes below describe the acquisition bundle now stored inside each pass folder. An incompatible older backend is refused and must be restarted while idle.

A local recorder for the four onboard linear-array microphones, native direction/energy telemetry, verified sweep files and the setup information needed to repeat a take. This version captures evidence and checks integrity; it does **not** produce a final calibrated RIR or remove the speaker response. See the current qualification report for tests actually completed on this laptop.

## Start and prepare

1. Connect the XVF3800 with the verified `3.2.1 ua-io48-lin` firmware and all external microphone connections removed.
2. After a cold power cycle, close other XVF audio/control programs and run [Prepare-XVF-24bit.cmd](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/Prepare-XVF-24bit.cmd>). It prepares the documented USB24 mode, which reboots the board. Do this while the recorder is stopped; open/restart the recorder afterward so Windows endpoints are rediscovered.
3. Double-click [Start-XVF-Measurement.cmd](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/Start-XVF-Measurement.cmd>). The current build uses [http://127.0.0.1:8767](http://127.0.0.1:8767). Keep its original server launcher running while recording. Opening the launcher again identifies an existing XVF app on this port, opens its page and exits successfully. It does not start a second recorder on that port or stop an existing process. An unrelated service on that port produces an error instead.
4. Select **Inspect devices** and confirm the displayed firmware, USB bit depth and gain/delay. Prefer **24/24 USB**, which gives 23 microphone audio payload bits after packing. A 24-bit file/container alone is not sufficient; the device must report 24-bit mode. If it reports 16/16, the app can record, but only 15 payload bits are available.

The software finds the unique XVF **Windows WDM-KS** input/output pair. It uses a 48 kHz stereo transport to recover six channels at **16 kHz**. Each microphone is therefore sampled at 16 kHz, not 48 kHz. Do not run Audacity, a second logger or another XVF control utility during a take.

Launcher reuse checks `/api/status` for this app's identity. Older builds are recognized only when their known XVF status fields and page title both match; this check does not inspect the board. Reusing a running server keeps its loaded backend code. Reloading the page refreshes the interface, but does not upgrade that running backend.

Older pages on ports 8765 or 8766 may still be open. Use the current 8767 page for this build. All instances share a device lock so only one can inspect or record with the XVF at a time; do not start captures from an older page.

## Record phone speech first

Use this for direction/energy characterization, quiet baselines and microphone checks.

1. Enter a trial label such as `PHONE_SPEECH_FRONT_R01`. Select the microphone domain and a record-only duration.
2. Leave **Also log selected-output angles** off for the fastest default: the queued adapter reads the full angle and energy arrays using the official XMOS transport libraries. It records host USB transaction timing. Turning the option on selects the official command-line backend for all three fields, including the smoothed selected-output angle. Actual rates and gaps are measured in each run; neither backend provides a device sample timestamp or guarantees that successive fields belong to one DSP frame. The live screen refreshes about once per second and does not set acquisition speed.
3. Play speech on the phone at a documented position and press **Record only**. This button does not play an acoustic stimulus from the software.
4. Keep the source and board still for a static direction trial. Label intentional source movements separately rather than mixing them into a stationary measurement.

Native angle order is focused beam 1, focused beam 2, scanning beam, auto-select. Energy follows that same order and is **not SPL**. The optional selected direction includes smoothing; NaN can be a valid no-speech result. Linear-array native angles span 0-180 degrees and cannot uniquely distinguish the two sides perpendicular to the microphone line. Preserve native values until the laboratory orientation has been mapped.

## Set up the Edifier measurement

The current model field says **Edifier bt1800**, as reported by the user. Verify the cabinet label before treating **R1800BT** as confirmed. No calibrated reference microphone is available, so use relative levels and record `uncalibrated` in the reference field.

- Choose **Output (XVF3800 Voice Processor) / Windows WDM-KS** for playback through XVF LINE OUT. This shares the XVF capture clock. Wire LINE OUT to **one Edifier RCA input/cabinet** and confirm only that cabinet plays. The default XVF DAC sends its left signal to both analog outputs; software left/right balance cannot isolate the cabinets on this route.
- A Realtek output is suitable for integration testing or a separately qualified playback route. It has a different clock from XVF capture. Marker timing is checked conservatively; a timing mismatch is not automatically interpreted as clock drift. This version does not correct clocks or qualify the result as a final RIR.
- Use wired input for the measurement setup. Record the input socket, cabinet, volume mark and Windows output level. The user reports that Edifier volume, bass and treble remain constant throughout the series: preserve those existing settings and record or photograph their positions once in the saved profile. The app records that policy and applies no automatic EQ or normalization. Do not change the hardware controls between comparisons.
- Pause phone speech during sweeps. Ambient speech contaminates a sweep-based transfer measurement. Resume it for the separate direction/energy trials.

Follow the [speaker calibration checklist](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/planning/SPEAKER_CALIBRATION_CHECKLIST.md>) before accepting a measurement series.

## Geometry and saved setups

Fill in room/table/placement IDs, source ID, repeat number and clutter condition. Record source position and cabinet facing direction separately. For the board, record mounting orientation, yaw/pitch/roll and height. Distances use metres; angles use degrees.

Expand **Coordinate frame & evidence** to define origin, axes, yaw sign/zero, the physical arrow on the board and photo filenames. Use the workbook convention consistently: +X forward, +Y device-left, positive azimuth counter-clockwise viewed from above. Firmware coordinates are separate from this laboratory frame. Leave unknown numbers **blank**; do not enter zero to mean unknown. Mark positions/orientations as measured or estimated honestly. Photo references are recorded as text; the files are not uploaded or copied.

Give the setup a profile name and select **Save setup**. **Load** restores a saved profile; check the playback device again because Windows device indices can change after reconnects. Browser autosave preserves form edits, while saved profiles live under `measurement_app/profiles`. Every take stores its own setup snapshot, so later profile changes do not rewrite earlier records.

## Choose raw or amplified microphones

| Choice | Capture domain | Use |
|---|---|---|
| Raw / Category 1 | Individual microphones before fixed gain and system delay | Preserve the sensor-domain recording, especially with verified PCM24 |
| Amplified / Category 3 | The same microphones after common fixed gain and delay | Direct match to the workbook's canonical pre-SHF/HIL domain |

The app reads and preserves the existing gain. The current verified settings are gain **10 (+20 dB)** and system delay **-32**, which means the amplified microphone signals lag raw by **32 samples = 2 ms**. This is fixed gain, not AGC. Do not compare raw/amplified files as though they had identical scaling or timing. Amplifying a quantized WAV afterward does not restore lost low-order detail.

For later HIL replay, a Category 3-derived vector already contains gain/delay; applying them again would be wrong. Keep its domain in the trial record. Never normalize or align the four microphones independently.

## Play the sweep and retain two repeats

1. Select the V2 **1-second-gap impulse + ESS** file. Its 20 ms marker is a timing aid; its 10-second 80-7500 Hz exponential sweep is the primary RIR excitation. Use the 2-second-gap alternate only if marker decay intrudes into the sweep.
2. Begin with the app's modest **-18 dB software playback level**, keeping the documented Edifier hardware controls fixed. This scalar is additional to the level already encoded in the WAV; it is not an acoustic SPL setting. If a level trial changes the software scalar, record the new value and hold it fixed for the measurement repeats.
3. Press **Measure selected excitation**. The app starts capture and telemetry, plays the stimulus, retains post-playback audio, and checks framing, the digital continuity sequence, channel levels and acoustic marker candidates.
4. Inspect the report. After level/linearity checks, freeze the controls, save the setup profile, and take two unchanged front-position repeats with separate repeat numbers. Do not expand to all positions until their timing and responses have been reviewed.
5. If interruption is necessary, use **Stop & retain partial run** and wait for restoration to complete. Start a new take afterward; do not reuse a partial recording as a complete sweep.

## Read the result

| Result | Meaning |
|---|---|
| **PASS** | Record-only capture passed its implemented integrity checks. This is not acoustic calibration or direction accuracy qualification |
| **REVIEW** | Measurement capture passed integrity checks; marker candidates, geometry, speaker level and eventual RIR extraction still need review |
| **RETAKE** | A stopped take or unreliable/missing acoustic markers. Keep its evidence and repeat after fixing the condition |
| **INVESTIGATE** | Acquisition, control, playback, restoration or integrity checks failed. Read the error and per-check results before continuing |

A capture can pass audio integrity while its scientific-measurement flag remains false. Read individual checks as well as the headline status. No final RIR deconvolution, absolute SPL, angular accuracy or automatic speaker equalization is claimed.

Known-sequence continuity is a required capture check. Clean audio-driver flags alone do not establish an intact recording: testing found reordered audio groups that the driver did not flag. A missing, repeated or reordered group fails continuity and produces **INVESTIGATE**, even when the WAV looks plausible or acoustic markers also fail. Preserve the original native recording and repeat after resolving the transport issue; do not repair or splice the evidence into a passing take. Playback/control/integrity failures take precedence over marker-only **RETAKE**; an intentional stop remains a partial **RETAKE**.

Acoustic QC derives separate start/stop templates from the actual played 48 kHz file and checks all four microphones. Missing or ambiguous peaks, an inconsistent 200 ms stop repeat, or excessive start-to-stop timing error retain **RETAKE**. The candidates are not calibrated direct-path arrivals and are never automatically used to resample or align the microphone recordings. See the [laptop marker investigation](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/planning/LAPTOP_MARKER_REVIEW.md>) for the failed pilot evidence and detector validation.

Each timestamped `TAKE_...` folder is under [XVF_MEASUREMENT_WORK/experiments](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/XVF_MEASUREMENT_WORK/experiments>). Useful files include:

- `REPORT.txt`, `result.json`, `quality.json`: outcome and measured checks.
- `request.json`, `identity.json`, `capture_configuration.json`, `playback.json`: geometry, controls, firmware, signal domain and route.
- `native_packed.wav`: untouched packed transport; **do not listen to this as ordinary audio**.
- `microphones_4ch.wav`, `MIC0.wav` through `MIC3.wav`: correctly decoded microphone recordings, all on one time base.
- `decoded_six_channels.wav`: digital continuity signal, processed auto-select audio, then MIC0-3. Its first channel is **not** the far-end acoustic reference.
- Excitation copies, actual USB playback vector, telemetry, command receipts, capture timestamps and source snapshot. The completed evidence package includes SHA-256 hashes; keep originals and failed takes.

The [sampling and speaker source review](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/planning/SAMPLING_AND_SPEAKER_FINDINGS.md>) explains device limits and cites the supplied manuals. Continue through workbook sections 7-10, then the two-repeat front-position P1 proof, before the physical HIL and multi-position campaign.
