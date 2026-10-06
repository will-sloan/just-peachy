# Runtime modes: current candidate and retained measurements

## Current release: build26, six scoped live routes and rich replay

The deployed build26 chooser has six named combinations: Pyannote,
CurrentDelayed or Chunk52 with two native graph threads, each with ReDimNet or
TitaNet. Select Live microphone or Saved WAV independently, then Open Application
to enter the retained portrait Mode/People/Settings application. The collapsed
Advanced attribution control retains single-D1 sparse/late policies; parallel
refinement remains disabled. The [current operator guide](stabilization_20261005/STABILIZATION_MODE_GUIDE.md)
and [completion backend matrix](../../../completion_20261001/BACKEND_COMBINATIONS.md)
describe these six choices; the broad historical selection matrix below does
not describe the current normal chooser.

The [speech storage repair](stabilization_20261005/SPEECH_STORAGE_REPAIR_FINDINGS.md)
prepares fresh text/SQLite allocation and independent terminal-cleanup metadata
after an actual speech session exhausted the old SQLite pool. New finite
checks reserve 256 MiB independently on Pi and PC and remeasure shared history;
this reserves disk space, not RAM. CHECK21 passed Pyannote/ReDimNet speech,
Stop/cleanup/Save raw + processed over 60.4 s / 966,400 samples with 48 indexed
nonempty captions and 40 visible rows; no failure or cleanup error was recorded.
This resolves source acquisition and metadata cleanup for that bounded run.
Its verified export confirms120 Pyannote segmentation calls and208 normalized
192D ReDimNet embedding calls; setup counters alone were incomplete evidence.
Naming accuracy and300s/hour use remain unqualified. Refer to the current result
matrix for other routes. Fresh staged build26 CHECK28 passed full rich saved
spatial replay/processed Save/Exit with source pins unchanged/current motion
excluded and independent closure. Build26 is activated; all six rows have
bounded native Live function/closure observations with separate quality limits.
Rich replay uses
recorded beams/BMI and original source anchors; plain WAV cannot supply spatial
cues. The original C088 identity calibration is not transferred to other
encoder/diarizer domains. Missing accepted calibration or cues stays Unknown.

## Preserved production16 guide

Later per-combination results are centralized in [STABILIZATION_RESULTS.md](stabilization_20261005/STABILIZATION_RESULTS.md);
the production16 instructions below are historical.

The consolidated launcher previously ran **v29 production16** at
`/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-16`.
The old v27/v28 runtimes, galleries and recordings remain rollback references.
The release permits 247 exact selections (246 nonoptional and one optional); this
is an authorization matrix, not 247 native tests. Actual model evidence retains
its original build identity, including build14 optional measurements reused by
reviewed GUI and path-only changes. See [IMPLEMENTATION_CHECKLIST.md](IMPLEMENTATION_CHECKLIST.md)
and [NATIVE_RESULTS.md](NATIVE_RESULTS.md) for each measured scope.

## Choose a pipeline, then choose its input

The unified launcher separates three choices: diarizer, embedding identity
backend and input source. Sherpa ONNX ASR and punctuation remain the text path.
Live input comes from the existing XVF3800 route; saved input is a pinned WAV or
a kept session's complete processed timeline. BMI270 motion integration remains
shared. A saved recording has no new live direction/motion evidence.

| Choice | What it does | Important distinction |
|---|---|---|
| Pyannote | Existing local speaker activity/association path | Baseline to compare against Nemotron on the same recording |
| Nemotron | Explicit native diarization geometry below | Accepting microphone audio does not imply sustainable real time |
| ReDimNet | Existing embedding and its own gallery | Named matching requires an appropriate enrolled gallery |
| TitaNet | Existing NeMo embedding and its separate gallery | Never mixes vectors or thresholds with ReDimNet |
| Anonymous | Speaker tracking without named-gallery matching | Pyannote retains ReDimNet continuity; native D1 skips embedding. A model slot is not automatically a stable person identity |
| Live | Physical microphone, finite normal 300-second policy | Stop and source closure precede the audio retention decision |
| Saved | Same processed samples replayed through another selection | Appropriate for matched comparisons; no audible playback is required |

The operator entry is the consolidated scrollable launcher shortcut. Temporary
experimental geometries belong in its selector, not in dozens of desktop icons.
The actual production16 check opened idle and returned through normal Exit. Do not
run historical one-shot campaign dispatchers as normal launchers.

## Nemotron configurations

