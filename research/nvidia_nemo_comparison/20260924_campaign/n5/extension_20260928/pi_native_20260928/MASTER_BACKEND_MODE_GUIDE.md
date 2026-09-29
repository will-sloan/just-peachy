# Master backend and mode guide — Raspberry Pi

Updated September 29, 2026, 09:59 EDT / 13:59 UTC. This is the current conceptual and engineering overview. Older reports preserve history; use this guide and STATUS.md for current priorities. Latest converter evidence is linked below; qualified preview scope is unchanged.

## Where we are now

No campaign numerical worker or preview is running. Fresh inspection found all 87 recorded research process identities closed, no active research systemd units, and no user preview runs. The original rc5 app is still running with its original process identities and install. The Pi is a Compute Module 5 with 2 GB RAM.

Two new **bounded saved-file previews** have native evidence:

- **B01:** Sherpa transcription + Nemotron diarization + ReDimNet voice embeddings + punctuation.
- **B05:** the same transcription/diarization path with the external embedding model explicitly bypassed. Anonymous speaker numbers only.

Live-input preparation advanced: a fresh B01 derivative now passes constructed48k conversion into the full pipeline, Stop/restart, withdrawn Tk and independent exact D1/E0 references within768MiB. It uses the lower-memory NumPy FIR. This is saved-input integration, not actual device capture/timing or a newly exposed preview. See [integration findings](B01_FIR_FINDINGS_V1.md).

Both currently use delayed speaker processing. They are experimental previews for one checked 44.695-second, 16 kHz file, not general live-microphone releases. A successful preview is not completion of the campaign. Physical screen/touch, sustained operation and real-world speech quality remain unvalidated.

The objective is a small set of clearly labelled, ready-to-run Pi modes using the same interface, with predictable caption/label delay, bounded memory/backlog, working Stop/save/reopen/rollback, and measured real-world behavior. We are not trying to run every mathematical combination or make every candidate a winner.

## User-prioritized ASR activity guidance

ASR-assisted diarizer scheduling is a priority experiment. The first candidate protects detected speech plus roughly1second before/after, while energy/VAD fallback and uncertain cues retain audio. Start with native shadow logging; no silence is skipped yet. Measure late ASR cues, buffer/context costs and actual model work before claiming speedup. See [native ASR-guided plan](ASR_GUIDED_D1_NATIVE_PLAN_V1.md). The catalogue already contains G07/G08/G09; these are not yet native qualified implementations.

## The pipeline in plain language

```text
XVF / saved audio → source clock and sample-rate conversion
                         ├─ ASR → punctuation → captions immediately
                         └─ one ordered diarizer → speaker activity/slots
                                             └─ optional ReDimNet → identity evidence
Caption source intervals + available speaker evidence → delayed label updates
                                                   → UI and saved archive
```

- **ASR:** what was said. Captions should not wait for the diarizer.
- **Diarization:** who spoke when, initially as session speaker numbers. It does not separate overlapping voices into clean audio tracks.
- **Embedding/identity:** ReDimNet produces a voice vector that can support matching compatible known profiles. Keeping this model loaded does not prove recognition. Our new tests use an empty research gallery and perform no enrollment.
- **Punctuation:** formats transcription without replacing the preserved raw text.
- **Backend versus mode:** a backend chooses models/runtime. A mode chooses behavior such as anonymous labels, retained identity, delayed labels or later transcript refinement. Runtime, chunk geometry and scheduling are separate choices.

A displayed “Speaker 1” is a session channel, not a persistent personal name. Unknown personal identity and a known anonymous speaker channel can coexist. Current word intervals are ASR revision windows, not precise phonetic word alignment.

## Component glossary

| Code | Component | Current role |
|---|---|---|
| A0 | Existing Sherpa Giga ASR through sherpa-onnx | Primary Pi caption engine and working control |
| A1 | Parakeet realtime EOU 120M | Offline comparison candidate; not a new qualified Pi application |
| A2 | Nemotron English ASR 600M | Next principal ASR alternative; native full application not qualified |
| A3 | Nemotron 3.5 ASR alternative | Lower-priority research comparator; short emulated checks do not establish native full-stack readiness |
| D0 | Existing Pyannote diarization path | Historical baseline speaker pipeline; preserve the installed app as control |
| D1 | Nemotron 3 diarization | Current native delayed speaker lane |
| E0 | ReDimNet | Retained voice-identity encoder; 192-dimensional normalized vectors in this artifact |
| E1 | TitaNet | Retired from further work; historical evidence preserved |

