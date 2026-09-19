# H2 Pre-XVF Software Baseline Handoff

Date: 2026-09-04  
Status: H2 selected; Windows software baseline ready for physical XVF3800 experimentation  
Branch at freeze: `codex/edge-component-expansion`  
Pre-freeze parent commit: `2902ce9b98efedd63ccbc88b47645097b339585f`  
Freeze reference: the commit containing this document and annotated tag `h2-pre-xvf-baseline-v1`

## 1. Current project status

H2 is the only speech pipeline selected for continued product development. The current software is sufficiently streamlined to stop broad component selection and begin physical XVF3800 characterization. This freeze is the reference point immediately before result-affecting XVF integration, so later changes in WER, diarization, speaker attribution, latency, runtime, memory, false-name behavior, and short-turn handling can be compared with an identifiable pre-XVF state.

The repository still contains historical evaluators and supporting research code. Their presence does not reopen model selection. The active Windows edge application is `app.edge_speech_pipeline`, launched through `scripts/run_edge_speech_pipeline.ps1`.

The local real-world measurement workbook reports that the XVF3800 already enumerates and runs on the Windows desktop and that a first host-polled telemetry sample has been captured. That sample is interface evidence only: exact endpoint selection, firmware topology, microphone order, units, timing, and angle mapping remain to be verified before fusion or accuracy claims.

## 2. Exact H2 architecture

```text
live microphone or WAV/FLAC simulation
                |
                v
fast normalize/resample to mono 16 kHz
                |
                v
append-only PCM16 source-clock journal
       |                         |
       v                         v
Sherpa-ONNX Giga stream     Pyannote ONNX segmentation
ASR partials/finals         speech and overlap regions
       |                         |
       |                    shared ReDimNet2-B2 worker
       |                         |
       |                 +-------+------------------+
       |                 |                          |
       |          session-local clustering    enrolled-profile scoring
       |          and Speaker_N continuity    and safe name gating
       |                 |                          |
       +-----------------+--------------------------+
                         |
                         v
               timestamped event/session output
                         |
                         v
            final-only learned punctuation/casing
            raw ASR text retained separately
                         |
                         v
                    CLI or Tk GUI
```

The journal is the only audio fan-out point. ASR and speaker processing own independent cursors, so a slow consumer cannot evict another consumer's PCM. A real device overflow or exhausted raw reserve is fatal and explicit rather than silently reported as normal progress.

One persistent ReDimNet2-B2 ONNX session supplies embeddings for both anonymous clustering and enrolled-speaker comparison. Session-local cluster centers accumulate evidence and preserve `Speaker_N` continuity. Enrolled names require the frozen score threshold, Top-1/Top-2 margin, and minimum evidence duration. Until enough evidence exists, the application keeps an anonymous label or marks a candidate tentative rather than forcing a name.

Terminology is intentionally explicit. The edge GUI displays session-local `Speaker_N` labels and uses an internal anonymous state; before any speaker decision it may show `Speaker_?`. The broader H2 product-mode contracts use `Unknown`/`Unknown_N` for unmatched identity and expose `Unknown_N` to users as `Speaker_N` in anonymous modes. This distinction should be preserved when the XVF adapter is added.

Sherpa emits immediate partials and finalized utterances. Partial display text receives casing only. The Edge-Punct-Casing model runs once on each final utterance, and the event record keeps immutable raw `text` separately from punctuated `display_text`, model identity, checksum, status, timing, and fallback information. Detected overlap is recorded as uncertain attribution; the system does not invent a word-level two-speaker split.

The current `SpatialEvidence`/`SpatialEvidenceProvider` contract reserves source-clock fields for energy, angle, angle confidence, direction change, and provider identity. The default provider is inactive and cannot affect segmentation, clustering, identity, or text. The broader H2 contracts also anticipate beam/state telemetry and IMU motion events. A physical XVF bridge must preserve raw native values before mapping them into any normalized contract.

## 3. Windows launch

From PowerShell:

```powershell
Set-Location "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
.\scripts\run_edge_speech_pipeline.ps1 gui
```

If the dedicated environment does not exist, run the one-time setup first from PowerShell or Anaconda Prompt:

```powershell
Set-Location "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
.\scripts\setup_edge_speech_pipeline.ps1
```

The GUI accepts a selected Windows microphone, a WAV/FLAC simulation file, live microphone enrollment, or labelled enrollment WAV files. It writes local session audio, events, labelled transcripts, a readable transcript, asset/policy receipts, and no-drop telemetry under `edge_speech_sessions`; local enrolled profiles are stored under `edge_speech_profiles`. Both directories are intentionally excluded from Git.

## 4. Important model and runtime assets

All runtime assets are local and checksum-bound; startup does not download model weights.