All values are 80 ms encoder frames. The nominal input buffer is
`(chunk + right) x 0.08 s`; it excludes computation and delivery delay.

| Profile ID | Cache | FIFO | Chunk | Right | Left | Update | Nominal buffer | Current evidence |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `current_delayed` | 264 | 0 | 264 | 1 | 1 | 188 | 21.20 s | Build07 full saved44.6954s pipeline completed; peak workerRSS556,761,088B (531MiB), unchanged768MiB AS; build08 live300 GUI/raw-save/full-replay workflow also completed; sustained full application and quality remain separate |
| `chunk52` | 264 | 80 | 52 | 1 | 0 | 40 | 4.24 s | New isolated CM5 full-input RTF 1.08129, exact retained probabilities; mature calls slower |
| `chunk52_threads2` | 264 | 80 | 52 | 1 | 0 | 40 | 4.24 s | Explicit two-thread native build: short matched RTF0.55433 with exact retained probabilities; closed1h component replay RTF0.88445, late~0.94,85.35C; not whole application |
| `streaming` | 264 | 80 | 13 | 1 | 0 | 40 | 1.12 s | Retained component RTF about 3.634; new live route requires integration qualification |
| `official_low` | 264 | 264 | 9 | 4 | 0 | 222 | 1.04 s | Native early output, but incomplete input at processing deadline; prefix RTF 4.81915 |
| `official_very_low` | 264 | 264 | 6 | 2 | 0 | 222 | 0.64 s | Native first output 0.816 s; failed at processing deadline after 28.5 s input, prefix RTF 5.79081 |
| `official_ultra_low` | 264 | 264 | 3 | 1 | 0 | 222 | 0.32 s | Native first output 0.460 s; failed at processing deadline after 20.5 s input, prefix RTF 8.11915 |
| `candidate_1_2` | 264 | 80 | 14 | 1 | 0 | 40 | 1.20 s | Experimental, measurement pending |
| `candidate_2` | 264 | 80 | 24 | 1 | 0 | 40 | 2.00 s | Full matched input complete, RTF 2.12330; first output 2.462 s; cannot sustain real time in this scope |
| `candidate_3` | 264 | 80 | 37 | 1 | 0 | 40 | 3.04 s | Experimental, measurement pending |
| `candidate_4_5` | 264 | 80 | 55 | 1 | 0 | 40 | 4.48 s | Native full-input RTF 1.10906; no short-input speed benefit |
| `candidate_3_compact` | 128 | 40 | 37 | 1 | 0 | 40 | 3.04 s | Native full-input RTF 0.85681; changed context and unmeasured quality, not sustained qualification |

CurrentDelayed is the retained local geometry, not an assertion that it equals
the current NVIDIA offline reference. Official preset provenance and native
C-ABI override rules are documented in [README_PIPELINES.md](README_PIPELINES.md).
The intermediate points are local experiments, not NVIDIA recommendations.

A separately pinned two-thread Chunk52 native build completed the same 44.6954 s
input at RTF 0.55433, with all 4,470 x 8 probabilities identical to the retained
reference. Its explicit operator option requires the separately pinned native
library and component evidence. The original
Chunk52 profile remains unchanged. A later continuous repeated-input hour completed with average componentRTF0.88445; late10-minute bins approached0.94 and temperature reached85.35C. Sampled RSS plateaued near166.5MiB. That closed hour is component-only and supplies neither whole-application real-time qualification nor speaker accuracy. See exact scope in [NATIVE_RESULTS.md](NATIVE_RESULTS.md).

## Research adaptations

* **Sparse clean-turn embeddings:** use diarization confidence and overlap
  evidence to avoid refreshing embeddings on every ambiguous interval. Keep
  source time and ASR audio continuous. This is an explicit experimental
  scheduling choice, not a silent threshold or model replacement.
* **Single-diarizer late labels:** let ASR text arrive independently, then revise
  recent speaker attribution using source-aligned Nemotron results. Preserve
  caption IDs, words and text revision provenance; bound the revision window.
* **Optional second diarizer:** Actual build14 First03 completed matched saved45 child/primary EOF; Followup02 then completed all4.8M primary/raw/child live300 samples and30,001 child frames with window60, source300/drain60/backlog30. Full owner/model closure and sampled aggregateRSS760,020,992B/minimumavailable1,178,828,800B/owned swap0 support that bounded experimental scope. Zero optional corrections were observed. The exact measured receipt is accepted for production16 through reviewed GUI-policy and path-only reuse. Its actual idle GUI verified the controls without starting models or capture; the model measurements remain build14 facts. The actual build13 window30 child timeout remains a preserved fallback result, not full child EOF.

