# v29 iteration report — evidence and delivery status

This report answers the twelve requested delivery questions using
[NATIVE_RESULTS](NATIVE_RESULTS.md), [MODE_GUIDE](MODE_GUIDE.md), and
[RAM_RESOURCE_GUIDE](RAM_RESOURCE_GUIDE.md). Full-application hour04 is now a
failed application attempt with a complete closed file mirror and reviewed
prefix telemetry; termination-cause diagnosis remains pending. Qualification
build13 was staged and completed the targeted History Export04 check. Research06
exposed a late-label projection defect; repaired qualification14 was staged and
Research07's reviewed comparison and optional live Followup02 passed their
specified scopes. Production16 is **staged, activated and consolidated to one
unified shortcut**, with complete host readback of both desktop transactions.
Its final actual Desktop Exec/idle/policy-control/normal Exit check passed.
Acceptance permits guarded field testing; it does not establish an application
hour or representative speech-quality result.
Verified backup03 is complete. GUI-only15 changes policy selection/display;
production16 retains its exact runtime content with separately reviewed reuse of
the actual14 optional evidence. No new production capture is claimed.
The prior eleven owned shortcuts have independent archive/restore copies outside
Desktop; unrelated icons and disabled autostart remain unchanged.
Historical `FINAL_*` receipts and frozen releases are unchanged.

**Evidence labels:** implemented means source/host contracts exist; functional
means the stated path completed; native means it ran on the CM5; sustained means
the stated continuous duration completed with reviewed final evidence; quality
requires a matched reference. These labels are not interchangeable.

## 1. Exactly what changed

The new candidate separates pipeline selection from live/saved input, uses a
configurable 300-second normal source policy with separate drain/cleanup limits,
and supplies an explicitly admitted developer hour policy. Disk-backed exact
processed audio, bounded raw transport, persistent captions, capacity admission,
UUID sessions and indexed history replace the fixed four-recording scheme.
Stop/closure precedes keep/discard. A kept recording can be replayed in full.
The launcher adds profile controls, history, developer diagnostics and retained
device-relative direction/motion controls. Research options add sparse embedding
queries, late speaker labels and a separately gated optional D1 child.
Existing Sherpa/PnC, galleries, XVF routing and calibration remain pinned/reused.

## 2. New profile and shortcut matrix

