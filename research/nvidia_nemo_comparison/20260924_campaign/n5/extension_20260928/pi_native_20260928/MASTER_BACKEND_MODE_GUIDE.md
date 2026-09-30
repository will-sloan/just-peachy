# Master backend and mode guide — Raspberry Pi

**Current update September30 02:05UTC:** The isolated source now has checked Start/request-Stop/drain/finalize controls. Five native fake-device cases exercise the actual startup method; queued accepted audio drains before finalization and faults remain explicit. Actual PortAudio/production-controller integration is next. See [startup findings](SOURCE_STARTUP_FINDINGS_V1.md). All research compute is closed; the alternate D1 projection mismatch and field release remain unresolved.

**Device storage:** fixed32GB Raspberry Pi; last measured available space is17.874GB(16.65GiB), including existing research usage. Host allowances do not enlarge it. All field models, app, recordings and rollback must fit with5GiB available reserve. See [storage budget](PI_STORAGE_BUDGET_V1.md).

Earlier scoped update September30 00:43UTC: separate-process source IPC now passes13 native fixture cases, including bounded buffering during a parent stall, exact audio bytes and explicit fault/Stop/closure handling. It is not yet a microphone adapter or live fix. Original app unchanged; no research compute remains active. See [isolation findings](ISOLATED_SOURCE_FINDINGS_V1.md) and CHECK_SUMMARY_V42.json. Generic A2 remains the qualified ASR component; its faster A76 candidate is unqualified. Alternate D1 state parity, full live/standalone field release and N4/N5 acceptance remain open.

Current overview updated September 30, 2026, 01:33 UTC. Dated entries below retain earlier evidence; the newest STATUS.md and CHECK_SUMMARY govern current work. Qualified saved-preview scope is unchanged.

## Next 36–48 hours

Unattended bounded quiet recording and necessary Pi/resource changes are now authorized, with ongoing backups and no further questions. The user will not provide playback; quiet checks establish stream/recording/resource behavior only. [Current authorization and workflow](AUTONOMOUS_QUIET_WORK_V1.md).

The user has prioritized implemented Nemotron diarizer modes, credible speed methods, native Nemotron ASR and alternate runtimes, all aligned with N5 GUI/field readiness. The existing October 1 checkpoint stays. See the [delivery plan and N5 mapping](N5_NATIVE_DELIVERY_48H_V1.md). Resource authority now permits measured adjustments; new WINDOW_V5 allows 5 GiB combined existing-plus-new file output and52GiB totalpayload with retained2.5GiB reservations, retaining old evidence and separate per-job limits.

## Where we are now

**September29 23:54UTC:** CHECK_SUMMARY_V40 / B01_QUIET_ARTIFACT_FINDINGS_V1: actual autonomous quiet B01 failed at25.56s with exact PortAudio input_overflow flag2.480frames is rejected callback size; upstream loss unknown. All408960accepted samples reached ASR/D1;2557finite D1frames including445failure-drain frames,zero model errors,zero text/E0window calls. Private microphone float/PCM408960samples independently exact/reopenable,compact archive2.35MB,zero clips; all queues/controller/Tk naturalexit1,route readbacks restored,captureclosed/leasesfree. FirstD1output25.532s; fault0.118s after publication is correlation,not proven cause. PeakRSS483.969MiB/VmPeak653.469MiB; no allocation/output guard. Source/app unchanged; private12.38MB backup verified. ClosureV70all157Pi/44hostclosed,combined4298110702/5GiB,targetfree17912446976bytes. Next no-capture serialization/GIL/throttle diagnosis before any changed quiet retry; advance A2optimized/sequential and alternateD1 in parallel priorities. Not full live/quality/endurance/release.