| Component | Runtime asset | Format | SHA-256 |
|---|---|---|---|
| Sherpa Giga encoder | `encoder-epoch-99-avg-1.int8.onnx` | INT8 ONNX | `32c98281c7bd8b63e3e142d007251b37f120572e8fdea9a4f5a79ce22b10ec4f` |
| Sherpa Giga decoder | `decoder-epoch-99-avg-1.onnx` | FP32 ONNX | `9da02b77cb08826756ec6a88635f35a40374e4164e7c6359121a9145958a6ceb` |
| Sherpa Giga joiner | `joiner-epoch-99-avg-1.int8.onnx` | INT8 ONNX | `831477d390e59a61f1b6a6f763b9903e6c6366ff6034f1ddba613be82637122f` |
| Sherpa tokens | `tokens.txt` | Text | `49e3c2646595fd907228b3c6787069658f67b17377c60aeb8619c4551b2316fb` |
| Edge-Punct-Casing | `model.int8.onnx` | INT8 ONNX | `9d611f445fe4a46186080fe161be6059d87d72eb88d3a8cb00c1a06e83a6067e` |
| Punctuation vocabulary | `bpe.vocab` | Text | `e118b7ad88c54db562517df49e1cffd4836d166c34fb190fd311d7f34eb238f5` |
| ReDimNet2-B2 | `redimnet2_b2_fp32.onnx` | FP32 ONNX | `5c1a8635cba0d4648463f3b6d30c5a6137bc38d1200ab00c5944400aaa7b5609` |
| Pyannote Segmentation 3.0 | `pyannote_segmentation_3_0_fp32.onnx` | FP32 ONNX | `b4b65085bbf2cc455565696604c87fedade1359aa6ddfac5d726d69124d5069a` |

The default runtime is mono 16 kHz, CPU-only ONNX/Sherpa inference. Current frozen policy values include a `0.35` clustering threshold, `0.5128856897354127` identity score threshold, `0.03` identity margin threshold, and `2.0 s` minimum identity evidence. These values are provenance-bearing baseline settings, not parameters to retune during initial XVF bring-up.

## 5. Validation already completed

The bounded Windows evidence recorded in `BUILD_VALIDATION_REPORT.md` includes:

- 6 focused tests passed for journal replay, identity gating, spatial-contract inactivity, checkpoint-bound profiles, raw/punctuated text handling, and overlap uncertainty;
- all 8 required runtime assets passed SHA-256 validation;
- a 22.26-second accelerated common-path WAV smoke completed with both inference cursors at the full source duration;
- zero dropped frames in that smoke;
- Windows punctuation execution passed, preserving raw uppercase ASR separately from learned display text;
- the exported bundle revalidated all 8 assets and executed punctuation from its own exported paths on Windows.

This is bounded integration evidence, not a new large evaluation campaign, punctuation-accuracy study, XVF qualification, or ARM64 qualification. Do not rerun the broad model-selection campaign for this handoff.

## 6. Raspberry Pi export and purchased CM5 context

The local Raspberry Pi export is approximately 220.2 MB of logical files. It contains the eight model/token assets, runtime source, pinned ARM64 requirements, launcher, license/provenance records, and `bundle_manifest.json`. The bundle has been checksum-validated and exercised from its exported paths on Windows. Its classification remains `PORT_REQUIRES_WORK` / `EXPORTED_UNQUALIFIED_ON_ARM64`.

The purchased first prototype is a Raspberry Pi Compute Module 5 with **2 GB RAM**, **32 GB eMMC**, **no Wi-Fi**, and **no Bluetooth**. The purchase also includes a CM5 IO board, cooling, Raspberry Pi power supply, BMI270 accelerometer/gyroscope breakout with I2C cabling, camera and camera cables, buttons, and prototype wiring/accessories. Initial access must use wired Ethernet and/or USB as appropriate.

**CM5 hardware qualification has not happened.** Do not describe this system as using a 4 GB CM5 and do not infer real-time, memory, thermal, audio, or wheel compatibility from the Windows export. The actual 2 GB device is the product-memory gate; sustained swap dependence, hidden resampling, dropped data, or thermal throttling fails that gate.

## 7. Current XVF3800 experiment plan

The XVF3800 remains the real physical DSP. First finish Windows characterization of the exact owned board, firmware/configuration, USB endpoints, channel formats, microphone geometry, control interface, update timing, reset behavior, and packed capture/injection paths. Candidate outputs and controls to verify include:

- processed ASR mono audio and the postprocessed auto-select stream;
- raw or amplified MIC0-MIC3, AEC residuals, and packed six-channel capture;
- packed HIL signal injection and its required 48 kHz/channel layout;
- focused and scanning/free-running beam azimuths;
- processed/selected direction-of-voice and beam-selection state;
- focused, scanning, and selected speech-energy values;
- AEC convergence, path-change state, RT60, counters, and reset controls.

The local workbook identifies candidate host queries such as `VERSION`, `--dump-params`, `AEC_AZIMUTH_VALUES`, `AEC_SPENERGY_VALUES`, `AUDIO_MGR_SELECTED_AZIMUTHS`, `AEC_AECCONVERGED`, `AEC_AECPATHCHANGE`, and `AEC_RT60`. Treat these as discovery candidates until the exact host utility version, firmware image/configuration, native output names, units, valid/invalid encodings, and timing behavior are captured from the owned board.

