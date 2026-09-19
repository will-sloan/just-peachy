# XVF measurement GUI guide

Use this tool to record the four onboard linear-array microphones, direction and energy telemetry, the played sweep, and enough setup information to identify each measurement. The main screen asks for a **room / table name, recorder position name, distance, device-relative angle, obstruction state and flat/upright pose**. One measurement action handles capture, playback, logging and evidence storage.

**Location names:** Room / table name identifies the room and, where needed, the table (for example `Meeting room — Table 2`). Recorder position name identifies the XVF microphone array's location (for example `Table centre` or `Seat 3`), not the speaker's location. Use consistent names across repeats. The saved metadata keys remain `setup.room_name` and `setup.position_name`; automatic room IDs distinguish the full room/table name and position IDs distinguish recorder positions within it. Speaker distance and angle are logged separately.

The default is **Amplified · campaign recording**: one Category 3 sweep through all four microphones, matching the workbook’s intended live-device input domain. Microphone gain is fixed at **10 (+20 dB)** and system delay at **−32 samples**. The recorder checks these values before and after acquisition; it blocks a starting mismatch and flags a change during capture instead of silently changing the configuration.

**Current hardware decision (6 September 2026): KRK GoAux 4, wired, is the fixed acoustic source. Dayton Audio EMM-6 is optional/reference-only.** Normal measurements use XVF MIC0–MIC3 and do not require an EMM-6, calibration file or completed reference session. See [current project context](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/PROJECT_CONTEXT.md>).

Optionally use **Play & record speaker reference** once to archive the KRK response and establish a reference playback level, then remove the EMM-6. Preserve the original reference audio, its calibration file and settings for later synthetic-versus-real mismatch analysis. Speaker correction and deconvolution are deferred; they are not prerequisites for recording the campaign. The tool produces recordings and QC; **no speaker-correction filter, final RIR, IMU measurement or HIL export is generated automatically**.

## Start the tool

**Delete a mistaken take:** under **Recent takes**, click **Delete last recording**. The line immediately below identifies the exact run, room, pose, distance and angle it will remove. One click moves that complete recording folder to the Windows Recycle Bin; restore it there if necessary. The button is disabled during recording or another pending operation. If a newer recording appears after the displayed target was loaded, the server refuses the stale deletion and asks you to refresh. Repeated clicks cannot cascade into deleting earlier takes. Diagnostic/recovery folders and optional reference-microphone archives are not targets of this button.

**Automatic reconnect recovery (enabled):** keep the recorder launcher running. While idle, it checks the XVF USB connection about every 5 seconds, backing off to 30 seconds during repeated failures. After a reconnect it verifies the known linear-array firmware, restores USB **24/24** if needed, preserves the read-back microphone/reference gain and delay across that USB-width restart, and reinitializes the Windows audio-device inventory. Gain **10** and delay **−32** are verified before declaring the board ready. A different firmware, array/injection mode or gain/delay configuration is not silently overwritten. Each full recovery writes an `AUTO_USB24_*` evidence folder under experiments; routine healthy probes do not create takes.

The GUI shows **Waiting for XVF** and blocks new takes while recovery is pending. It refreshes outputs after recovery, retaining a moved device index only when its name and audio API identify a unique match; otherwise reselect the output. Recovery shares the capture hardware lease and never restarts audio while a capture or unfinished writer owns it. A disconnected or corrupted take remains failed and preserved: **press Play & record again** once ready. There is no automatic sweep replay. If the board keeps returning invalid USB replies, physically unplug/reconnect its USB cable; software cannot restore a broken physical connection. Manual `Prepare-XVF-24bit.cmd` remains available as a fallback while the recorder is stopped.

**Current recording profile:** load **KRK formal measurements — -6 dB** for the new measurement series. It saves amplified MIC0–MIC3, software −6 dB, the tested Realtek WASAPI left output, reported Windows 70% and KRK maximum, with Voice Clarity and speaker enhancements OFF recorded in notes. Reference input is disabled. Phase remains P1 for acoustic RIR acquisition; `trial_label = KRK_FORMAL_RIR` distinguishes the new series from the earlier setup captures. Existing P0/P1 pilot archives are preserved. This profile clears speaker distance and angle so you must enter the current geometry; it retains the last room/table name and recorder position, which you must update if the array moves. Keep two unchanged repeats per geometry. Record actual EQ/ARC settings when known and keep them fixed. Capture QC is separate from final RIR/decay/HIL qualification.

**Offline use:** This installed tool works without internet and without Codex running. Double-click `Start-XVF-Measurement.cmd` in this project folder; it starts the local Python recorder and opens your default browser at `http://127.0.0.1:8767/`. That address means this laptop, not an internet website. Keep the recorder terminal open (it can be minimized). Opening the address alone will not start a stopped recorder. Stop with Ctrl+C in the recorder terminal after a take finishes.

