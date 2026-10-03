# Just Peachy mode and recording guide

> Current October3 update: **v28, desktop-first startup**. Use the ten desktop
> shortcuts; choose **Exit to desktop** in the main manager to close normally.
> Four recording slots remain. See [DESKTOP_GUIDE.md](DESKTOP_GUIDE.md) and
> DESKTOP_RELEASE_INDEX.json. Earlier v27 measurements below remain historical.

The current prepared CM5 release is **field-runtime-v28**. It offers ten combinations through one offline frontend, with NeMo TitaNet and ReDimNet both available. Sherpa ONNX ASR and punctuation remain selected. The Pi stays at the desktop after login; a shortcut opens the app idle with capture off; display orientation is270 and the viewport480×800. Current validation establishes execution, controls and recording integrity, not superior speaker-recognition accuracy.

## Available combinations

| Profile / shortcut suffix | Diarizer | Speaker embedding or identity | Input and limit |
|---|---|---|---|
| baseline | Pyannote | ReDimNet | Microphone,120s |
| baseline-titanet | Pyannote | NeMo TitaNet | Microphone,120s |
| baseline-anonymous | Pyannote | ReDimNet for anonymous continuity | Microphone,120s |
| d1-delayed | Nemotron-3 Delayed | ReDimNet | Microphone,120s |
| d1-delayed-titanet | Nemotron-3 Delayed | NeMo TitaNet | Microphone,120s |
| d1-anonymous | Nemotron-3 Delayed | Native anonymous slots; embedding bypassed | Microphone,120s |
| d1-streaming-saved | Nemotron-3 Streaming | ReDimNet | Saved WAV,30s |
| d1-streaming-titanet-saved | Nemotron-3 Streaming | NeMo TitaNet | Saved WAV,30s |
| d1-chunk52-saved | Nemotron-3 Chunk52 | ReDimNet | Saved WAV,120s |
| d1-chunk52-titanet-saved | Nemotron-3 Chunk52 | NeMo TitaNet | Saved WAV,120s |

Desktop files are named `just-peachy-field-runtime-v28-PROFILE.desktop`, replacing PROFILE with the table value. Ten profile shortcuts plus rollback are retained; older generated shortcuts were backed up and archived. Use the visible profile chooser to change selection while idle. If opening another shortcut, close the current idle manager first: duplicate ownership is rejected.

Pi terminal example:
~~~sh
/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v28-profiles/bin/launch-profile --profile d1-delayed-titanet
~~~
Substitute another exact table profile. Saved inputs must be mono16kHz PCM16 WAV, at most32MiB, under `/home/peachyprototype/JustPeachy`. Streaming/Chunk52 microphone routes are unavailable. Nemotron Delayed buffers about21.3s before its regular output; short runs can emit speaker results at Stop. This is a latency tradeoff, not a missing recording.

## Record, stop and save

1. Select a profile and choose **New recording**.
2. In the broker choose a new microphone recording or the supported saved-WAV route.
3. Create the audio draft and choose **Audio off**, **Processed**, or **Raw+processed** where offered. Confirm the raw-recording notice when selecting it.
4. Press Start and provide the normal in-app consent. Nothing starts merely by opening a shortcut.
5. Press Stop and allow source/model/archive cleanup to finish. Then Save and Return to modes.
6. Close the recording broker. Wait for the manager's verified independent local backup before another recording. Saved recordings opens the read-only history.

The release reserves four recording slots; all four remain in v28; the motion integration recording is preserved in v27. There are16 total manager/helper launch slots; each idle manager launch is bounded to24h. Each recording uses separately reserved helper slots. Closing/reopening the manager consumes another launch, so avoid unnecessary reopen loops. Stop is bounded automatically at the input limit. Failed/cancelled/finished slots remain consumed. After exhaustion follow the desktop-aware renewal requirements below.

## Audio formats and clocks