The first host-polled telemetry sample is not an angle-accuracy result: it has no synchronized audio, ground-truth source path, or event labels, and its median polling interval was about 234 ms with a maximum observed gap of about 579 ms. Replace one-process-per-value polling with a persistent connection or library call when the board/tooling permits, timestamp every request/response against a host monotonic clock, and never imply that separately polled fields are atomic.

## 8. RIR, convolution, and physical XVF HIL workflow

```text
physical source
  -> room, table, enclosure, port, and microphone acoustics
  -> synchronized MIC0/MIC1/MIC2/MIC3 capture
  -> four common-time-base RIRs
  -> convolve clean speech separately with h0/h1/h2/h3
  -> preserve relative delay and level; add controlled coherent noise/scenes
  -> pack four synthetic microphone signals in the verified XVF input format
  -> inject into the physical XVF3800
  -> let the real XVF perform beamforming, AEC/noise processing, and selection
  -> capture actual XVF speech audio plus synchronized native telemetry
  -> feed the resulting mono speech stream into unchanged H2
  -> compare against the frozen pre-XVF metrics and real acoustic playback
```

Deconvolve the sweep separately for MIC0-MIC3 without independently normalizing channels. Preserve direct-path arrival differences, relative level, one untouched raw multichannel recording, excitation hashes, channel map, geometry, firmware/configuration, processing version, QC, and repeat history. The combined room/table/device/microphone response is the desired simulation input; do not try to mathematically remove the device enclosure or port response.

The local `Just_Peachy_XVF3800_Excitation_and_Logging_Pack_V2.zip` is a prepared measurement input, not part of the Git freeze. It contains deterministic 16 kHz and 48 kHz 80-7,500 Hz sweeps, a speaker-safe 20 ms marker, primary 1-second marker-to-sweep files, 2-second alternatives, exact timing/sample indices, SHA-256 hashes, a 48-trial plan, trial/output templates, and a synchronized XVF/IMU metadata schema. Use the 1-second-gap file first and switch to the 2-second variant only if measured marker decay remains materially above the noise floor. The ZIP, master workbook, future captures, RIRs, user enrollment audio, and generated result directories remain outside Git.

## 9. Why Windows comes first

Windows is the research host for rapid endpoint discovery, RIR extraction, convolution, scene generation, telemetry logging, visualization, packed HIL replay, batch comparison, and debugging. It has better working storage and makes exact hardware receipts and failure analysis easier. This is an experimental sequencing choice, not a change to the deployment target.

After the Windows/XVF path is stable, move the same frozen production-style H2 runtime, validated XVF transport/adapter, audio-only fallback, telemetry contract, replay vectors, and acceptance tests to the purchased 2 GB CM5. Generate large convolution sets and research plots on the desktop; transfer only frozen qualification vectors and the required runtime assets to the CM5.

## 10. Research principle and fine-tuning status

Do not duplicate XVF functions such as beamforming, AEC, or noise suppression in software unless a specifically designed ablation requires it. Use RIRs to synthesize synchronized microphone-domain inputs, route them through the **physical XVF3800**, and evaluate the real DSP outputs.

No ASR or speaker-embedding fine-tuning has been selected or performed for this transition. First characterize the actual XVF output, integrate it with unchanged H2, compare synthetic HIL replay with matched real recordings, and identify the remaining failure mode. Fine-tune Sherpa Giga or ReDimNet2-B2 only if controlled evidence shows representation failure after output-path, synchronization, segmentation, policy, and timing problems have been addressed.

## 11. Immediate next steps

1. Finish the exact XVF output and control inventory, including firmware/configuration identity and raw examples.
2. Verify the physical microphone geometry, MIC0-MIC3 channel order, firmware topology, angle convention, and signal domains.
3. Replace ad hoc polling with synchronized, persistent telemetry logging and measure update rate, lag, jitter, drift, loss, stale values, invalid states, and reconnect behavior.
4. Capture microphone-domain marker/sweep measurements with frozen playback, gain, geometry, and Windows enhancement settings.
5. Recover four synchronized RIRs with shared timing, relative level, repeatability checks, hashes, and QC receipts.
6. Validate raw capture -> four-channel synthetic convolution -> packed physical-XVF injection end to end.
7. Compare matched real acoustic playback with RIR/HIL replay before scaling the scene matrix.
8. Test the candidate XVF processed-audio outputs using unchanged H2 and frozen metrics.
9. Run controlled audio-only, angle, energy, angle+energy, and session-memory combinations with missing/stale-metadata fallback.
10. Move the frozen workflow and qualification vectors to the purchased 2 GB CM5, then measure native memory, CPU, thermals, latency, storage, continuity, reconnect, and sustained real-time behavior.

## 12. Freeze boundaries

This baseline does not include model caches, virtual environments, local sessions, raw audio, RIR recordings, enrollment recordings/profiles, temporary logs, secrets, large result directories, or machine-specific XVF reference binaries. The repository contains source, configuration, tests, launch instructions, small provenance records, and this handoff. No model architecture, threshold, training state, or XVF fusion policy was changed for the freeze.