The original app's continued operation is not a new full B00 live/GUI qualification. Detailed historical offline results remain in the N2/N3 reports; saved-file native tests are not new WER or speaker-accuracy scores.

## All planned compositions, without implying they all work

| ID | Composition / behavior | Actual Pi status and intended use |
|---|---|---|
| B00 | Original complete Sherpa pipeline | Installed rollback/control. Preserve it. Separate Sherpa saved-file component passage passed. |
| B01 | A0 + D1 + E0 | Bounded saved-file preview qualified. Captions first, delayed labels, empty research gallery. Main route toward live validation. |
| B02 | A2 + D1 + E0 | Planned priority after resource-qualified native A2. No integrated Pi pass. |
| B03 | B01 with on-demand E0 | Candidate. Must measure actual calls saved and retain quiet/returning-speaker/overlap behavior. Existing E0 window selection is not acceptance of a new on-demand policy. |
| B04 | B02 with on-demand E0 | Candidate; depends on B02 and on-demand evidence. |
| B05 | A0 + D1, external encoder bypass | Separately qualified bounded anonymous saved-file preview. No persistent personal naming. |
| B06 | A2 + D1, external encoder bypass | Candidate; depends on native A2. |
| B07 | B01 with deliberately delayed D1 | The currently tested B01 preview already uses this delayed strategy. It is an overlapping catalogue variant, not a third independently delivered mode. |
| B08 | B02 with delayed D1 | Candidate; no native combined pass. |
| B09 | Sherpa first, Nemotron ASR refinement later | Candidate for sequential loading on 2 GB RAM. Must preserve source time, transcript revisions and completion/drain. |
| B10 | Cheaper tracking between selective D1 refinements | Exploratory; no qualified native implementation. Must expose uncertain/unanalyzed spans. |
| B11 | A2 with the existing speaker pipeline | ASR substitution control; not a qualified native application. |

Other A1/A3/D0 combinations remain comparators, not priority releases. The 34-method catalogue also covers pacing, jitter, worker strategies and gates; it is not 34 completed implementations. Do not launch a Cartesian sweep.

## What has actually passed

| Evidence | What it establishes | What it does not establish |
|---|---|---|
| Native Sherpa original-paced saved file | Audio reaches ASR, text/endpoints/EOF appear, sample coverage and shutdown work; decode workload RTF about 0.133 in that component run | New WER, microphone route or full-system real-time capacity |
| D1 full file/repeat/reset/EOF; generic versus repaired Cortex-A76 kernel | Same-geometry probability arrays match exactly at the unchanged 1e-5 gate; native state/mapping and tested resource bounds work | Speaker accuracy, all recipes or long conversation stability |
| ReDimNet application-window reference | All 26 short/full reference windows recomputed twice match application vectors exactly | Recognition of people, enrollment or noisy-speaker accuracy |
| B01 and B05 native saved-file passage and Stop/restart | Source offsets/session identity reset, all full-file samples retained, models/queues/archive handles close naturally | Unbounded runs or live input |
| Real withdrawn Tk widgets | Caption rendering and relevant controls work with native models without taking the visible desktop | Actual screen fit, touch, scanout or user interaction on the physical device |
| Copied-archive Save/Open/Delete/cancel | Stored text, labels, spans and histories survive; only fresh copied data is deleted | Every product mode or data migration |
| Guarded previews | Idle startup, selected-file restrictions, actual Start/Stop/restart/Close, no unintended capture/playback, serialized dispatch | A later user's run outcome or general release acceptance |

N1–N3 retain scoped offline acceptance; N2 has 422/422 evaluations. N4's original actual 240-cell application panel remains partial: two collected pending acceptance, two failed, 236 unattempted. Modeled comparisons are not application acceptance. N5 is incomplete and there are zero accepted new final release profiles.

## What is slow, and what the numbers mean

The main tradeoff is **speaker latency versus diarizer compute**:

| Tested D1 recipe | Native observation on the saved file | Practical meaning |
|---|---|---|
| Streaming, 13 coarse frames | About 3.63 seconds of work per second of input | Too slow to sustain this input rate in the tested configuration |
| Experimental 52-frame chunk | Average work RTF 1.085; later warm blocks about 1.56 | Initial averages hide growing backlog; paced first output about 5.09 s, EOF drain about 16.66 s |
| Delayed, 264-frame chunk | About 18.1 s model work for 44.7 s input, RTF 0.405 | Compute fits on this short sample by accepting large label delay; paced component first probabilities about 25.5 s |