Audio off keeps events/metadata without recorded audio. Processed stores the exact16kHz mono model-input float stream and WAV. Raw+processed additionally stores physical MIC0–MIC3 as interleaved signed32-bit little-endian PCM at16kHz. The firmware transports its packed six-channel stream over48kHz stereo S32LE I2S. The raw recording is **not48kHz ADC audio** and is not the ordinary processed O0/O1 tap.

The raw metadata identifies four channels, firmware route, sample clocks, packing prefix/tail and source/processed counts. Candidate22 recorded85919 paired samples with zero packing-marker errors, then restored every changed route. Shared sample-clock indexing does not imply equal acoustic latency between raw and processed paths. Preserve RAW_CAPTURE metadata with the PCM; do not infer format from the extension.

## Speaker galleries

TitaNet and ReDimNet use separate model/revision/tap/gain namespaces. Existing personal ReDimNet data is preserved. TitaNet's separate gallery is empty, so Unknown identities are expected until a future explicitly consented enrollment. No vectors are converted or compared across embedding models. Anonymous modes do not assign personal names. Baseline anonymous still uses ReDimNet continuity; D1 anonymous bypasses embedding extraction.

## Copy to the PC and renew

Use `operator-tools-v1/export_runtime_recording_v4.py` under `C:/Users/amiri/Documents/GitHub/just-peachy/Resumes/imu_integration_20261002`; its maintained instructions are in `README_RUNTIME_RECORDING_OFFLOAD_V4.md`. Copy the original and independent Pi-local backup separately into new private PC directories. Each command checks complete membership, sizes, SHA256 and full readback before BACKUP.json. The Pi originals remain untouched.

PowerShell example (replace the previous utility and NEW_DESTINATION with the actual latest receipt and an absent private directory):
~~~powershell
& "C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B "C:/Users/amiri/Documents/GitHub/just-peachy/Resumes/imu_integration_20261002/operator-tools-v1/export_runtime_recording_v4.py" --local "G:/Just_Peachy_N1/20260924_campaign/local" --private "G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928" --prior-closure "G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/NATIVE_CLOSURE_V315.json" --previous-inspection PREVIOUS_RECEIPT --candidate-install "G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/field-runtime-v28-install" --active-install "G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/field-runtime-v28-install" --slot recording-01 --root-kind original --output NEW_DESTINATION
~~~
CMD/Anaconda uses the same arguments after `python -B "C:/Users/amiri/Documents/GitHub/just-peachy/Resumes/imu_integration_20261002/operator-tools-v1/export_runtime_recording_v4.py"`. Then use that output as PREVIOUS_RECEIPT, change root-kind to local and choose a different destination.

For a fresh batch, preserve completed recordings and local backups first.
Desktop-first renewal: see DESKTOP_GUIDE.md. Do not execute the older motion renewal wrapper unchanged; its launcher would restore automatic startup and its old Close-button selector is obsolete.

## Mounted motion

All profiles share the integration described in [MOTION_GUIDE.md](MOTION_GUIDE.md).
Live beams stay microphone-relative; existing location logic uses trusted relative
rotation correction. Acceleration/gaps invalidate spatial trust. Voice-only rules
and plain saved WAVs do not gain invented location evidence. Settings -> Orientation
graphic toggles an upper-right diagnostic; tap it to zero the visual only.
It is hidden by default. Automatic quiet reference acquisition needs no manual zero.

## Validation scope

Before the motion change, all ten routes had scoped native functional evidence, including nonempty saved captions, both real embedding paths, history/data actions, Audio off/Processed and paired raw recording. Actual broker and child processes deny IPv4/IPv6 sockets; local assets are used. Physical cable-disconnected coldboot, touch, battery endurance and noisy-world accuracy remain operator validation tasks. Use FIELD_VALIDATION.md, keeping each run within the actual duration/slot/storage limits.

The changed shared motion path passed one new D1/ReDimNet live recording; all ten profile pins were checked. Other unchanged model/raw routes were not rerun. Three slots remain.