**September29 23:37UTC:** CHECK_SUMMARY_V39 / B01_ARTIFACT_COMBINED_FINDINGS_V1: actual B01 Stop/fullrestart with compact logs+float/PCM retained131520early and715127fullsamples;4470x8D1 maxabs0 at1e-5,20fullE0calls,newwindowreferencespending,learnedPnC/zeroinferenceerrors. Firsttext5.645s inclsilence,D1output25.602s,EOFdrain12.934s,RSS551.844MiB/VmPeak730.188MiB. Harness failed after inference by comparing4rawutterances with40segments; naturalexit1/cleanallqueues retained. Supplemental model/PCM review preserves failure. Separate fresh copied-archive controller Save/Open+withdrawnTk passes all40rows/text/labels/spanhistory,zeromodels,naturalexit0. Faultdetail wrapper bound,actualcallbacknotrepaired. Both private backups verified. All155Pi/44hostclosed,baselineunchanged,captureclosed,leasesfree;closureV67combined4271854546/5GiB. Next fresh autonomousquiet B01 with recording/restoration; no rerun of saved model pass. D1state/A2optimization remain open.

**September29 23:16UTC:** CHECK_SUMMARY_V38 / APP_ARTIFACT_FINDINGS_V1: fresh app derivative passes native actual engine event-writer factory, archive writer and compatible SessionStore reopening. All2628/2672events exact; three final rows preserve all fields and match legacy reader; actual saved715127samples produce exact float master/reopenable byte-exactPCM. Partial archive and asynchronous quota failure explicit; queues/handles/naturalexit0. Peak51.969MiBRSS,10.565s,actual768MiB envelope. No models/capture/full controller/GUI/live timing or callback repair. Private17.56MB target backup verified. All151Pi/44host identities closed,baseline unchanged,captureclosed/leasesfree; closureV64combined4,183,937,133/5GiB. Next combined-model saved-input Stop/restart with compact-aware review and callback detail binding, then fresh autonomousquiet; D1state diagnosis/A2optimized-sequential remain open.

**September29 22:50UTC:** CHECK_SUMMARY_V37 / LIVE_ARTIFACT_FINDINGS_V1: native bounded journal/PCM helpers pass independent model-free replay. Both original failed-live journals reconstruct all2628/2672events exactly;34,094,111bytes become7,276,651bytes (~78.7%smaller),not a live speedup. Original715127saved samples reopen as byte-exactPCM; no new mic recording. Byte/record/frame limits reject before rejected writes; five invalidPCM calls and normal/overflow callback-to-journal cases pass under actual768MiB/1MiBstack/CPU2/3/200%/300s/10s envelope. Peak39.656MiBRSS,naturalexit0. Source/archives unchanged,newhelpers UNINTEGRATED,oldcallbackfault NOTfixed. Exact private output backup verified. All149Pi/44host identities closed,baseline unchanged,captureclosed,leasesfree; closureV60combined4,146,445,841/5GiB. Next freshapp integration of bounded sinks plus compatible readers, then autonomousquiet trial; keep D1state mismatch and A2optimized/sequential work moving.

**September29 22:32UTC:** CHECK_SUMMARY_V36 / D1_WAVEFORM_FINDINGS_V1: complete waveform candidate implemented but host tail final-cache parity fails1e-5 (1.639e-4 embedding error, probabilities8.568e-8). A separate original-feature graph/state diagnostic reproduces the failure: full4469probabilities error9.000e-6 passes, cache2.346e-4 fails; repeats exact. Frontend alone is not the cause; precise operator still unknown. No native waveform/GUI/speedup acceptance. Original reference uses actual learned silence,valid4469frames distinct from Q8 4470. Preserve initial64MiB extraction guard stop/partialweights; fresh256MiB reference trial closed naturally1 and diagnostic0 is observations only. All147Pi/44host identities closed,baseline unchanged,captureclosed,leasesfree. WINDOW_V5 now5GiBcombined/52GiBtotal/2.5GiBreserved,oldlimits preserved,fixed32GBPi unchanged. ClosureV57 combined4,127,737,930bytes,targetfree17,995,952,128bytes. Next isolate preencoder graph output on retained features; keep bounded quietPCM/journal and A2optimized/sequential work advancing.