See [RESEARCH_ARCHITECTURES.md](RESEARCH_ARCHITECTURES.md) for primary papers,
what was adapted, and what has not been reproduced. Host tests do not establish
native speaker accuracy. See [RAM_RESOURCE_GUIDE.md](RAM_RESOURCE_GUIDE.md) for
the current 2 GB evidence and the unmeasured potential benefits of 4/8 GB.

## Selecting the reviewed optional mode

These controls were verified in the actual production16 idle GUI: the option enabled for the exact selection below, and checked/unchecked policy summaries matched. All 267 Start-disabled checks passed, with zero Start invocations, model loads or capture; normal Exit and complete ownership closure passed. Capture and optional refinement open unchecked. This idle check adds no new model-performance or physical-touch evidence.

1. Choose **Pyannote**, **TitaNet** and **live**. Keep embedding schedule **continuous**, refresh **2 seconds**, and speaker attribution **retained**.
2. Enable experimental options. In Developer settings, set **Label revision window in seconds (1-300)** to **60** before selecting the optional refiner. Keep the legacy provisional-correction checkbox off.
3. The **Optional anonymous CurrentDelayed refiner** checkbox becomes available only when the release contains one exact approved selection/policy/assets proof. Its description must say **reviewed combined admission available**. Otherwise the mode remains unavailable; do not substitute another source, embedding or policy.
4. Check the optional refiner. Advanced and Launch must display **Source 300 s; load 120 s; drain 60 s; backlog 30 s; cleanup 60 s.** Start revalidates these exact settings. Unchecking optional restores the ordinary300/load120/drain120/backlog120/cleanup60 policy.

The measured child processed full live300 within this explicit60-second revision window; its maximum observed label lag was30.98s, not a promise of instantaneous labels. Zero optional label corrections were observed. The actual2GB unit sampled aggregateRSS760,020,992B/PSS700,768,256B, minimumavailable1,178,828,800B and no owned swap. This supports the stated bounded experimental fit/function only, not all model combinations, power efficiency, speaker accuracy or sustained operation. The distinct single-D1 late-label option has its own actual anonymous-evidence result and does not use this second worker.

See [exact GUI policy contract](gui_optional_policy_derivative_20261004/README_GUI_OPTIONAL_POLICY.md) and [optional evidence/lifecycle](README_OPTIONAL_REFINER.md). When returning to a stable ordinary profile, use its exact authorized Experimental value; a leftover true flag is a different selection, not implicit permission.

## Record once, compare fairly

Normal sessions use a configurable 300-second source limit. Audio is spooled
in bounded disk segments. After Stop and drain, choose processed audio, raw plus
processed when the actual raw adapter is qualified, or discard. The processed
float timeline is authoritative; replay-compatible WAV exports preserve its
source order with documented representation. Raw means physical MIC0-MIC3,
not the XVF processed output. The packed physical route currently tested is
four-channel16kHz PCM32 with a shared sample clock and explicit timing metadata. The actual07 source-only raw qualification passed and all outputs were mirrored. Actual build08 GUI02 then exercised43 controls, reached the ordinary300-second source boundary with4800000 processed and raw samples, saved raw, replayed the whole kept source to natural EOF, discarded the replay and exited. This is programmatic Tk/control/source evidence; the quiet run does not establish speech accuracy or physical-touch ergonomics.

Recording availability is governed by storage admission and explicit retention,
not a four-slot deployment counter. UUID session IDs, indexed paged history and
leases protect independent recordings. Discard/deletion targets one owned
recording; it must not delete another session or renew a runtime to free a slot.
Actual native storage-check01 kept31 synthetic recordings across35 total sessions and exercised five history pages, restart/reopen, selected/single export, isolated delete/discard and new admission afterward, with complete closure/PC mirror. These are storage fixtures, not31 acoustic/model recordings. Actual GUI02 separately exercised kept-history replay/discard. Export03 verified the unchanged export data path in a fresh owned child and all112 ZIP members on the PC; actual build13 History04 subsequently passed the History Export callback and normal Exit without capture/models.

To compare modes, save one processed session and use History Replay or the
saved-input CLI with each selected profile. Compare identical sample counts
and hashes. Unmatched live conversations are useful field observations but not
a controlled quality comparison. Ground-truth labels are needed for DER; an
unlabeled quiet run cannot measure speaker accuracy.