| Operator choice | Implemented selection | Delivery/evidence boundary |
|---|---|---|
| Diarizer | Pyannote or a named Nemotron geometry | Exact mode table in [MODE_GUIDE](MODE_GUIDE.md#nemotron-configurations) |
| Identity backend | ReDimNet, TitaNet, anonymous | Separate galleries; anonymous behavior differs by diarizer |
| Input | Live, WAV, entire kept processed session | GUI02 passed live300 and full kept-session replay |
| Research | Sparse clean-turn embeddings, single-D1 late labels, optional second D1 | Explicit experimental controls; optional normal use requires reviewed combined admission |
| Desktop | One unified scrollable launcher, opening idle with normal Exit | Actual production16 activation, eleven-shortcut consolidation and final Desktop Exec/idle/normal Exit passed with complete closed readback |

No new shortcut per experimental profile is required. Prepared activation,
backup, consolidation, rollback and actual Desktop Exec/idle checks are described
in [README_DESKTOP_ACTIVATION](README_DESKTOP_ACTIVATION.md) and
[README_GUARDED_ACTIVATION](README_GUARDED_ACTIVATION.md). The final check used
programmatic Tk controls through the actual desktop command, not a physical
double-click or touch test. Rollback copies and the explicit restore procedure
are preserved; rollback was not invoked against the delivered release.

## 3. Exact Nemotron parameters

The [exact geometry/provenance matrix](README_PIPELINES.md#geometry-and-provenance)
lists all twelve configured rows: cache, FIFO, chunk, right/left context, update
and nominal input seconds. Retained CurrentDelayed is
`264/0/264/1/1/188`; retained Streaming is `264/80/13/1/0/40`; Chunk52 is
`264/80/52/1/0/40` in that column order. The explicit two-thread variant preserves
Chunk52 geometry. Official and local intermediate configurations are identified
separately; local candidates are not NVIDIA recommendations.

## 4. Latency versus RTF

Nominal buffer is `(chunk + right) × 80 ms`, excluding computation and delivery.
Measured first output, caption latency, backlog and compute RTF are separate.
For example, Chunk52's buffer is 4.24 s; the one-thread short run first output
was 5.125 s and component RTF 1.08129. Official Ultra Low produced first output
at 0.460 s but prefix RTF was 8.11915 and it did not reach EOF. Earlier output
therefore does not establish sustainable processing. Paced elapsed time includes
source pacing and drain; overlapping component times cannot be summed into an
end-to-end RTF. [Exact cohort and scopes](NATIVE_RESULTS.md#short-isolated-component-cohort).

## 5. Chunk52 optimization and bottlenecks

The separately pinned two-thread core reduced short matched component RTF from
1.08129 to 0.55433, approximately 1.95× throughput. All 4,470 × 8 probabilities
matched the retained reference exactly. Original profiles remain unchanged.
The one-thread run's mature calls were about 1.55 RTF; native graph computation,
not small input copies, was the measured dominant cost. The compact 3.04 s
candidate completed at 0.85681 RTF but changes context and has no quality or
numerical-equivalence claim. CPU contention with ASR/embeddings and cooling
remain integrated concerns. [Optimization evidence](README_NATIVE_OPTIMIZATION.md).

## 6. RAM and CPU

All measurements are on the 2 GB CM5. Saved CurrentDelayed/ReDimNet worker peak
sampled RSS was 556,761,088 B; saved Pyannote/TitaNet was 468,762,624 B. Live300
worker RSS reached 500,858,880 B; its external aggregate trace began late and
covered replay, so it cannot certify the earlier whole-live peak. These runs
used the unchanged 768 MiB per-process address-space guard. RSS, PSS, virtual
size, owned swap and system available RAM are distinct metrics.

Hour04's4,228 worker health rows reached RSS616,251,392 B/PSS607,257,600 B and
VM peak797,163,520 B, close to the805,306,368 B AS ceiling. Whole-unit sampled
RSS reached643,776,512 B, available RAM stayed above1,210,351,616 B and owned
swap was zero. This demonstrates physical headroom during the failed prefix,
not mature end-to-end success or the reason for its termination. Whole-unit
sampled temperature peaked at79.85°C.

The completed component hour had later RSS near 166.5 MiB but reached 85.35°C
and late RTF near 0.94. This points to CPU/cooling headroom, not demonstrated
physical RAM exhaustion. More 4/8 GB capacity may help simultaneous residency;
it does not change the virtual-memory policy, CPU quota or graph work. No larger
board was measured. [Memory table and limits](RAM_RESOURCE_GUIDE.md).

## 7. Provisional/correction results

Stable caption IDs, source times and bounded revisions are implemented. Research07
passed the matched sparse/late-label comparison after repairing the projection
of supported upstream identities; compared input, probabilities and ASR were
preserved. Research06 remains a failed projection attempt. This functional
comparison does not establish representative speech or identity quality.
Optional-first01 completed the primary's 715,127 samples, but its D1 child failed
at 2,880 samples with zero frames when empty warm-up acknowledgements filled the
consumer queue. This establishes primary fallback, not a combined pass. The
narrow repair retains protocol checks and bounds. Actual optional-first02 reached
primary/refiner EOF with 715,127 samples and 4,470 refiner outputs; this does not
by itself establish correction consumption or a normal combined admission.
The first live followup retained the primary's300-second result and closed the
outer job, but the secondary exceeded its active30-second label-lag limit and did
not report EOF. That failed attempt remains separate. Actual First03 completed
715,127 source/refiner samples and4,470 outputs with model/owner closure and
measured resource fit. It produced zero optional revisions, so it establishes
short combined feasibility, not a correction or quality result. Its selection
uses `revision_window_seconds=60` and its saved45 policy separately allows60seconds
drain. Reviewed live Followup02 completed4,800,000 primary/raw/child samples,
30,001 child frames, source EOF, model closure and exact owner closure. It also
produced **zero optional corrections/history**: successful combined completion
does not demonstrate correction consumption or quality. Its sampled aggregate
RSS/PSS peaks were760,020,992/700,768,256 B; minimum available RAM was1,178,828,800 B
with no owned swap. The normal optional receipt authorizes only this exact live
Pyannote/TitaNet/window60 configuration and300/60/30 source/drain/backlog policy.
The legacy timing comparison uses a model/options-matched saved715127 baseline,
not a matched live300 experiment. [Architecture and research boundaries](RESEARCH_ARCHITECTURES.md).

## 8. Sustained session results

GUI02 completed a policy-driven 300-second live capture and its full saved replay,
with 4,800,000 samples in each source timeline. It used no injected manual Stop.
The separate two-thread Chunk52 **component-only** hour completed 57,600,000
samples and 360,001 frames at RTF 0.8844478644, with no drops. Its late bins near
0.94 did not sustain the preferred 0.8–0.85 headroom target.

Full-application hour02 failed around 319 s on the output-membership guard;
physical closure/full mirror passed, but missing final worker receipts prevent
logical/model-cleanup or hour credit. Full-application hour04 also **FAILED**:
systemd recorded signal9 and watchdog termination was reported. Its exact owner
and cgroup closed, and all786 regular files /651,313,592 bytes were independently
mirrored (`full-app-hour-04-monitor-01`). Worker RESULT, HOST_CLOSURE and
session_summary are absent. The stored57,359,280 samples cover3584.955 s, short
of3600 s; last health source time was3584.695 s. Backlog peaked at27.55 s while
mean diarizer-push rolling RTF was about0.450; source time fell behind wall time.
That component metric cannot certify overall throughput. Full source EOF,
successful drain, logical/model cleanup and a sustained-application pass are not
established. Termination-cause diagnosis is pending; signal9 alone does not
establish OOM. Neither failure is merged with the successful component hour.

## 9. Post-Stop recording preservation and capacity

GUI02 saved raw + processed after physical closure, replayed the entire kept
source to EOF, discarded only the replay, then exited. Raw was actual MIC0–MIC3
at 16 kHz PCM32, packed by firmware over 48 kHz stereo transport; it was not four
channels captured at 48 kHz. Exact float32 processed samples and authoritative
sample counts drive replay; no complete recording is loaded into RAM.

Native storage-check01 exercised **35 synthetic sessions, 31 kept recordings,
five history pages**, reopen/restart, selected/single export, isolated deletion
and discard, and new admission afterward. These are storage fixtures, not 31
speech-model recordings. Capacity uses explicit per-session reserves/free-space
floors; failed sessions consume no global slot and there is no automatic deletion.
Export03 preserved the selected original and passed PC verification of all 112
members in a 142,926,668-byte ZIP. Actual **History Export04 passed** the real
widget callback and normal Exit, with ten stable fullscreen observations,
unchanged original metadata and no capture/model invocation. Its closed mirror
and independent PC readback verified 112 members /142,904,468 payload bytes in
a 142,926,668-byte ZIP. This closes the targeted callback/offload check without
rerunning capture; it is separate from export03.
[Storage](README_STORAGE.md), [whole-session replay](README_SAVED_REPLAY.md),
[owned export](README_OWNED_EXPORT.md).

## 10. Files modified or added

| Source area | Principal files and detailed documentation |
|---|---|
| Policy, selection, native binding | `profiles.py`, `nemotron_binding.py`; [pipeline documentation](README_PIPELINES.md) |
| Lifecycle and shared engine | `launcher.py`, `worker.py`, `installed_engine.py`, `native_scope.py`, `runtime_support.py`; [runtime README](README.md) |
| Audio/storage/source | `storage.py`, `audio_journal.py`, `saved_replay.py`, `owned_export.py`, `installed_source.py`, `raw_capture.py`, `source_batch.py`; [storage](README_STORAGE.md), [batching](README_SOURCE_BATCH.md) |
| UI and research | `runtime_ui.py`, `runtime_ui_channel.py`, `late_labels.py`, `sparse_embedding.py`, optional-refiner modules; [mode guide](MODE_GUIDE.md) |
| Evidence and deployment utilities | Package/authorization, guarded actions, monitor, scoped backup/reconciliation, activation/consolidation/rollback helpers and matching READMEs |

This is a navigation list, not a byte inventory or claim that every file changed
in every build. Each immutable package manifest and reviewed derivative's exact
source diff is authoritative. v27/v28, failed receipts and old `FINAL_*` files
remain preserved; external utilities do not mutate frozen qualification packages.

## 11. Tests and evidence currently credited

| Evidence set | Credited result at this snapshot |
|---|---|
| Eight short matched component rows | Five full-input completions; three official-profile failed prefixes. Prefixes are not full-file passes. |
| Saved pipeline04 and05 | Two complete 715,127-sample pipelines: Delayed/ReDimNet and Pyannote/TitaNet respectively, with closed mirrors. |
| GUI02 | 43 programmatic Tk controls, stable 480×800+0+0 fullscreen, live300/raw-save/full replay/discard/Exit. Physical touch/visual quality unqualified. |
| Storage-check01 / export03 | 31 kept synthetic fixtures across35 sessions; separate112-member selected export/readback. |
| Component hour01 | One continuous diarizer-only hour with reviewed limitations; no whole-application hour credit. |
| Full-application hour04 | Failed signal9;786-file/651,313,592-byte closed mirror passed. Missing final worker/session receipts; no sustained-application pass. |
| Production backup02 | Failed finite snapshot deadline; exact owner/cgroup closed, leases released,19-file/1,167,954-byte guard mirror complete. Partial PC copy has426 complete hash-matching files/638,307,564B; no COMPLETE backup credit. |
| Production backup03 | VERIFIED_CURRENT_RELEASE_BACKUP:1,932 files/657,980,201B, independent full PC readback and source membership/hash checks, exact natural owner/cgroup closure and leases released. Selected current-release/user-data scope; historical exclusions remain explicit. |
| History Export04 | One actual History Export callback and one normal Exit; ten stable fullscreen observations; closed mirror plus independent112-member PC verification; original recording unchanged. |
| Research07 / optional First03 / Followup02 | Research07 matched comparison passed. First03 short feasibility and Followup02 live300 completed child EOF/model/owner closure. Both optional runs produced zero correction revisions; no quality or full-application hour credit. |
| Production16 desktop delivery | Stage16 verified328 files including manifest. Activation01 and consolidation01 completed naturally; host readback02 verified10 activation metadata files and46 archive members, respectively. One unified shortcut remains, with prior shortcuts preserved outside Desktop. |
| Final production idle01 | Actual Desktop Exec/native_scope/default data root;10 stable480×800+0+0 observations; actual optional policy300/120/60/30/60 and ordinary300/120/120/120/60;267 disabled-Start checks and zero Start invocations; normal Exit, all nested/watchdog/outer closure and37-file/234,564-byte closed mirror. No worker/model/capture. Autostart disabled, display270 and settings unchanged. |
| One short matched ASR reference | 38 reference words; 12 substitutions,2 deletions,2 insertions; WER42.1053%. No DER or representative live identity score. |

No global "all tests passed" count combines unrelated host suites or native
attempts. Export01 import-memory failure, export02 lease refusal, GUI01 locator
failure before Start, raw boundary/control failures, early pipeline guard/model
load failures, optional-first01 child failure and full-app-hour02/hour04 failures remain
separate. Their later repairs do not retroactively change those outcomes.
Initial activation/consolidation host readers failed after the successful native
transactions; narrowly scoped host-only readers completed their readback without
repeating either native action. The original failed readbacks remain preserved.
Exact private receipt names and measurement definitions are in
[NATIVE_RESULTS](NATIVE_RESULTS.md); no private transcript, audio or image is
included in this report. Drafting this report ran no tests or experiments.

## 12. Remaining limitations and technical questions

| Gate | Current status |
|---|---|
| Repaired full application hour04 | **FAILED** at3584.955 s stored source; physical closure/full mirror and numeric prefix review passed. Cause diagnosis **PENDING**; missing final receipts prevent EOF/drain/cleanup credit. |
| Repaired optional first + live followup | First03 short feasibility and Followup02 live300 **PASS** for exact EOF/resources/model/owner closure, with zero optional revisions. Failed First01 and Followup01 remain separate. No correction, quality or hour pass inferred. |
| Matched sparse/late-label research comparison | Research07 reviewed comparison **PASS** after the projection repair; compared input/probabilities/ASR preserved. Research06 remains failed; no representative quality pass inferred. |
| Actual History Export04 | **PASS**, including actual widget invocation, natural closure and independent full ZIP readback. |
| Current-release/user-data full backup | Backup03 **VERIFIED COMPLETE**:1,932 files/657,980,201B with source and independent PC readback. Backup02 remains a failed attempt. Historical exclusions stay explicit preserved references. |
| Production16 from GUI-only15 | **DELIVERED**: staged, activated, one-shortcut consolidation and actual Desktop Exec idle/policy-controls/normal Exit all passed with closed readback. Accepted for247 guarded field-testing rows (246 standard plus one measured optional row); actual14 model evidence remains explicit. Physical touch/visual quality and a full-application hour remain unqualified. |

Open questions are the whole-pipeline thermal/CPU margin, mature optional-child
memory/throughput, sparse scheduling's effect on identity evidence, and quality
on representative labeled speech. Quiet live input made zero embedding and
punctuation inference calls, so its successful five-minute workflow cannot
answer those questions. Neither early output nor extra RAM alone proves real time.

The root operator updates this document only from reviewed closed evidence before
final publication. Inputs are the three linked evidence guides and exact new
receipts; output is this text-only report. Reproduction commands, inputs/outputs,
PowerShell and Command Prompt/Anaconda instructions remain in the linked component
READMEs. This document introduces no executable step, new experiment or archive.