Ordered speaker-cache/FIFO handling now passes15 constructed native updates and exact repeats, including an overlap tie that stopped the first candidate. A small explicit ONNX compression helper preserves the observed NeMo selection. The frontend and state components are separately checked; the complete high-resolution audio/model stream remains open. [State findings and preserved failures](D1_STATE_FINDINGS_V1.md).

The portable audio frontend now passes nine native Pi cases, including full saved audio, irregular blocks, EOF and reset, at about57MiB peak RAM. This closes the audio-to-feature component; the complete model/state/source-time integration remains. [Frontend findings](D1_FRONTEND_FINDINGS_V1.md).

Current future-admission policy is WINDOW_V5:52GiB totalpayload with2.5GiBretained reservations and5GiBcombined output. ClosureV92 uses4,415,554,387bytes; refresh both budgets before dispatch. Old50GiB/4GiB policies, rejections and receipts remain immutable. Pi physical32GB capacity and5GiB free reserve remain separate.

The alternate D1 ONNX graph now passes three actual Pi FP32 feature/cache checks and exact repeats against PyTorch references. Peak RAM was about 509 MiB. This verifies the graph on ONNX Runtime CPU; V4 now separately preserves learned high-resolution outputs, while the complete audio/cache/FIFO/EOF driver remains open before it becomes a usable alternate mode. No speedup is established. [Native findings](D1_ORT_NATIVE_FINDINGS_V1.md).

Native A2 endpoint/tail checks now pass: empty input, one sample,1281-sample tail and full-source forced endpoint at12.34s, followed by continued transcription, EOF and clean shutdown. This extends component functionality; it does not make A2 real-time or an integrated GUI mode. [Endpoint findings](A2_NATIVE_EDGES_FINDINGS_V1.md).

Nemotron ASR (A2) passes full saved-source/repeat and scoped empty/tail/forced-endpoint checks on the Pi. Generic runtime takes about77-79seconds per44.7-second file and peaks near966MiB RSS. A sequential Sherpa-first/A2-later coordinator now passes independently; GUI/controller and combined B02 integration remain open. No real-time or accuracy claim. [Sequential findings](SEQUENTIAL_ASR_FINDINGS_V1.md). Follow-ups run every10minutes.

At closureV60 (22:50UTC), all149Pi and44isolated host research identities were closed; no research model or capture was active. The original rc5 app remained unchanged. The Pi is a Compute Module5 with2GB RAM and fixed32GB storage.

Two new **bounded saved-file previews** have native evidence:

- **B01:** Sherpa transcription + Nemotron diarization + ReDimNet voice embeddings + punctuation.
- **B05:** the same transcription/diarization path with the external embedding model explicitly bypassed. Anonymous speaker numbers only.

Live-input preparation advanced: a fresh B01 derivative now passes constructed48k conversion into the full pipeline, Stop/restart, withdrawn Tk and independent exact D1/E0 references within768MiB. It uses the lower-memory NumPy FIR. This is saved-input integration, not actual device capture/timing or a newly exposed preview. See [integration findings](B01_FIR_FINDINGS_V1.md).

Both currently use delayed speaker processing. They are experimental previews for one checked 44.695-second, 16 kHz file, not general live-microphone releases. A successful preview is not completion of the campaign. Physical screen/touch, sustained operation and real-world speech quality remain unvalidated.

The objective is a small set of clearly labelled, ready-to-run Pi modes using the same interface, with predictable caption/label delay, bounded memory/backlog, working Stop/save/reopen/rollback, and measured real-world behavior. We are not trying to run every mathematical combination or make every candidate a winner.

## Actual microphone path now passes the quiet check

After one expressly authorized XVF-only restart, the new 12-second real I2S check passed: 48kHz input converted to16kHz with exact counts, no dropped frames, successful tested-route restoration and clean closure. No audio was saved and no models ran. The earlier failed check/reset rejection remains preserved. The restart cleared volatile state; restoration covers the post-restart test settings. [Recovery evidence and limits](QUIET_ROUTE_RECOVERY_V1.md).