Current B01 preview: first text about 5.64 s **from file start**, including initial silence; first D1 probabilities about 25.5 s; previous same-source label-lineage check first label about 26.9 s. This is not per-word latency. Full-preview EOF drain was about 12.56 s. Peak process RSS was about 544 MiB; sampled virtual peak about 720 MiB under the 768 MiB virtual-address cap. Concurrent component times cannot be added as total elapsed time.

The existing rc5 app remains active, so these are conditional measurements. A 44.7-second pass is not a 30/60-minute stability test. Sparse synthetic scenes are not representative dense conversation, and no silence-removal speedup has been qualified.

Much of the elapsed campaign time has been engineering and verification: native numerical discrepancies, allocation failures, graph-cache growth, thread-stack reservations, unnecessary imports, Stop/drain behavior and source-bound evidence review. Successful current application trials take roughly a minute; slower D1 variants took minutes per short file. No training or large new download is running. Hourly continuation is periodic work, not continuous computation between wakeups.

## Native runtime, ONNX and lower-level implementation

The working D1 route is a **Python application calling a native C++ CPU runtime**, using the already-staged mixed-Q8 model. “Native build” here means those compiled ARM64 components; no separate PyNative product/runtime has been qualified. ONNX Runtime is the likely intended “Onyx runtime.”

- Pi environment: aarch64 Bookworm, Python 3.11.2, glibc 2.36, ONNX Runtime 1.29.0 and sherpa-onnx 1.13.4, as inventoried.
- Sherpa, ReDimNet and punctuation already use the existing portable runtime stack. D1 has no staged/qualified ONNX graph plus streaming driver. Exporting a file alone would not preserve the frontend, recurrent state, cache, EOF semantics or prove faster ARM execution.
- The successful Cortex-A76 change retains integer lane grouping before float accumulation while using dot-product instructions. Earlier faster mismatching kernels remain failed attempts; their tolerance was not loosened.
- D1-only bounds: scheduler capacity 2048 with the original 95% guard, 2 MiB metadata reservations with assertions, executable graph LRU capacity 1. The speaker/FIFO history was not shortened. These bounds are qualified only for the tested delayed recipe, not A2 or arbitrary longer workloads.
- Delayed C-ABI recipe: chunk/right/left/FIFO/cache/refresh = **264/1/1/0/264/188**, on an 80 ms coarse grid. Selecting the v3-offline preset is necessary to retain FIFO 0 because that API ignores a zero-valued override.
- Current app source: `shared-app-b01-defer-scipy-v1/prototype`. Only two otherwise-unused SciPy resampling imports were moved into rate-conversion branches. Already-16-kHz input avoids that startup cost; the resampling algorithm was not changed. A real 48-kHz route may import it again and needs its own memory check.
- Process-local native/Python stacks are 1 MiB, allocator settings are bounded, models use one native thread, GPU is off. Original app and OS settings are unchanged.

Credible next optimization work is targeted: actual live-route conversion cost, native A2 resource fit, one useful shorter-latency recipe if measurements justify it, on-demand E0, then a proven alternative runtime when its graph/assets/operator coverage are available. More workers share the same CPU budget and can add copying/context/memory costs. Keep one ordered stateful D1 stream. Do not apply silence skips until source mapping, quiet/overlap speech, cache, returning speakers and flush are validated.

## What we are waiting on

| Item | Waiting on | Does it block current offline work? |
|---|---|---|
| Spoken/XVF and restaurant validation | You physically ready for a short agreed session and suitable consented speech | No; software preparation can continue |
| Physical screen/touch review | User-visible preview and hands-on interaction | No |
| Live 48-kHz route | Engineering checks of actual route/format/resampling and combined memory | This is the next software gate before claiming live readiness |
| Native A2 / B02 | Component load/state/resource checks, then integration | Blocks the all-Nemotron ASR alternative, not B01 |
| 30/60-minute tests | Fresh bounded time/resource/output admission and an appropriate long input | Short runs cannot substitute |
| Previous 1-GiB virtual-cap question | Still unanswered | **No longer blocks the working B01 saved-file route.** No increase has been used. |
| Alternative D1 ONNX assets | Concrete compatible export/driver and any required acquisition authorization | Not a reason to stop the existing native route |