## Where to read next

* [README.md](README.md): runtime components and entry commands.
* [README_STORAGE.md](README_STORAGE.md) and
  [README_SAVED_REPLAY.md](README_SAVED_REPLAY.md): retention, history and replay.
* [README_PIPELINES.md](README_PIPELINES.md) and the individual `pipelines/`
  documents: architecture, parameters, mathematics and integration for each mode.
* [README_LATE_LABELS.md](README_LATE_LABELS.md) and
  [README_SPARSE_EMBEDDING.md](README_SPARSE_EMBEDDING.md): experimental identity logic.
* [README_RELEASE_AUTHORIZATION.md](README_RELEASE_AUTHORIZATION.md): production
  authority, pinned assets and rollback requirements.
* [README_SOAK_DISPATCH.md](README_SOAK_DISPATCH.md): explicitly admitted long
  continuous replay. A successful five-minute recording is not an hour-long pass.

The component READMEs provide purpose, inputs, outputs and PowerShell,
Command Prompt/Anaconda commands. Use the installed production16 launcher;
mutable research files are not a substitute for its pinned package.

## Reading RAM and throughput evidence

The measured machine is the 2 GB CM5 (MemTotal 2,108,473,344 bytes). The saved CurrentDelayed/ReDimNet worker sampled RSS 556,761,088 bytes; the saved Pyannote/TitaNet worker sampled RSS 468,762,624 bytes. These are different whole-pipeline workers on short matched inputs, not continuous aggregate GUI/source/child peaks. The TitaNet run's partial aggregate sample reached RSS 492,240,896 bytes. The quiet live300 GUI run measured its own worker; its late external trace covered replay, not the complete live peak. Do not add peaks from independent runs or use quiet-session inference costs as speech-load measurements.

The 768 MiB per-process AS guard constrains virtual mappings. It is distinct from RSS/PSS and from installed/available physical RAM, and adding two AS ceilings does not estimate dual-worker resident use. Owned swap and system swap have different scopes. Shared pages can be counted in several processes' RSS; aggregate PSS is a complementary measurement.

The two-thread Chunk52 component hour completed with RSS near 166.5 MiB, available RAM above 1.48 GB and temperature up to 85.35 C. Its average component RTF 0.88445 and later bins near 0.94 expose CPU/cooling margin limits despite physical-memory headroom. This does not qualify a whole-application two-thread hour. The repaired full-application hour04 ended at its worker watchdog before source EOF: 57,359,280 of 57,600,000 samples were committed. Whole-unit sampled peak RSS was 643,776,512 bytes and minimum available RAM was 1,210,351,616 bytes with zero owned swap. Worker VmPeak 797,163,520 bytes was near its 805,306,368-byte AS ceiling, but no allocation failure establishes that as the cause. Source delivery fell behind wall time; synchronous storage and shared-lock costs require separate timing evidence. The closed mirror does not establish successful logical/model cleanup. Actual Research07 verified single-D1 anonymous evidence consumption, and First03/Followup02 reached child EOF. Followup02 sampled aggregateRSS760,020,992B/PSS700,768,256B, minavailable1,178,828,800B and no owned swap for its exact live300/window60/drain60/backlog30 scope. Zero optional corrections were observed; broader combinations, quality and sustained operation remain unqualified. First01 startup samples remain a failed prefix.

A 4/8 GB board may allow more resident models/cache when physical memory is the constraint. It does not itself change a fixed virtual-memory limit, reduce native graph work, increase the shared CPU quota or prove improved cooling. No 4/8 GB native measurement or performance scaling claim is available.

The controlled build13 source candidate adds bounded100ms saved/repeated/kept replay appends and numeric append-time/source-wall-lag metrics; see the [source-only batching contract](README_SAVED_SOURCE_METRICS.md). It also includes the reviewed optional activity-handoff repair. Production16 is now activated through the consolidated launcher; actual build13/14 matched45s optional/research trials exercised that changed saved path. Research07 retained exact processedF32, all4,470 x8 native floats and final ASR, while adding30 supported/partial late-label publications. This is not a claim that batching fixes the failed hour04: external5Hz output-tree checks and1Hz fsynced resource sampling are other unmeasured overhead candidates, and their guards remain unchanged. The research comparison reuses baseline04, requires exact processed float32/sample-clock agreement, and compares all4470×8native D1 probabilities by hash and maximum absolute difference with an explicit1e-5 tolerance. No additional baseline, hour or geometry sweep is prescribed.