Two user-ready live attempts are preserved. The first hit the virtual cap; a process-local ALSA configuration reduced unnecessary import mappings and passed saved-input checks. The retry retained 26.25 seconds and produced captions, diarizer probabilities and embeddings, but aborted on a PortAudio input-status indication. **The reported 480 frames count the rejected callback block; the total upstream loss and exact status flags are unknown.** The trial remains failed, with incomplete D1 coverage. The microphone is closed, routes restored and original app unchanged. No full live pass or listenable WAV is qualified.

Eight native synthetic callback cases now qualify an unintegrated fault diagnostic helper, without opening a microphone or loading models. A supplemental admission-field mismatch still needs correction before reusing that dispatch; its eight functional results do not qualify the complete execution envelope. Read-only analysis found display histories make up 87.33% of the main session journal. Next bound diagnostic output and verify compact replay, then a bounded listenable PCM path and combined integration. This does not prove logging caused the interruption. The user has since authorized resource adjustments. After staging A2, about 1.37 GiB remains under the new 3 GiB file allowance. Logging still needs a real bound; extra storage does not fix the input interruption. [Current findings and limits](CALLBACK_AND_JOURNAL_FINDINGS_V1.md). Saved B01/B05 previews remain unchanged.

## User-prioritized ASR activity guidance

A separate candidate now bounds policy metadata as well as audio. Twelve native model-free checks passed, including a simulated hour of events in 5.661 seconds. It is not integrated into B01 and does not skip inference; this is no live endurance or speedup result. Overflow and uncertain late history retain audio. Next replay the retained actual cue chronology before integration. [Bounded metadata findings](ASR_BOUNDED_METADATA_FINDINGS_V2.md).

The next implementation step now passes on the Pi: an actual192k audio shadow queue plus successful-ASR progress. Missing/failed health, late cues, buffer pressure and EOF have constructed checks; B01 full outputs stay exact and drain cleanly. Observation costs about1.09s on the44.7s diagnostic. All audio still runs; there is no demonstrated inference speedup. [Causal buffer findings](ASR_CAUSAL_FINDINGS_V1.md).

ASR-assisted scheduling now has a native shadow check: actual ASR/energy cues were recorded online, then a causal±1second policy was replayed while all audio still ran. Fine-resolution proposals covered49.4%of this sparse clip, but current21.12second chunks left only a2.46second final partial candidate. No actual skip or speedup is qualified; EOF/context, cue-health and buffering gates remain. See [shadow findings](ASR_SHADOW_FINDINGS_V1.md) and the [investigation plan](ASR_GUIDED_D1_NATIVE_PLAN_V1.md).

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
| B02 | A2 + D1 + E0 | A2 component full/repeat/empty/tail/forced-endpoint passes on Pi; about1.75RTF and966MiB RSS. Independent-runtime parity and combined/UI fit remain open. |
| B03 | B01 with on-demand E0 | Candidate. Must measure actual calls saved and retain quiet/returning-speaker/overlap behavior. Existing E0 window selection is not acceptance of a new on-demand policy. |
| B04 | B02 with on-demand E0 | Candidate; depends on B02 and on-demand evidence. |
| B05 | A0 + D1, external encoder bypass | Separately qualified bounded anonymous saved-file preview. No persistent personal naming. |
| B06 | A2 + D1, external encoder bypass | Candidate; depends on native A2. |
| B07 | B01 with deliberately delayed D1 | The currently tested B01 preview already uses this delayed strategy. It is an overlapping catalogue variant, not a third independently delivered mode. |
| B08 | B02 with delayed D1 | Candidate; no native combined pass. |
| B09 | Sherpa first, Nemotron ASR refinement later | Native saved-source coordinator passes exact51/87reference events and separate model lifetimes; primary/refined revisions preserved. Actual GUI/controller/D1/live integration pending. [Evidence](SEQUENTIAL_ASR_FINDINGS_V1.md). |
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
| Actual quiet I2S route | 12s native input, conversion counts, control readbacks, route restoration and closed capture | Speech/noise quality, live combined B01, acoustic clock calibration or endurance |
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