The GUI, Python dependencies, USB control libraries, sweep files, profiles and guidance are local. No cloud login, CDN or online API is required. Recordings are saved under `XVF_MEASUREMENT_WORK/experiments`; OneDrive can synchronize them later when online. The application, planning notes, bundled audio dependencies, USB control directory and top-level launchers/guides were marked **Always keep on this device** for offline availability. Do not use OneDrive **Free up space** on these files. Keep the existing local Python installation at `C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`; this launcher is configured for this laptop, not a standalone installer for another PC. External manufacturer links and downloading a new EMM-6 calibration file require internet; neither is required for routine recording.

**Offline verification (6 September 2026):** A fresh local server passed with non-loopback Python connections and external DNS blocked. The page, JavaScript, CSS, status, saved profiles, excitations and both guidance routes loaded; all 17 excitation assets passed their hashes and 23 local audio endpoints were enumerated. The existing-instance launcher path also passed. This check did not disconnect Windows networking or repeat physical playback/recording. Repeat the software check with the installed Python and `tools/diagnostics/check_offline.py`.

**Latest readiness check — KRK/EMM-6 update, 6 September 2026:** 159 offline Python tests, the GUI request/profile contract check and JavaScript syntax check passed. A fresh 15-second amplified-only XVF diagnostic also passed, with EMM-6 disabled, all four microphones nonzero/unclipped, zero continuity errors, gain 10 / delay −32 before and after, and approximately 62.37 Hz per telemetry field. Independent PCM24 decoding and all 176 parent-archive file hashes passed. The GUI is running with the KRK profile available. This validates the recorder; the actual wired KRK route, speaker level/EQ/ARC and optional EMM-6 interface need physical pilot verification. [Validation report](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/validation/KRK_EMM6_20260906T122412Z/VALIDATION_REPORT.md>)