At the latest closure, combined new outputs used about 801 MB of the 1 GiB allowance, leaving about 260 MiB. Future long tests need bounded logging and a fresh census; do not delete evidence or increase limits silently. Device physical RAM is 2 GB, while the research job's virtual cap is 768 MiB: these are different quantities. The kernel has no memory cgroup controller, and global swap counters do not establish per-job swap-free behavior.

## Shortest path to real-world validation

1. **Finish the input route:** saved-input diagnostic of the actual sample-rate conversion/dependency path; verify sample counts, timestamps, model passage and memory. Do not assume the inventoried I2S XMOS endpoint is an established USB/live XVF route.
2. **User-ready quiet-room session:** verify routing, then a short consented spoken passage with B01/B05; inspect real captions, speaker changes, Stop/drain and listening outputs. Silence-only capture checks routing, not speech quality.
3. **Native sustained run:** bounded original-paced 30 minutes, then 60 for a finalist. Track dense-speech backlog, caption/label delay, CPU/RAM, thermals/clocks/throttle, failures and drain. Repeated/constructed input remains a diagnostic, not independent accuracy evidence.
4. **Real noisy comparisons:** freeze settings first; compare microphone reference, XVF Auto ASR and postprocessed outputs where actual firmware/routing supports them. Preserve simultaneous chronology and paired listening gains. Separate restaurant babble, steady fan/HVAC noise, impacts, quiet/brief speech, overlap and returning speakers. Use known consenting speakers; do not deliberately record unrelated conversations.
5. **Release:** choose useful modes from measurements, qualify install/update/rollback and physical UI, keep failure behavior explicit, complete remaining acceptance gates, and back up reviewed code/manifests.

Native A2/B02 and sequential refinement can progress between these gates when admitted resources are free. They should not delay first real-world validation of the already functioning B01/B05 route.

## Starting a checked preview

These are user-invoked visible Pi previews. **This guide does not start one.** Keep the original app installed; the fresh launch guard rejects another active research worker. Each preview admits only the checked sample, starts idle, allows at most two starts, and closes within its bounded window. No microphone or playback.

PowerShell:
```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
# Retain ReDimNet:
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/launch_b01_preview_v1.py --mode user
# Anonymous alternative, in a separate run after the first closes:
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/launch_b05_preview_v3.py --mode user
```

CMD / Anaconda Prompt: use `cd /d G:\Just_Peachy_N1\20260924_campaign\worktree`, then the same chosen interpreter/script command without the leading `&`. No installation is required. Window flow: **File → Choose saved sample → Start file**. Selection alone does not run inference. Stop drains; Start restarts from zero. Inputs/outputs, exact resource checks and restrictions are in the per-preview READMEs.

## Keeping research and token use efficient

- Inspect compact current status/active owners first. Read detailed evidence only for a changed result or concrete blocker.
- Keep hourly checks, but do not invent work or repeat passed tests for an update. Notify only meaningful changes.
- Prioritize native live readiness, a small mode shortlist and decisive tests. No further Windows sweeps unless they resolve a specific Pi blocker.
- Reuse verified models/builds and existing reference arrays. Keep historical failure evidence, but avoid reprinting it in every prompt/report.
- Freeze configuration before real-world tests. Avoid full combination sweeps, speculative extra agents, repeated documentation and duplicate archives.
- Record exact measured compute/resources; do not invent token-cost totals or promise a finish date for unmeasured gates. The authorized review checkpoint remains October 1, 2026 at 17:47:34 UTC (13:47 EDT).

## Evidence and practical links

- [Current native status](STATUS.md), [latest small check summary](CHECK_SUMMARY_V13.json), [B01 findings](B01_PREVIEW_FINDINGS_V1.md).
- [B01 launch instructions](README_B01_PREVIEW_V1.md), [B05 launch instructions](README_B05_PREVIEW_V3.md).
- [Actual method coverage](NATIVE_METHOD_COVERAGE_V1.md), [composition research plan](../RESEARCH_PLAN.md), [held-out real-world requirements](../../realtime_validation_v1/REAL_WORLD_HOLDOUT_V1.md).
- Private listening examples: `G:\Just_Peachy_N1\20260924_campaign\local\n5\listening-examples-v1\index.html`. Synthetic scenes through real hardware are not recordings of real conversations; the real cafeteria excerpt is only 0.75 seconds. These examples do not establish restaurant performance.
- Exact source/model hashes and immutable admissions live in the versioned qualification/review receipts. Audio, transcripts, vectors, personal profiles and weights stay private; reviewed small code/docs go to the campaign Git branch.