Much of the elapsed campaign time has been engineering and verification: native numerical discrepancies, allocation failures, graph-cache growth, thread-stack reservations, unnecessary imports, Stop/drain behavior and source-bound evidence review. Successful current application trials take roughly a minute; slower D1 variants took minutes per short file. No training or large new download is running. The requested ten-minute continuation is periodic work, not continuous computation between wakeups.

## Native runtime, ONNX and lower-level implementation

The working D1 route is a **Python application calling a native C++ CPU runtime**, using the already-staged mixed-Q8 model. “Native build” here means those compiled ARM64 components; no separate PyNative product/runtime has been qualified. ONNX Runtime is the likely intended “Onyx runtime.”

- Pi environment: aarch64 Bookworm, Python 3.11.2, glibc 2.36, ONNX Runtime 1.29.0 and sherpa-onnx 1.13.4, as inventoried.
- Sherpa, ReDimNet and punctuation use the existing portable runtime stack. D1 high-resolution ONNX graphs and a waveform/state driver are now implemented; separate component checks pass, but full-runtime state parity fails. The host projection diagnosis isolates a specific FP32 arithmetic mismatch. Native natural-feature projection outputs now exactly match host ORT but still fail the PyTorch state gate; a qualified repair is required; no acceleration is claimed.
- The successful Cortex-A76 change retains integer lane grouping before float accumulation while using dot-product instructions. Earlier faster mismatching kernels remain failed attempts; their tolerance was not loosened.
- D1-only bounds: scheduler capacity 2048 with the original 95% guard, 2 MiB metadata reservations with assertions, executable graph LRU capacity 1. The speaker/FIFO history was not shortened. These bounds are qualified only for the tested delayed recipe, not A2 or arbitrary longer workloads.
- Delayed C-ABI recipe: chunk/right/left/FIFO/cache/refresh = **264/1/1/0/264/188**, on an 80 ms coarse grid. Selecting the v3-offline preset is necessary to retain FIFO 0 because that API ignores a zero-valued override.
- Saved previews retain their bound deferred-SciPy sources. The current live research derivative `b01-quiet-artifact-v1/prototype` also uses the checked NumPy FIR and compact archive/PCM sinks. Its actual quiet trial avoided allocation failure but failed input overflow. Separate-process transport, callback bridge and actual startup under fake-device checks pass. Physical PortAudio startup and production-controller drainage integration are still required.
- Process-local native/Python stacks are 1 MiB, allocator settings are bounded, models use one native thread, GPU is off. Original app and OS settings are unchanged.

Credible next optimization work is targeted: actual live-route conversion cost, native A2 resource fit, one useful shorter-latency recipe if measurements justify it, on-demand E0, then a proven alternative runtime when its graph/assets/operator coverage are available. More workers share the same CPU budget and can add copying/context/memory costs. Keep one ordered stateful D1 stream. Do not apply silence skips until source mapping, quiet/overlap speech, cache, returning speakers and flush are validated.

## What we are waiting on

| Item | Waiting on | Does it block current offline work? |
|---|---|---|
| Spoken/XVF and restaurant validation | Future consented, labelled speech with frozen working modes | No; the user is not providing speech/playback now |
| Physical screen/touch review | User-visible preview and hands-on interaction | No |
| Live B01 integration | Integrate isolated source startup/controller and qualify a changed bounded quiet trial | Quiet capture is authorized; overflow remains unresolved and no complete30s live pass exists |
| Native A2 / B02 | Actual controller/GUI integration of qualified sequential ASR; separate memory qualification for combined B02 | Generic A2 and sequential saved-source checks pass, but A2 is slower than real time |
| 30/60-minute tests | Fresh bounded time/resource/output admission and an appropriate long input | Short runs cannot substitute |
| Resource adjustments | Fresh measured admission under existing user authorization | No new question; isolated A2/ORT use1536MiB virtual caps, not proof of integrated fit |
| Alternative D1 ONNX runtime | A justified projection-arithmetic repair, then full waveform/state checks | ARM reproduces the same mismatch; numerical gates are unchanged |