1. Connect the XVF3800 using the verified onboard linear configuration. The external microphone connections have been removed. Keep the board and cables in their documented positions.
2. After a cold power cycle, close other XVF audio/control programs and run [Prepare-XVF-24bit.cmd](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/Prepare-XVF-24bit.cmd>). Preparing USB24 reboots the board only when the width needs to change; an already-24/24 readback does not reboot it. Start or restart the recorder afterward so Windows endpoints are discovered again.
3. Double-click [Start-XVF-Measurement.cmd](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/Start-XVF-Measurement.cmd>). Open the current page at [127.0.0.1:8767](http://127.0.0.1:8767).
4. Inspect the device status before the first measurement. Confirm firmware `3.2.1 ua-io48-lin`, the onboard linear array and USB **24/24**. Confirm microphone gain **10** and system delay **−32**. These are locked campaign values checked before and after each acquisition; a mismatch needs resolution before recording.
5. Select the actual **playback output**. No output is preselected: the tool requires an explicit choice before it can play a sweep.

Use the saved profile **KRK GoAux 4 — wired campaign setup** for the first excluded P0 level/setup pilot. Fill in actual geometry, pose and obstruction; select the wired output and record speaker settings. Change the pilot phase to P1 for the subsequent formal front-position proof. Earlier profiles and recordings remain historical evidence. Old Edifier drafts migrate to KRK with old source-specific controls, calibration and output selection cleared; measured geometry is preserved for review.

Keep the server launcher running. Starting the launcher again opens an existing compatible **version-3** app on this port; an older backend receives a restart instruction. A page refresh updates the page, not a running Python backend. Use the current 8767 page and one recorder at a time.

**Development-board session limit:** XMOS documents that the XK-VOICE-SQ66 evaluation board stops processing audio after eight hours from power-on/reset. Restart the board between long sessions, while idle, then verify USB24 and gain 10 / delay −32 again before recording. USB identification can still work when audio-engine reads fail. This occurred during the 6 September check and a documented restart restored the audio engine. Do not reboot during a take. See the supplied [XVF user guide, §2.1](C:/Users/amiri/Downloads/xvf3800_user_guide_v3.2.1.pdf).

## Connect the measurement speaker

Use the **KRK GoAux 4** as the same acoustic source throughout the RIR campaign. In **Speaker settings & calibration notes**, record speaker volume, LF/HF EQ, ARC state and configuration, Windows output volume, interface output level, cable/active cabinet, and physical facing/tilt. Keep these settings and the software playback level fixed during formal measurements. Position changes follow the experiment; preserve the declared speaker-facing convention. Do not rerun ARC at each seat or room. ARC is logged separately from recorder software EQ; the GUI does not enable, disable or measure it automatically. [KRK product documentation](https://www.krkmusic.com/products/goaux-4-portable-powered-studio-monitors)

For the intended experiment, use **one wired cabinet**:

- **Preferred route:** XVF LINE OUT to one KRK RCA input, with **Output (XVF3800 Voice Processor) — Windows WDM-KS** selected. Playback and microphone capture then use the XVF clock. The normal XVF DAC duplicates the left signal on both analog outputs. Connect only one KRK input channel and confirm only the intended cabinet plays; software balance does not isolate cabinets on this XVF route.
- **Alternative wired route:** laptop/Realtek or audio-interface line output to the KRK, selecting that exact output endpoint. Direct KRK USB playback is also wired, but its driver/stream must be verified in the pilot. These playback paths and XVF capture have separate clocks. Marker checks do not automatically qualify or correct clock differences.
- Selecting Realtek while the KRK is not connected can play the laptop speakers. That is an integration test, not a KRK measurement or calibration.

Use wired input rather than Bluetooth for measurement playback. Confirm the cable route and cabinet locally before accepting a series; a Windows device name cannot establish which physical cabinet is connected. Pause phone speech during sweeps. Phone speech is useful in separate record-only direction/energy trials.

## Optional EMM-6 speaker-reference setup

This is optional and can be skipped entirely. The [reference-microphone plan](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/planning/REFERENCE_MICROPHONE_CALIBRATION_PLAN.md>) explains what to archive for later analysis.

1. Connect the **Dayton Audio EMM-6** by XLR to a microphone preamp/audio interface with the required phantom power (+15 to +48 V per Dayton). Select that interface input in **Setup → Optional EMM-6 speaker reference**; the microphone itself is not a USB device. It is separate from KRK's supplied ARC microphone. No input is chosen automatically. [Dayton documentation](https://www.daytonaudio.com/product/911/emm-6-electret-measurement-microphone)
2. Record microphone model/serial, interface gain, calibration-file path and microphone orientation. Enter its positive distance to the speaker and a placement description. A supplied manufacturer file is archived and hashed; the generic software does not automatically interpret it as a frequency correction or SPL sensitivity.
3. Choose the wired KRK output, stimulus and software playback level. Record fixed volume, EQ, ARC, Windows/interface level and speaker orientation. Document EMM-6 distance, height and facing. Keep the speaker and microphone still for repeats.
4. Press **Play & record speaker reference**. The reference starts before playback and records the sweep and tail into a separate `SPEAKER_REF_*` folder. This action is not a room-array trial.
5. Inspect noise/clipping and save repeat sweeps. An excluded level check may compare two software levels 6 dB apart at unchanged geometry; then select one level for formal work. Archive now; **no speaker correction or deconvolution is required**. Consider correction later only if synthetic-versus-real mismatch justifies it.
6. Remove the reference microphone and continue with the main Category 3 measurement button. Its availability is not required for routine trials.

Relative speaker-response characterization does not require absolute SPL calibration. It does require the correct microphone response/orientation evidence. An optional **Acoustic calibrator** section records a fitted, compatible calibrator for 10 seconds with no speaker playback. Enter its actual level, verify the displayed tone frequency and confirm the fit. The estimator examines seconds 2–8; only an accepted result offers **Use sensitivity**. That scale applies to the same microphone/interface gain and does not flatten its frequency response. Leave sensitivity unknown if no valid evidence is available.

Reference WAVs use 48 kHz FLOAT storage, which does not imply 32 bits of acoustic precision. The reference and playback may have separate sample clocks; host timestamps alone do not establish acoustic alignment. No automatic resampling or EQ is performed. Do not divide every array response by a nearby reference response: that can cancel desired room information and magnify nulls. Preserve the uncorrected RIR library and any later correction as separate derived versions.

## Fill in the six main fields

| Field | What to enter | Meaning saved with the recording |
|---|---|---|
| **Room name** | A stable friendly name, such as `Living room` | Which room the measurement belongs to; an internal room ID is assigned automatically |
| **Position name** | A stable source-location name, such as `Left chair` | Where the speaker/source is placed; an internal position ID is assigned automatically |
| **Distance (m)** | A positive number, such as `1.20` | Straight-line distance from the source reference point to the microphone-array center |
| **Device-relative angle (°)** | A number from −180 to +180; `0` is a valid angle | Your measured or estimated source bearing in the protocol diagram below; this is ground-truth metadata, not an XVF reading |
| **Obstructed** | On when an object obstructs the source-to-device path | Independent obstruction state; use optional notes to identify the object |
| **Device pose** | **Flat** or **Upright** | The nominal physical pose; it does not claim an automatically measured tilt |

Room, position, distance, angle and pose are required for a measurement. Do not put `0` in the distance field to mean unknown. Optional details such as source height, actual tilt, source facing, photographs or table construction can remain unknown; the software must not manufacture those measurements.

**Obstruction and pose are independent.** A device can be flat and obstructed, upright and unobstructed, or either other combination. “Unobstructed” also does not mean “empty table”: ordinary clutter can remain present without blocking the direct path.

The array center is midway between MIC1 and MIC2. Use a repeatable source reference point, such as the chosen cabinet's marked acoustic center. A single distance and horizontal angle do not specify source height/elevation, so they are not automatically a full three-dimensional position measurement.

## Physical direction convention

The user has specified **MIC0, MIC1, MIC2, MIC3 from left to right as viewed by the seated user**. That ordering is saved as a user-declared physical convention; channel files retain their native MIC identities.

For this protocol, mark and photograph a forward arrow pointing **away from the seated user**. In a top view:

```text
                         0° forward
                       away from seat
                             ↑

       +90° left   MIC0  MIC1  ·  MIC2  MIC3   −90° right
                              array center

                             ↓
                       ±180° behind
                         seated user
```

Positive angles turn toward the seated user's left; negative angles turn right. The physical arrow defines the reference, so another person can reconstruct the setup. Keep that reference consistent when changing flat/upright pose. Record additional tilt or rotation when it matters.

**Native XVF angles use a different convention.** The documented linear configuration reports 0° toward MIC3, 180° toward MIC0 and 90° on either side perpendicular to the microphone line. Consequently, a native 90° reading does not distinguish the protocol's forward and behind positions. Store native values separately from your entered source angle; do not overwrite one with the other or infer a unique 360° direction from this linear array alone. The firmware microphone-line coordinates also remain separate from the protocol's forward/left axes. See the user guide §3.5–3.6, including its linear-array angle diagram.

## Start one measurement

1. Put the source and device at the entered geometry. Check distance, angle, obstruction and pose, then keep both still.
2. Leave **Amplified · campaign recording** selected. The microphone gain/delay must remain 10 / −32; choosing a domain does not retune them.
3. Check the playback output and software level. Use the verified primary **1-second-gap impulse + ESS** excitation unless the setup needs its documented alternate.
4. Pause phone speech and other intentional sound. Press the main **Play & record** button once.
5. The software checks configuration, starts capture and telemetry before the stimulus, records the tail, checks the final gain/delay and preserves the evidence.
6. Wait for the result before moving anything. Read any QC or configuration reason before accepting a take.

The primary excitation is 17.22 seconds long. Capture margin and preparation/flush time make the operation longer than the file. Automatic repeat numbering identifies a subsequent measurement; another formal repeat still requires another measurement action.

**Raw / paired diagnostics** remains available for troubleshooting. Raw records one Category 1 pass; Both records a raw pass followed by an amplified pass, with two stimulus playbacks and two distinct acoustic realizations. Keep the setup unchanged through both; both passes must succeed for a complete pair. These diagnostic choices are not required for the Category 3 campaign.

Use Stop if needed and wait for recording/restoration to finish. Completed and partial evidence is retained. Keep failed/partial trials and make a new measurement after resolving the cause.

## What raw and amplified mean

| Selection | Signals saved | Intended use |
|---|---|---|
| **Amplified · campaign recording** | Category 3 MIC0–3 after common fixed gain/delay, before SHF voice processing | Default; workbook §§7.1 and 13.6.2 canonical RIR/HIL domain |
| **Raw only** | Category 1 MIC0–3 before microphone gain/system delay | Diagnostic capture and a general acoustic archive |
| **Both · diagnostic comparison** | Complete raw pass followed by complete amplified pass | Two sequential recordings, not simultaneous copies of one event |

The packed USB interface carries **six channels at 16 kHz**. Each pass uses four slots for microphones, one for a known digital continuity signal and one for postprocessed auto-select speech. Four raw plus four amplified microphones cannot fit simultaneously, even before those two diagnostic slots.

Live microphone gain is **10 (+20 dB)** and system delay **−32**, which delays all Category 3 microphones by **32 samples = 2 ms** relative to Category 1. Version 3 preserves pre/post readbacks and rejects a configuration mismatch. These are fixed common operations: no level adaptation or AGC is added to these four microphone channels. They preserve relative microphone levels and arrival differences. System delay concerns microphone/reference timing for AEC; −32 is not a measurement of room propagation or source distance.

Digital gain raises microphone signal and noise together; it does not improve acoustic SNR, though gain before transport quantization can preserve finer digital detail. It consumes headroom, so verify no Category 3 clipping. An offline multiplication/delay of raw PCM24 only approximates exported Category 3: the earlier simultaneous MIC0–2 test found `amplified[n+32] − 10×raw[n]` between 0 and 18 PCM24 counts. Dividing amplified audio cannot recover clipping. Keep the original recorded domain and its gain/delay provenance.

For later **physical HIL**, a vector already representing Category 3 must use **microphone gain 1 and system delay 0** to avoid applying them twice. The workbook also specifies reference gain 1 when already embodied; near-end-only vectors use a zero far-end reference. HIL replay is separate later work. Restore and verify live settings 10 / −32 before returning to room capture. Never normalize or align the four microphones independently.

## Sampling, direction and energy

| Item | Capability and interpretation |
|---|---|
| Native transport WAV | Stereo **48,000 frames/s**, PCM24 required for measurement mode; it carries packed slots rather than two ordinary listening channels |
| Each physical microphone | **16,000 samples/s**, with one common time base across MIC0–3 |
| USB24 precision | One LSB carries the packing marker, leaving **23 transported audio payload bits**; this does not claim 23-bit acoustic effective resolution |
| Device processing cadence | **256 samples per 16 kHz frame = 16 ms**, or 62.5 frames/s |
| Default telemetry | Full `AEC_AZIMUTH_VALUES` and `AEC_SPENERGY_VALUES` arrays; the fast logger has demonstrated approximately 60 updates/s per array. Use each pass's measured rate/gap report for its actual performance |
| Telemetry time | Host request/response timing and arrival evidence; no calibrated device sample timestamp and no guarantee that separately queried angle/energy arrays belong to the same DSP frame |
| Live screen | A status display; its refresh rate does not set the microphone sample rate or logger speed |

The four native angle and energy entries are ordered **focused beam 1, focused beam 2, scanning beam, auto-select**. Energies are uncalibrated speech-related indicators, not dB SPL, source distance or identity. Keep zero, invalid and missing states distinguishable. The optional selected-direction output has additional smoothing and can legitimately be NaN when speech is absent; faster host polling does not remove the algorithm's smoothing delay.

The underlying recorder also supports USB16, which leaves only 15 payload bits after packing. Use verified USB24 for the intended precision measurements. A wider WAV container by itself cannot establish the device's precision; inspect the saved USB-width readbacks and actual WAV format.

Audio callback timing is also separate from data continuity. Tests found a driver-unflagged continuity failure, which is why the saved known sequence is checked exactly. The successful 300-second run preserved continuity through a substantial host callback gap. Neither an empty error list nor a large host gap alone proves what happened to individual audio samples.

## Excitation and speaker level

The primary V2 file has these exact source-file times:

| Event | Time | Encoded level |
|---|---:|---:|
| Initial silence | 0–2 s | Silence |
| Start marker | 2 s onset, 20 ms long | −18 dBFS |
| Exponential sweep | 3–13 s, 80–7,500 Hz | −12 dBFS |
| Response decay | 13–16 s | No sweep playback |
| Stop markers | 16 and 16.2 s | −24 dBFS |
| Final silence | Through 17.22 s | Silence |

The optional 2-second-gap file keeps the start marker at 2 s, moves the sweep to 4–14 s, the stop markers to 17/17.2 s and ends at 18.22 s. Choose it only when the marker response has not decayed adequately before the primary sweep.

The software playback level is an **additional scalar** on these encoded levels. For example, an additional −18 dB gives a nominal sweep level of −30 dBFS before any downstream Windows/speaker controls. It does not mean −18 dB SPL or a measured acoustic level. Save the exact excitation hash and software scalar for every pass.

Keep the KRK volume, LF/HF EQ, ARC configuration, Windows/interface level, software level, cabinet, input and physical orientation fixed. The EMM-6 reference procedure is optional and archives evidence for later use; it is not required before the campaign. Relative spectral characterization does not require absolute SPL, and a microphone calibration file alone does not establish either a flat speaker or valid absolute sensitivity. During an excluded setup trial, compare software levels 6 dB apart at unchanged geometry to check compression and noise. Freeze the qualified level. Do not raise loudness merely to move microphone peaks close to full scale.

The [one-time reference plan](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/planning/REFERENCE_MICROPHONE_CALIBRATION_PLAN.md>) is the current source-characterization workflow; the earlier [relative-level checklist](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/planning/SPEAKER_CALIBRATION_CHECKLIST.md>) remains supporting context. Uncorrected measurements include speaker, room/table, objects and device/microphone effects. A future source correction needs controlled measurement geometry and validation, not blind removal of a room response. No filter is generated or applied automatically.

## Files and folders

New trial folders are stored under [XVF_MEASUREMENT_WORK/experiments](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/XVF_MEASUREMENT_WORK/experiments>). Friendly room/position names remain in the metadata, while stable room/position IDs, condition and automatic repeat numbers identify trials. A canonical name has the structure:

`JPXVF_P1_R01_T01_D01_S01_F00_NAT_CU_R01`

The exact generated ID appears in the result. Coordinates are stored in metadata rather than encoded into the filename. `P1`, `T01`, `D01` and `NAT` can be protocol defaults; they do not prove that a table/device placement or source-facing direction was physically measured. `CU` records unknown clutter for an unobstructed trial; `C2` identifies the selected obstructed condition. The obstruction boolean is retained independently. All failed trials remain available.

For the default amplified campaign measurement:

```text
<TRIAL_ID>/
  REPORT.txt
  result.json
  request.json
  SHA256SUMS.txt
  00_admin/
    trial_metadata.json
  01_photos/                         reserved
  02_raw/
    pass_01_amplified/               complete immutable capture bundle
  03_derived/
    pass_01_amplified/               microphone copies, processed_auto.wav, QC
  04_hil_exports/                    reserved, explanatory README
  05_analysis/                       reserved, explanatory README
```

Raw diagnostics instead use `pass_01_raw`; Both diagnostics have `pass_01_raw` and `pass_02_amplified`. Reserved directories are not evidence that photos, HIL vectors, RIRs or analysis have been generated. The current software does not upload photographs or record an IMU. Unknown tilt, stationarity, calibration and source-facing facts must not be presented as measurements.

Each `02_raw/pass_...` folder retains the underlying recorder's full bundle:

| File or group | Exact role |
|---|---|
| `native_packed.wav` | Original stereo 48 kHz transport, PCM24 for a verified USB24 pass. Preserve untouched; do not listen to it as ordinary audio |
| `decoded_six_channels.wav` | Six simultaneous 16 kHz channels: digital continuity, postprocessed auto-select speech, MIC0, MIC1, MIC2, MIC3 |
| `microphones_4ch.wav` | Only the four physical microphones, ordered MIC0–3, in this pass's raw or amplified domain |
| `MIC0.wav` … `MIC3.wav` | Individual microphone files extracted from that same common time base |
| `continuity_source_16k.npy` | The exact known sequence used to test missing, repeated, changed or reordered collection groups |
| `usb_playback.wav` | Actual USB playback vector, including the continuity signal. Its acoustic content depends on the selected route |
| `excitation_original.wav` and timing metadata | Exact source excitation copy and documented source-file boundaries; the applied software scalar is recorded separately |
| `telemetry/` | Raw/native and timestamped logger records, backend evidence, measured rate/gap summaries and source/library provenance |
| `commands/`, parameter/identity/configuration files | Exact command receipts, device state, mux/domain, gain, delay and USB-width readbacks |
| `capture_gain_delay_lock.json`, `gain_delay_after_capture.json` | Version 3 expected/observed gain 10 and delay −32 before and after capture; failures remain evidence |
| `capture.json`, `playback.json` | Capture/playback timestamps, sample counts, stream format, callback timing/status and route information |
| `quality.json`, `result.json`, `REPORT.txt` | Individual checks, pass outcome and remaining limitations |
| `source/`, `SHA256SUMS.txt` | Code snapshot and evidence hashes for reproducibility |

The guard channel is a **digital continuity reference**, not the measured far-end acoustic reference and not an extra microphone. The processed speech channel includes processing such as noise suppression/AGC; it must not substitute for a physical microphone in RIR recovery.

`03_derived/pass_...` supplies convenient `MIC0.wav`–`MIC3.wav` copies, the extracted `processed_auto.wav`, `qc_summary.json` and `provenance.json`. “Derived” here does not mean deconvolved RIR: no new frequency response, denoising, alignment or calibration is implied. The complete original capture remains in `02_raw`. Future analysis must identify source hashes, processing version and parameters and create new outputs. Do not overwrite frozen audio, metadata or failed trials; record corrections as new evidence or a new version outside the frozen originals.

### Separate source-reference and optional calibrator archives

The dedicated setup actions create their own folders under the experiments directory, separate from room trials:

```text
SPEAKER_REF_<unique_id>/
  request.json
  reference/
    reference_original.wav          all opened reference channels
    selected_reference.wav          chosen input, unchanged scale
    capture.json
    quality.json
    calibration/                    original supplied evidence, when present
  ...                               exact stimulus and playback receipt
  result.json
  REPORT.txt
  SHA256SUMS.txt

REFERENCE_CAL_<unique_id>/           optional fitted-calibrator recording
  request.json
  reference/...
  calibration.json                  only for an accepted estimate
  result.json
  REPORT.txt
  SHA256SUMS.txt
```

Enter the prior speaker-reference run ID/path in the saved setup’s **Reference notes**, and use **Calibration label** to record the correction state, initially `source correction not applied`. This preserves the link in campaign metadata; it does not automatically apply a filter. Routine array passes do not need reference WAVs. No final speaker filter is stored unless a later, separately validated process creates one. Keep original source recordings, uncorrected RIRs and future corrected derivatives distinct.

## Read the result before continuing

| Result | Meaning |
|---|---|
| **PASS** | A record-only run passed its implemented acquisition checks; not acoustic calibration or direction-accuracy certification |
| **REVIEW** | A sweep measurement passed implemented capture and marker checks; final RIR recovery, geometry, level and repeatability still require scientific review |
| **RETAKE** | A partial/stopped recording or unreliable acoustic markers; preserve it and repeat after addressing the condition |
| **INVESTIGATE** | Control, playback, restoration, framing or digital continuity failed; inspect the detailed evidence before another accepted run |

An intact-looking WAV can still contain repeated or reordered sample groups. Digital continuity failure takes priority over a marker-only problem and must not be repaired into a passing scientific recording. A diagnostic paired measurement needs both passes. Gain/delay mismatch is also a configuration failure. Read the per-pass reasons as well as the group headline.

A saved speaker-reference recording still needs source-response and timing review. A **PASS** from the optional calibrator action applies only to its implemented input/tone checks and sensitivity estimate, not to speaker correction or RIR acceptance.

Marker QC uses separate templates derived from the actual played 48 kHz file and all four microphones. It checks candidate confidence, the 200 ms stop repeat and the start-to-stop interval. A passing marker check does not establish a calibrated direct-path arrival. Timing mismatches are not automatically interpreted as constant clock drift, and microphone recordings are not automatically resampled or independently aligned.

## How to use the recordings next

Document and fix the wired KRK settings, then make an excluded Category 3 array setup/level trial. An EMM-6 speaker-reference archive is optional and may be skipped. If collected, preserve it for later comparison and remove the reference microphone before routine trials. No source correction or deconvolution is required at this recording stage.

For P1, collect two formal front-position amplified repeats, separated by another condition/time interval as the workbook recommends. Extract four synchronized RIRs from the **sweep segment**, excluding the pre-sweep marker and using the matching inverse filter. Compare timing, level, shape, noise and clipping with criteria set from that one-position proof. Preserve a common time base and scale across MIC0–3 and retain the uncorrected library.

Only then proceed to P2 physical XVF HIL at unity microphone gain / zero system delay, and P3 six-position geometry screening, including directly behind the device. A future source-corrected derivative or physical playback filter must be independently reviewed and versioned; it is not an automatic condition of a successful capture.

## Workbook sections 6–12: what this workflow covers

| Workbook section | Tool/evidence connection | Work that remains physical or analytical |
|---|---|---|
| **6 — Windows bring-up and one-button logger** | Explicit format/state checks, microphone capture, fast telemetry, command receipts, continuity and immutable bundles | Photograph/verify the current hardware and cable route; repeat reconnect checks after relevant hardware changes |
| **7 — Exact output inventory** | Category 3 campaign map, locked pre/post gain/delay, exact native telemetry names and separate processed diagnostics | Optional ASR-versus-postprocessed comparison, angle accuracy/lag experiments and physical HIL qualification |
| **8 — Excitation and RIR timing** | Verified primary/alternate V2 files, playback scalar, complete capture and marker QC | Check actual acoustic decay and level; implement/validate sweep-only deconvolution and any justified common clock correction |
| **9 — Coordinates, naming and folders** | Friendly names plus stable IDs, device-relative geometry, native angles kept separate, MIC0–3 identities and canonical trial folders | Photograph the forward axis and physical setup; provide additional coordinates/elevation when needed |
| **10 — Room/device/source planning** | Required simple room/position/distance/angle/obstruction/pose controls; saved protocol defaults and optional details | Measure actual heights/tilt, source facing and room/table properties; verify the wired KRK route, fixed volume/EQ/ARC/output level and orientation |
| **11 — Staged pilot** | Separate one-time source setup, Category 3 formal repeats, optional diagnostics and every failed trial | P1 accepted RIR pair → P2 physical HIL → P3 six-position screen → selective pose/facing expansion; avoid launching the full 48-case matrix first |
| **12 — Trial record and QC** | Metadata snapshot before acquisition, pass/group outcomes, hashes and versioned evidence | Movement verification, RIR extraction, between-repeat comparison and final PASS/REMEASURE/EXCLUDE/INVESTIGATE scientific decision |

The workbook's historical external-array descriptions and unresolved firmware notes are superseded by the user's current onboard-array setup and later evidence. Its earlier “do not build yet” stage is also superseded by the user's explicit request to build this tool. The simpler front page changes data-entry burden; it does not turn missing physical measurements into known facts.

## Validation evidence

**Version 3 software validation completed on 6 September 2026 UTC (5 September locally): 164 offline tests pass** — 116 application/workflow tests, 40 playback/reference/hash tests and 8 telemetry tests. JavaScript syntax and browser checks also pass. Reference tests cover exact FLOAT preservation, calibration binding, insufficient coverage, clipping, cancellation and failed cleanup. The actual reference microphone remains unconnected and untested; no speaker correction has been generated or physically qualified.

A fresh 15-second amplified-only hardware diagnostic passed: all four microphones nonzero/varying, no rail samples or fully zero one-second windows, 720,000 native frames, 235,127 decoded samples per channel after a common startup crop, and zero continuity mismatches. Gain 10 / system delay −32 were verified before and after. Direction and speech-energy reads averaged 61.27 Hz per field; these are host transaction rates, not atomic device-frame timestamps. Reference recording was disabled and speaker playback was off. Independent PCM24 decoding and all 179 parent-manifest file hashes passed.

The first attempt retained clean microphone data but failed archive verification on a Windows `PermissionError` opening a copied source file. The GUI reported failure and no parent completion marker was published. Hashing now retries only permission failures while opening a file, at most seven attempts over 1.175 seconds; persistent or subsequent read failures still fail. The successful take is a new archive. A short timeout in an offline telemetry subprocess fixture was also corrected; all eight telemetry tests then passed.

Evidence: [version-3 validation report](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/validation/GUI_V3_20260906T020708Z/VALIDATION_REPORT.md>) and [amplified hardware diagnostic](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/XVF_MEASUREMENT_WORK/experiments/TAKE_20260906T021128_508059Z_c8973b/REPORT.txt>).

**Earlier version-2 validation completed on 5 September 2026:** 108 hardware-free tests passed (88 application/pipeline tests, 12 playback tests and 8 telemetry tests). These include actual PCM24 serialization and demultiplexing with independently encoded fixtures, excitation routing, deliberate sample corruption, metadata validation, sequential-pass failures, cancellation, writer shutdown and atomic manifest publication.

The version-2 visible browser GUI was tested for required fields, Flat + Obstructed, saved profiles, legacy migration, startup gating, per-pass results and archive links. The final page reported no browser console errors.

A real GUI-initiated **15-second raw pass followed by a 15-second amplified pass** passed on the connected XVF. All four microphones in each domain were nonzero and varied, with no clipping or fully-zero one-second windows. Each pass captured 720,000 native stereo frames and retained 235,127 decoded samples per channel after the documented common startup crop. Independent byte audits found zero framing errors, zero digital continuity mismatches and exact agreement between the native carrier and saved microphone files. The group manifest verified all 330 listed files. Native direction/energy response logging averaged approximately **60.4–61.2 reads/s per array**, with no parse errors; these are host read rates, not proof of fresh or simultaneous device frames.

This was a **silent recording-pipeline diagnostic**, with no generated speaker stimulus or measured geometry. It does not qualify Edifier acoustic level, speaker response, marker reliability, angle accuracy or RIR repeatability. The actual KRK Category 3 pilot remains a physical validation step. An EMM-6 reference session is optional.

Evidence: [earlier version-2 GUI validation report](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/validation/GUI_V2_20260905T233058Z/VALIDATION_REPORT.md>) and [real two-pass capture report](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/XVF_MEASUREMENT_WORK/experiments/TAKE_20260905T233852_402856Z_dca238/REPORT.txt>).

Supporting evidence already available includes verified true PCM24 packing, the fixed Category 1/3 gain-delay relationship, two consistent callback-playback sweep captures, and an independently audited 300-second recording with zero digital continuity mismatches. See the [sampling/source review](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/planning/SAMPLING_AND_SPEAKER_FINDINGS.md>), [raw/amplified comparison](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/planning/TRUE_PCM24_INDEPENDENT_REVIEW.md>), [playback/marker investigation](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/planning/LAPTOP_MARKER_REVIEW.md>) and [300-second independent byte audit](<C:/Users/amiri/OneDrive/Documents/ChatGPT/XVF Measurement/tmp/audit_buffer150_300s_pcm24_independent.json>).

Primary references: the supplied [master workbook V4](<C:/Users/amiri/Downloads/Just_Peachy_H2_XVF3800_Master_Workbook_and_Experiment_Plan_V4.docx>), [XVF3800 programming guide v3.2.1](<C:/Users/amiri/Downloads/xvf3800_programming_guide_v3.2.1.pdf>) §4.1.2–4.1.4, and [XVF3800 user guide v3.2.1](<C:/Users/amiri/Downloads/xvf3800_user_guide_v3.2.1.pdf>) §§3.5–3.6, 4.2.2 and 4.3.
# Reviewed background-noise recordings

Recent takes can show **Background noise present** with a **Noise review** link. This annotation retains the original recording and acquisition status; it does not turn RETAKE into PASS. For the five Loeb Caf captures reviewed on 2026-09-07, exact background-reference sample ranges, hashes, and later-processing instructions are saved in `validation/LAST_FIVE_NOISE_REVIEW_20260907/noise_annotations.json`. Read `NOISE_REVIEW.md` in that folder before noise reduction. Post-sweep room decay is part of the RIR, not automatically a noise-only reference. Original audio must stay unchanged; any denoised RIR is a separate derivative.
