> October4 runtime addendum: current2GB measurements and the4GB/8GB capacity
> interpretation are maintained in [RAM_RESOURCE_GUIDE](../extension_20260928/pi_native_20260928/live_runtime_20261003/RAM_RESOURCE_GUIDE.md).
> This earlier pricing/licensing comparison is dated historical research, not
> a current purchase quote or a larger-RAM benchmark. Completed combined
> five-minute runs fit2GB. Chunk52's component hour points to CPU/thermal limits.
> No drastic speedup from additional RAM has been measured.
# CM5 memory, model choices and product cost

**Decision — 1 October 2026:** keep **Sherpa ONNX ASR**, Nemotron-3 diarization and the compatible ReDimNet speaker encoder as the delivery candidate. The user explicitly chose Sherpa after reviewing Nemotron ASR's measured cost. No new model or hardware was tested for this report.

**Buy 4 GB for economical headroom, or 8 GB for development flexibility. I would not spend roughly C$375 extra on 16 GB expecting faster diarization or markedly better noise accuracy.** Every CM5 memory option has the same quad-core Cortex-A76 CPU at 2.4 GHz; more RAM adds capacity, not processing cores. [Official specifications](https://www.raspberrypi.com/products/compute-module-5/)

## Canadian pricing and sourcing

These comparable Newark SKUs have **16 GB eMMC and no wireless**. The supplied CM5004016 is **4 GB RAM**, not 16 GB RAM. Our current device has 32 GB physical storage; check the installed storage/radio variant before buying. Prices exclude tax and shipping.

| RAM | Module / Newark listing | CAD, one unit | Added cost vs 2 GB | Listing availability |
|---|---|---:|---:|---|
| 2 GB | [CM5002016 / 20AM3745](https://canada.newark.com/raspberry-pi/cm5002016/system-on-mod-rpi-compute-mod/dp/20AM3745) | 131.35 | — | Orderable; deliveries from Nov 20 |
| 4 GB | [CM5004016 / 20AM3753](https://canada.newark.com/raspberry-pi/cm5004016/system-on-mod-rpi-compute-mod/dp/20AM3753) | 177.50 | 46.15 | 106 listed in stock |
| 8 GB | [CM5008016 / 20AM3761](https://canada.newark.com/raspberry-pi/cm5008016/system-on-mod-rpi-compute-mod/dp/20AM3761) | 269.80 | 138.45 | Orderable; deliveries from Oct 9 |
| 16 GB | [CM5016016 / 20AM3769](https://canada.newark.com/raspberry-pi/cm5016016/system-on-mod-rpi-compute-mod/dp/20AM3769) | **504.00 provisional** | **372.65 provisional** | Conflicting indexed snapshots |

The 16 GB listing returned C$504 / 244 in stock in a newer index, but C$437.85 / 249 in an older response. Direct browser verification returned 403. C$504 is a provisional budget, close to the stated C$375 premium; these are not checkout quotes or guaranteed current stock. At C$437.85, its premium would be C$306.50. No purchase was made.

| RAM | What it realistically enables |
|---|---|
| **2 GB, current** | The existing small ASR + D1 + ReDimNet composition has scoped native passes, with tight memory/process management. Persistent offline release remains unfinished. |
| **4 GB** | More OS, cache and combined-model headroom for the selected stack; small embedding/front-end alternatives. Best cost-controlled upgrade. |
| **8 GB** | More room for resident alternatives, larger saved-audio analysis and development frameworks. Preferred development board; real-time CPU limits remain. |
| **16 GB** | Large full-precision frameworks and several resident research models. Little expected benefit over 8 GB when the selected workload already fits. |

These are evaluation tiers, not measured minimum requirements. RAM can help if swapping or repeated unloading is the bottleneck. Existing 768 MiB process limits would still apply until a new measured admission changes them. RAM does not increase recording storage.

## Will it become real time or better in noise?

The recorded **~1.75 RTF / ~966 MiB RSS was Nemotron streaming ASR**, not the diarizer. RTF means processing time divided by audio duration. We will retain Sherpa ONNX ASR; a Nemotron ASR replacement is outside the delivery priority.

Retained D1 component results on one 44.695-second saved file:

| D1 mode | Processing time | RTF | Practical limit |
|---|---:|---:|---|
| Delayed | 18.118 s | 0.405 | Faster than incoming audio in this trial, but about 21.3 s of source buffering |
| Chunk52 | 48.501 s | 1.085 | Near real-time computation; sustained whole-app qualification remains open |
| Streaming | 162.412 s | 3.634 | Substantial computational backlog |

These modes use different geometries; the baseline app ran concurrently. The currently selected delayed LRU1 library also differs from the earlier paired kernel measurement. Later live/archive passes establish scoped function, not low-latency sustained streaming. More RAM cannot remove required lookahead. [Local timing evidence](../extension_20260928/pi_native_20260928/CHECK_SUMMARY_V94.json), [backend guide](../extension_20260928/pi_native_20260928/MASTER_BACKEND_MODE_GUIDE.md).

A workload at 1.8 RTF needs at least 1.8× throughput, or about 44% less processing time, to reach 1.0 before whole-app overhead. A RAM upgrade alone cannot promise that.

**With identical audio, models and settings, RAM should not improve noise accuracy.** Better microphones/placement, suitable training data, overlap handling and a validated audio front end matter. Larger models may improve quality but can be slower. Enhancement can also damage speaker cues. Future paired raw/processed tests must measure WER, DER and speaker false accepts/rejects; no new noisy-human accuracy evidence exists.

## Models worth considering under open licences

Keep the current stack first. Alternatives below are research options, not approved replacements or demonstrated CM5 real-time improvements.

| Model / purpose | Sensible evaluation tier | Published model licence |
|---|---|---|
| [Nemotron-3-Diarization](https://huggingface.co/nvidia/Nemotron-3-Diarization) | Already runs on 2 GB; retain it across tiers and optimize compute/latency | OpenMDW 1.1 |
| [SpeechBrain ECAPA-TDNN VoxCeleb](https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb) — speaker embeddings | 2–4 GB; compare against ReDimNet. No evidence it is better in our noise | Apache 2.0 |
| [pyannote community-1](https://huggingface.co/pyannote/speaker-diarization-community-1) — diarization | 4–8 GB saved-audio comparison; offline after acquisition, not a proven live CM5 replacement | CC BY 4.0; initial access/contact gate |
| [Whisper small / medium / large-v3-turbo](https://github.com/openai/whisper) — optional saved-audio ASR | 4 GB for small; 8–16 GB for larger experiments with suitable quantization/runtime. Sherpa remains live ASR | MIT code and weights |
| [Parakeet TDT 0.6B-v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3) — optional saved-audio ASR | 4–8 GB; not a drop-in streaming replacement | CC BY 4.0 |
| [Nemotron 3.5 streaming 0.6B](https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b) — optional multilingual ASR research | 4–8 GB candidate with suitable runtime; deferred by the Sherpa decision | OpenMDW 1.1 |

[DeepFilterNet](https://github.com/Rikorose/DeepFilterNet) is a possible noise-reduction experiment, not a reason to buy 16 GB. Its code is MIT/Apache licensed; check the exact weights separately before redistribution. A new speaker encoder needs versioned profiles: its vectors cannot simply replace ReDimNet vectors.

OpenMDW, CC BY, MIT and Apache have different notice/attribution conditions. [OpenMDW 1.1](https://openmdw.ai/license/1-1/) grants use free of charge with conditions. Existing English Nemotron ASR and [Parakeet Realtime EOU 120M](https://huggingface.co/nvidia/parakeet_realtime_eou_120m-v1) use the [custom NVIDIA Open Model License](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-open-model-license/), not plain Apache/MIT; they are deferred, not silently approved. Audit each exact checkpoint and runtime together using the [licence ledger](../LICENSE_LEDGER.md). No downloads, training or enrollment were performed.

## What would product pricing need to be?

There is no required per-minute API bill for local inference. An absolute selling price needs the full landed BOM, assembly, cooling, support, warranty/returns and channel costs.

For a RAM-only change, **retail premium = added landed cost ÷ (1 − gross margin)**:

| Upgrade | Module cost added | Retail premium at 35% margin | At 50% margin |
|---|---:|---:|---:|
| 4 GB | C$46.15 | C$71.00 | C$92.30 |
| 8 GB | C$138.45 | C$213.00 | C$276.90 |
| 16 GB, provisional | C$372.65 | C$573.31 | C$745.30 |

At the stated C$375 difference, that is about **C$577 or C$750 extra** at those margins, before other added costs. These are pricing scenarios, not recommended margins. Replacing an owned board requires paying the full new-module price unless the old board is reused or resold.

Keep the present delivery on 2 GB. Test a 4/8 GB board only with identical frozen inputs, models, cooling and CPU policy; measure sustained whole-app RTF, label delay, RAM/swap and thermals. Buy 16 GB only for a demonstrated workload that needs more than 8 GB. The new [desktop shortcuts and optional raw/processed PC export requirements](OPERATOR_SHORTCUTS_AUDIO_REQUIREMENTS_V1.md) remain required and open; they do not depend on a RAM purchase.