At closureV92 combined outputs used4,415,554,387 of5,368,709,120bytes. The52GiB host/target payload policy, retained reservations and fixed32GB Pi capacity are separate checks. Future tests need fresh measured admissions and bounded logs. Device RAM is2GB; default768MiB and isolated1536MiB virtual caps are not RSS limits. The kernel has no memory cgroup controller, and global swap counters do not establish per-job swap-free behavior.

## Shortest path to real-world validation

1. **Live B01 diagnostics:** integrate separate-process capture startup/controller and qualify exact IPC, drain, restoration and combined resources before a changed autonomous quiet trial. Compact output and reopenable microphone PCM already pass scoped checks; input overflow remains unresolved. No periodic reset workaround.
2. **Future spoken session:** after a stable field candidate, use consented material to inspect captions, delayed speaker changes and Stop/drain. The user is not supplying speech/playback now, so continue autonomous software and quiet-route work without requesting it. Existing retention consent persists; quiet tests cannot establish speech quality.
3. **Native sustained run:** bounded original-paced 30 minutes, then 60 for a finalist. Track dense-speech backlog, caption/label delay, CPU/RAM, thermals/clocks/throttle, failures and drain. Repeated/constructed input remains a diagnostic, not independent accuracy evidence.
4. **Real noisy comparisons:** freeze settings first; compare microphone reference, XVF Auto ASR and postprocessed outputs where actual firmware/routing supports them. Preserve simultaneous chronology and paired listening gains. Separate restaurant babble, steady fan/HVAC noise, impacts, quiet/brief speech, overlap and returning speakers. Use known consenting speakers; do not deliberately record unrelated conversations.
5. **Release:** choose useful modes from measurements, qualify install/update/rollback and physical UI, keep failure behavior explicit, complete remaining acceptance gates, and back up reviewed code/manifests.

Native A2/B02 and sequential refinement progress alongside these gates. Their remaining integration work should not delay a stable B01/B05 field candidate; current saved-file previews alone do not establish that field readiness.

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
- Continue every ten minutes with concise, factual progress and compute status. Do not invent activity, duplicate healthy jobs or repeat passed tests.
- Prioritize native live readiness, a small mode shortlist and decisive tests. No further Windows sweeps unless they resolve a specific Pi blocker.
- Reuse verified models/builds and existing reference arrays. Keep historical failure evidence, but avoid reprinting it in every prompt/report.
- Freeze configuration before real-world tests. Avoid full combination sweeps, speculative extra agents, repeated documentation and duplicate archives.
- Record exact measured compute/resources; do not invent token-cost totals or promise a finish date for unmeasured gates. The authorized review checkpoint remains October 1, 2026 at 17:47:34 UTC (13:47 EDT).

## Evidence and practical links

- [Current native status](STATUS.md), [latest small check summary](CHECK_SUMMARY_V47.json), [B01 findings](B01_PREVIEW_FINDINGS_V1.md).
- [B01 launch instructions](README_B01_PREVIEW_V1.md), [B05 launch instructions](README_B05_PREVIEW_V3.md).
- [Actual method coverage](NATIVE_METHOD_COVERAGE_V1.md), [composition research plan](../RESEARCH_PLAN.md), [held-out real-world requirements](../../realtime_validation_v1/REAL_WORLD_HOLDOUT_V1.md).
- Private listening examples: `G:\Just_Peachy_N1\20260924_campaign\local\n5\listening-examples-v1\index.html`. Synthetic scenes through real hardware are not recordings of real conversations; the real cafeteria excerpt is only 0.75 seconds. These examples do not establish restaurant performance.
- Exact source/model hashes and immutable admissions live in the versioned qualification/review receipts. Audio, transcripts, vectors, personal profiles and weights stay private; reviewed small code/docs go to the campaign Git branch.

Live route update: the actual quiet I2S/I2C source, conversion and tested settings restoration passed after the authorized restart. Capture is now closed. Combined live B01, independent acoustic timing and speech/noise quality remain open. See [recovery findings](QUIET_ROUTE_RECOVERY_V1.md); the earlier [read-only route inventory](LINUX_ROUTE_READINESS_V1.md) is preserved.
