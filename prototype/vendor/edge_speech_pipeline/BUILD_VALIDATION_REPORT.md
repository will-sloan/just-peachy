# Build and Validation Report

Date: 2026-09-01  
Status: `WINDOWS_DEMO_VALIDATED__ARM64_TARGET_PENDING`

## Delivered

- New isolated runtime, CLI, and Tk GUI; frozen research code and evidence were not altered.
- Live microphone and WAV streaming through one common path.
- Unlimited start/stop live enrollment and WAV enrollment with duration, level, clipping, and embedding-consistency checks.
- Separate loading indicators and audio-clock timers for transcription and enrollment.
- Raw-preserving learned punctuation/casing on final utterances and explicit overlap-uncertain transcript events.
- Native streaming Sherpa Giga ASR plus ONNX Pyannote segmentation and ReDimNet2 embedding.
- Anonymous speaker labels and frozen H2 score + Top-1/Top-2 margin + evidence gate for enrolled names.
- JSONL, Markdown, audio journal, telemetry, model identity, and failure exports.
- Inactive timestamped XVF3800 evidence contract.
- Checksum-bound Raspberry Pi bundle with no model downloads.

## Exact components

| Component | Format | Bytes | SHA-256 |
|---|---:|---:|---|
| Sherpa Giga encoder | INT8 ONNX | 187,823,992 | `32c98281c7bd8b63e3e142d007251b37f120572e8fdea9a4f5a79ce22b10ec4f` |
| Sherpa Giga decoder | FP32 ONNX | 2,092,566 | `9da02b77cb08826756ec6a88635f35a40374e4164e7c6359121a9145958a6ceb` |
| Sherpa Giga joiner | INT8 ONNX | 259,335 | `831477d390e59a61f1b6a6f763b9903e6c6366ff6034f1ddba613be82637122f` |
| Sherpa tokens | Text | 5,048 | `49e3c2646595fd907228b3c6787069658f67b17377c60aeb8619c4551b2316fb` |
| Sherpa online punctuation | INT8 ONNX | 7,490,500 | `9d611f445fe4a46186080fe161be6059d87d72eb88d3a8cb00c1a06e83a6067e` |
| Punctuation BPE vocabulary | Text | 149,430 | `e118b7ad88c54db562517df49e1cffd4836d166c34fb190fd311d7f34eb238f5` |
| ReDimNet2-B2 | FP32 ONNX | 16,025,408 | `5c1a8635cba0d4648463f3b6d30c5a6137bc38d1200ab00c5944400aaa7b5609` |
| Pyannote Segmentation 3.0 | FP32 ONNX | 5,925,265 | `b4b65085bbf2cc455565696604c87fedade1359aa6ddfac5d726d69124d5069a` |

Sherpa Giga was already natively ONNX. The two speaker graphs are the existing checksum-preserved portable exports with prior bounded Windows native-versus-ONNX parity passes. No thresholds were retuned.

## Measured Windows performance

Model microbenchmark on the current Windows/x86-64 host:

| Operation | Threads | Median | P95 | Model RTF |
|---|---:|---:|---:|---:|
| ReDim 0.5 s | 2 | 12.01 ms | 13.37 ms | 0.0240 |
| ReDim 2.0 s | 2 | 40.43 ms | 42.87 ms | 0.0202 |
| Segmentation 10 s | 2 | 35.00 ms | 35.80 ms | 0.0035 |

Unpaced common-path WAV smoke:

- audio: 8.8975625 seconds, mono 16 kHz;
- post-source processing wall time: 0.810805 seconds;
- complete-pipeline compute RTF: **0.0911**;
- 21 partial transcripts, 1 correct final transcript, 11 segmentation events, 27 speaker decisions;
- both source cursors: 8.8975625 seconds;
- dropped frames/faults: **0 / 0**.

Real-time WAV smoke:

- source duration: 8.8975625 seconds;
- stream wall time: 9.020912 seconds (paced RTF 1.014);
- final transcript: `BUT ALL MY DREAMS VIOLATED THIS LAW` repeated three times;
- zero dropped frames and zero final lag.

Bounded live microphone smoke on Logitech device 31:

- accepted source duration: 12.1 seconds;
- stream wall time: 12.20945 seconds;
- startup/model validation: 2.357892 seconds, completed before capture;
- maximum observed ASR lag: 0.08 seconds;
- maximum observed speaker lag: 0.09 seconds;
- PortAudio overflows: 0;
- raw-reserve failures: 0;
- dropped frames: 0;
- both consumer cursors: 12.1 seconds;
- final speaker-analysis tail below the 0.25-second hop: 0.1 seconds, explicitly reported rather than treated as dropped audio.

Focused validation covers byte-exact fast/slow journal consumers, score-margin-evidence identity gating, backend/checkpoint profile invalidation, the inactive timestamped spatial contract, raw-preserving punctuation handling, and explicit overlap-uncertain transcript events. The exported bundle independently validates all eight hashes through its own asset-root configuration.

Unlimited-enrollment capture smoke on Logitech device 31:

- preferred 16 kHz input opened successfully;
- requested 3.2-second bounded smoke produced 3.24 seconds / 51,840 frames;
- output was streamed to a 103,724-byte PCM16 WAV;
- PortAudio overflows: 0;
- raw-reserve failures: 0;
- writer errors: 0;
- GUI loading/timer state-transition smoke passed.

Enrolled-name transcript audit on the user's recent 65.94-second local session:

- 16 transcript events used confirmed `AMIR Test`;
- 2 used tentative `AMIR Test`;
- 13 used anonymous labels;
- confirmed identity scores ranged from 0.5786 to 0.7256;
- the alternating anonymous labels are measurable cluster fragmentation, not a missing name-display connection.

The punctuation integration preserves the uppercase raw hypothesis and writes learned final `display_text`, model identity, checksum, status, and compute time to the exported event record. Final measured smoke evidence is recorded below after the focused validation run.

Focused punctuation and common-path smoke after integration:

- 6 unit tests passed;
- exact official-style input restored as `How are you? I am fine. Thank you.`;
- punctuation compute time was 6.23–9.16 ms across the three focused text probes;
- the 22.26-second common-path WAV run completed in 4.67 seconds accelerated wall time;
- 2 final utterances were punctuated in 22.46 ms total, 11.50 ms maximum;
- learned output included `Holy moly, What's up? My name is Emir, and this is how I talk.`;
- raw uppercase `text` remained unchanged in the same event;
- both inference cursors reached 22.26 seconds and dropped zero frames;
- the refreshed Pi bundle revalidated all eight assets and successfully loaded and ran punctuation from its own exported paths on Windows.

This is intentionally bounded integration evidence, not punctuation-accuracy validation or ARM64 hardware qualification.

## Raspberry Pi status

The refreshed local deployment directory contains about 220.2 MB of logical files, including the punctuation graph, vocabulary, licenses, source, and all prior runtime assets. On C:, model files were staged as hard links, so they do not allocate a second copy of model data. The lean runtime environment excludes Torch and Pyannote training/export packages.

Classification remains `PORT_REQUIRES_WORK`, because a Windows export is not an ARM64 qualification. Before calling it Pi-ready, measure on the exact Raspberry Pi/CM5:

1. Raspberry Pi OS 64-bit wheel installation and model loading;
2. ONNX numerical parity using fixed audio and embeddings;
3. ALSA/PipeWire capture and source-clock continuity;
4. real-time ASR + segmentation + identity under sustained load;
5. RAM, CPU, thermals, throttling, and storage rate;
6. device disconnect, worker failure, restart, and clean shutdown;
7. display/GUI or headless service behavior.

The roughly 220 MB logical bundle fits 2 GB storage/RAM budgets in principle, but model working memory and sustained scheduling must be measured before choosing a 2 GB over 4 GB module. The runtime and bundle do not assert hardware readiness.

## Evidence paths

- Unpaced compute smoke: `edge_speech_sessions/edge_wav_20260901T180823Z_4d0355a1`
- Real-time WAV smoke: `edge_speech_sessions/edge_wav_20260901T180615Z_86840945`
- Live microphone smoke: `edge_speech_sessions/edge_microphone_20260901T180716Z_fe0ff0f5`
- Raspberry Pi bundle: `JustPeachyResearchSummaries/edge_speech_pi_bundle_v1`
