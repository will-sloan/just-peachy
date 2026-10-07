# RAM, virtual address space and storage

Current build35 scope: build35 is activated through the Just Peachy shortcut.
Opening stays idle with capture off. Choose one of six backend combinations,
Live microphone or Saved WAV, then Open Application and a Mode. Eleven Mode
policies are visible; backend, identity policy and calibration are separate.

Ordinary Pyannote + ReDimNet Start captured 12.5 s and completed Stop and the
selected full Discard in normal03. That whole check FAILED its later Settings
observer. Separate exit-only05 passed idle Open Application, Settings and Exit
with no Start, capture, models or worker launch. These are distinct scopes.
Live53 passed quiet capture after one verified recovery; Saved54 processed C24
speech with 137 indexed parts, 40 text rows and 117 embedding queries.

Hour08 completed 3600 s / 57.6M samples and all 20 source/model/closure gates.
Backlog grew to 495.360 s; source-to-EOF took 4090.959 s. Completion passed,
but sustainable real-time operation did not. Speech/name accuracy, natural
conversation and biometric calibration remain unqualified or UNCALIBRATED.

Normal live uses manual Stop and storage capacity without arbitrary duration,
recording, people, reference or slot counts, or a fixed ordinary backlog cutoff.
Actual memory/AS/free-space, finite capacity-derived file/drain allowances,
bounded queues, source/lease/owner, I/O and cleanup guards remain. Individual
lane delay labels are unavailable; aggregate backlog remains in health metadata.
Model geometry, thresholds and calibration math are unchanged.

2 GB, 4 GB and 8 GB describe physical RAM. A per-process RLIMIT_AS ceiling describes
virtual address mappings; it is not resident use, available RAM or a duration
allowance. More RAM does not remove repeated CPU/copy work or prove sustained
operation. Backend/model/query/calibration choices keep their own exact scopes.

| CM5 physical RAM | What current evidence permits |
| --- | --- |
| 2GB | Build35 completed the repeated-source hour and closure. Sampled whole-unit RSS797,212,672B; minimum available962,789,376B; owned swap12,976,128B and81.5C. Growing lag/memory prevents sustainable real-time or steady-state qualification. |
| 4GB | More physical headroom may help coexistence/caches. Finite AS/CPU/storage guards still apply; this RAM variant was not measured. More RAM does not fix growing compute lag. |
| 8GB | Greater physical headroom, not automatic latency, naming, thermal or hour qualification. Guarded model/context/CPU costs remain. |

Hour01 on30 failed a genuine D1 speaker backlog at 312 source seconds. Whole-unit
peak RSS 615464960/PSS 599397376 bytes, minimum MemAvailable 1066254336 bytes,
swap 0 and peak 72.15 C belong to that failed scope.

Hour05 on31 failed at 922.9 source seconds. The complete external closed mirror
contains an incomplete compact writer with MemoryError. Whole-unit peak
RSS 648724480/PSS 632099840 bytes, minimum MemAvailable 1125548032 bytes and swap 0
do not indicate physical RAM exhaustion. Worker VmPeak 805224448 bytes was
81920 bytes below the finite 768 MiB ceiling. D1 backlog pressure also existed;
exclusive failure allocation/stop ordering remains unproven. Peak 76 C belongs
to a failed headless repeated-source run, not a thermal/noisy/GUI-hour pass.

Build35 retains source-bound finite 1 GiB model AS for the worker
and admitted recording parents, retaining frontend 256 MiB soft/1 GiB hard,
independent metadata 128 MiB and other parents 768 MiB. Physical free-RAM/disk
floors and CPU/stack/core/task/source/queue protections remain. HOST10 validates source policy. Hour08 completed source/drain/closure; sustainable real-time remains unqualified. Writer HOST14 preserved canonical bytes/digests and lowered
traced preparation peak 1,868,863 to 961,646 bytes; it is a host allocation case.

Storage totals are capacity-driven, while queues, files, payloads and source
copies remain bounded. The reserve+8MiB writable-SQLite edge can still block
cleanup before unlink; ASR ledger planning needs 16 MiB above its reserve.
See [technical notes](CORE_REPAIR_TECHNICAL_NOTES.md) and the final
[selected source map](core_repair_20261006/current_build35/SOURCE_MAP.md).



Hour08 sampled whole-unit peak PSS780,467,200B; worker VmPeak959,758,336B. No throttle flag was sampled. Memory grew: no steady-state, leak-free, cooling/noisy-room/name-quality proof follows. The4GB/8GB possibilities are not measured upgrade results.

## Historical pre-core RAM guide and measurements

Original bytes follow. "Current" and 4 GB/8 GB proposals below retain their stated
historical scope, not a new33 acceptance or authorization to widen guards.

# RAM and processing limits on the CM5

The device used for this iteration has **2 GB of physical RAM**. Results below
are measurements on that device. Statements about 4 GB and 8 GB are capacity
estimates, not measurements of larger devices. This guide is updated with the
native results; source implementation alone is not a memory qualification.

## What the measurements currently establish

| Workload | Observed process memory | Available system RAM | Finding |
|---|---|---|---|
| Isolated Chunk52, 44.6954 s matched input | Maximum sampled RSS 190,349,312 B / 181.5 MiB | Minimum 1,480,802,304 B / 1.38 GiB | Component RTF 1.08129; mature calls about 1.55. Compute is the observed limit, not physical RAM exhaustion. |
| Isolated Chunk52, explicit two-thread build, same input | Sampled RSS 190,808,064 B / 182.0 MiB; cached PSS 184,850,432 B; virtual size 361,807,872 B; swap zero | Minimum 1,470,562,304 B | Component RTF 0.55433; all 4,470 x 8 probabilities exactly unchanged. Improved CPU scheduling, essentially unchanged observed RAM; sustained whole-application behavior remains pending. The separate completed component hour is reported below. |
| Isolated compact 3.04 s candidate | Sampled RSS 169,885,696 B / 162.0 MiB; cached PSS 164,120,576 B; virtual size 344,391,680 B; swap zero | Minimum 1,500,643,328 B | Component RTF 0.85681 on this short input. Changed context, with quality and sustained operation still unqualified. |
| Continuous 3,600 s Chunk52, two graph threads | Later RSS plateau 174,637,056 B / 166.5 MiB; sampled EOF maximum 175,210,496 B; separate ru_maxrss 176,357,376 B; swap zero | Minimum 1,481,637,888 B | Completed all 360,001 frames, component RTF 0.88445. Temperature reached 85.35 degrees C and late RTF approached 0.94. Physical RAM was not the observed limit. |
| Official Low Latency | Failed at bounded processing deadline, with prefix retained | No demonstrated memory exhaustion | Last measured graph computation 6,988.73 ms for a 720 ms chunk; input copy 0.18 ms. More RAM alone does not remove this compute cost. |
| Combined saved-input Sherpa/PnC + ReDimNet + Delayed diarizer, failed 26.74 s prefix | Model-load RSS 455,671,808 B / PSS 446,701,568 B; later process RSS high-water 544,227,328 B / 519.0 MiB; virtual high-water 718,536,704 B; swap zero | 1,224,671,232 B available after model acquisition | Restored allocator settings allowed model loading under the unchanged 768 MiB AS ceiling. The run failed on event serialization/storage bounds, not on a demonstrated physical RAM shortage. These are current-process observations, not an aggregate GUI/live peak. |
| Changed combined saved-input pipeline04, complete 44.6954 s | Worker sampled RSS 556,761,088 B / 531.0 MiB; PSS 547,734,528 B; virtual size 730,234,880 B / 696.4 MiB; VM high-water 730,447,872 B | Minimum 1,124,483,072 B / 1.05 GiB | Full source, saved audio and cleanup passed under the same 768 MiB AS limit. This measured worker fits; it has less virtual headroom than its physical-RAM availability suggests. Live child/GUI and long-term growth are separate checks. |
| Build08 GUI live300, CurrentDelayed/ReDimNet, followed by full saved replay | Live worker sampled RSS 500,858,880 B / PSS 490,336,256 B / VM 659,587,072 B; replay RSS 498,057,216 B. Partial aggregate replay samples reached RSS 539,049,984 B / PSS 518,532,096 B | Live minimum 1,148,338,176 B; replay minimum 1,225,031,680 B | Both complete 4,800,000-sample sessions and physical closure passed. The external aggregate trace started late and covers replay, so it is not a measured full live/source/GUI peak. Quiet capture made zero embedding and punctuation inference calls. |
| Build08 saved Pyannote/TitaNet + Sherpa/PnC, complete 44.6954 s | Worker sampled RSS 468,762,624 B / PSS 459,514,880 B / VM 626,655,232 B; VM high-water 634,437,632 B. Partial aggregate RSS 492,240,896 B / PSS 474,051,584 B | Worker-trace minimum 1,253,867,520 B; partial aggregate minimum 1,246,920,704 B | Complete source/EOF/closure passed under the unchanged 768 MiB AS limit. Backlog maximum 0.23 s; punctuation ran on three utterances. This remains a short saved-input measurement. |
| Optional second diarizer, failed first01 startup | Three child-active samples: aggregate RSS 427,720,704 B / PSS 406,160,384 B; child startup RSS 145,883,136 B / VM 262,012,928 B | Minimum 1,343,094,784 B | Child failed at 2,880 samples (0.18 s), zero returned frames, while the primary completed. This is failed startup-prefix evidence, not mature combined fit, throughput or an optional pass. |
| Build13 optional First02: saved Pyannote/TitaNet primary plus anonymous CurrentDelayed child, complete44.6954s | Whole-unit sampled RSS637,370,368 B / PSS615,421,952 B; primary VM689,324,032 B and child VM284,901,376 B; owned swap zero | Minimum1,211,170,816 B | Both consumers reached715,127 samples, child returned4,470 frames, zero dropped samples, complete EOF/model/owner closure and full mirror. Short combined feasibility on the current2GB device, not live300, sustained operation or production approval. |
| Build13 optional live Followup01: primary/raw300 complete, optional child degraded | Whole-unit sampled RSS 696,287,232 B / PSS 651,709,440 B; owned swap zero | Minimum 1,189,969,920 B | Primary and raw each completed 4,800,000 samples. The child stopped on the 30 s label-lag window after 676,800 samples/2,112 returned frames, with no child EOF. Primary backlog stayed at most 0.25 s, with zero drops and full closure. No physical-RAM failure or optional live correction pass is established. |
| Build14 Research07 sparse embedding + single-D1 late labels, full matched input | Worker sampled RSS 550,502,400 B / PSS 541,426,688 B; VMpeak 729,858,048 B; owned swap zero | Minimum 1,258,323,968 B | Complete715,127 samples and changed attribution path passed. All4,470 x8 native floats and final ASR matched baseline04; no whole-unit trace, quality evaluation or sustained pass. |
| Build14 optional Followup02 live300/window60, primary + anonymous continuous D1 | Sampled whole-unit RSS760,020,992 B / PSS700,768,256 B; child recorded VMpeak287,916,032 B; owned swap0 | Minimum1,178,828,800 B | All4.8M primary/raw/child samples and30,001 child frames completed; full physical/model closure. Primary backlog0.50s and child lag30.98s; child compute132.00s. Bounded experimental fit/function, zero optional corrections observed, no sustained or quality claim. |

The selected recording export is a separate non-model workload. Export01
failed importing storage under the128 MiB AS policy in the already running
supervisor; this does not establish physical RAM exhaustion. Fresh-child
export02 then failed a read-only/shared-lease contract, not a memory bound.
Export03 completed the142,926,668-byte ZIP with the fresh128 MiB child and an
exact156,186,885-byte file ceiling. Its terminal RSS/VmHWM were24,672 KiB,
VmSize33,296 KiB, VmPeak33,440 KiB and process swap0. Parent resource limits
were unchanged. These child readings must not be added to a noncontemporaneous
parent reading and called a measured aggregate peak. Full child/unit closure
and the112-member independent PC readback passed; later History04 also passed the actual History Export callback and normal Exit with no capture/models. Its frontend snapshot showed RSS29,456 KiB, VM46,896 KiB and swap0, not a measured whole-unit peak.

The first full-application hour attempt (`full-app-hour-02`) stopped on the
output-membership guard after about319 seconds. Its314 whole-unit prefix samples
reached RSS590,315,520 B/PSS573,756,416 B with minimum available RAM1,143,275,520 B
and temperature66.65 degrees C. It is not an hour pass or a demonstrated RAM
failure. Exact physical cgroup closure and the full file mirror passed; absent
worker final receipts mean logical/model cleanup is not claimed. The original
guard lacked path/link diagnostics, so an atomic-publication race remains a
plausible diagnosis rather than an established cause. The changed09 guard
retains bounded output and adds those diagnostics plus an exact publish-pair
check before the next trial.

Full-application hour04 is also a failed application attempt. Its completed
independent PC mirror contains786 regular files /651,313,592 bytes; the exact
native owner is gone and the cgroup is empty. Systemd recorded signal9, and
watchdog termination was reported. Worker RESULT, HOST_CLOSURE and
session_summary are absent, so successful full-input EOF, drain and logical/model
cleanup are not established. The mirror's COMPLETE describes the copied files,
not successful application completion. The stored57,359,280 samples represent
3584.955 s rather than3600 s; last worker source time was3584.695 s. Its4,228
health rows reached worker RSS616,251,392 B/PSS607,257,600 B and VM high-water
797,163,520 B versus the805,306,368 B AS guard, leaving only8,142,848 B of
virtual-space margin at that observed high-water. Whole-unit sampled RSS/PSS
maxima were643,776,512/627,185,664 B; available RAM stayed above1,210,351,616 B,
owned swap stayed zero and whole-unit temperature reached79.85°C. Backlog
peaked at27.553 s; mean diarizer-push rolling RTF was0.44984. Source time fell
behind wall time despite that component metric. These sampled observations do
not establish the exact termination mechanism, a leak, OOM or final EOF.
Evidence: `full-app-hour-04-monitor-01/MIRROR_COMPLETE.json`, its closed output,
and `audit-preparation/full-app-hour-review-39182a83d2134831814742c829683a09/REVIEW.json`.

The completed short native runs and component hour demonstrate useful physical
headroom on this2GB device within their stated scopes. That does not turn a
failed whole-application attempt into a fit/throughput pass or establish the
reason it ended. No4/8GB measurement exists and no speedup is promised from more
capacity alone; CPU, thermal, virtual-space, queue and storage limits remain
separate. Build13 First02 and build14 First03 have short saved combined feasibility passes. Build14 Followup02 then completed live300 with the explicit60-second window and received an exact experimental evidence review; production16 now selects its exact source300/load120/drain60/backlog30/cleanup60 policy through reviewed GUI reuse. The actual production16 idle check verified that control path with zero Start/model/capture, so it adds no new RAM measurement. The failed application hour remains failed. The late-only build14 subsequently passed the short Research07 attribution path. Production16 has 247 permitted selections, not 247 measured modes; sustained whole-application operation remains unqualified.

The first combined-pipeline qualification failed before model initialization on
a file-size guard calculation. That is **not a RAM failure**. The first raw
sample-boundary failure is also not a RAM failure. A later raw boundary check
passed but found about 1.9 s of lag from the unbatched path over 5 s; increasing
the audio queue would hide latency, not fix throughput.

The second combined-pipeline attempt failed while loading the unchanged Sherpa
encoder with `std::bad_alloc`, inside the 768 MiB address-space envelope.
Preflight available RAM was 1,636,384,768 B; that is not a measurement of memory
at the instant of failure. The new launcher had omitted the retained v28
`MALLOC_ARENA_MAX=1`, `MALLOC_MMAP_THRESHOLD_=131072` and
`MALLOC_TRIM_THRESHOLD_=131072` environment settings. The next attempt restored
those before process startup and successfully loaded the unchanged models with
the same AS limit. Its after-load virtual size was 603,553,792 B and available
system RAM was 1,224,671,232 B. This supports the allocator configuration diagnosis;
the failed earlier attempt has no equivalent instantaneous trace proving its
exact allocation path. The changed attempt later stopped on an explicit event
record/queue/disk bound after 427,840 source samples. That storage failure is
preserved separately. No AS limit was raised, and these results do not establish
a need for larger hardware.

The separate Chunk52 `ru_maxrss` observation was 188,710,912 B. It remains
separate from the sampled RSS maximum above. Neither is a continuously sampled
peak for every process in the application. Detailed receipts and scope are in
[NATIVE_RESULTS.md](NATIVE_RESULTS.md).

## Distinguishing the limits

The build08 GUI test reached the policy boundary without an injected Stop,
saved exactly 4,800,000 raw and processed samples, replayed the whole kept
recording and discarded the replay. Source lag peaked at 0.327 s, with no
dropped frames and route restoration confirmed. Live and replay worker backlog
peaked near 21.2 s, including CurrentDelayed's input context; final source/ASR/
speaker cursors reached 300 s. Paced source-to-EOF elapsed times were 310.08 s
and 310.17 s. These include pacing and drain and are not compute-only RTFs.
Minute live-worker RSS maxima rose from 494,632,960 to 500,858,880 B over the
five-minute window. This is bounded completion over that window, not evidence
of an hour-long flat memory trend or speech/identity accuracy.

The external memory trace sampled only the later two-process replay phase.
Owned-process swap was zero, while system-wide swap usage ranged from
94,371,840 to 119,537,664 B; these are distinct observations. The TitaNet
short-run samples likewise showed zero owned-process swap and 118,489,088 B
system swap usage. A late sampled maximum cannot certify an earlier live peak.
The 768 MiB AS ceiling is 805,306,368 bytes of virtual address space, rather
than a resident-RAM budget; the measured RSS/PSS and available RAM are reported
separately. The GUI's quiet input exercised model residency and capture/storage,
but did not exercise representative embedding or punctuation inference load.
The saved TitaNet run did exercise three punctuation utterances, with zero
inference failures and two terminal fallbacks.

Private numeric reviews: `audit-preparation/gui-resource-review-0aaa7708b56e489da324a1c23ad6a286/REVIEW.json`
and `audit-preparation/gui-resource-review-ee00881493764163879c58cc5b96b77b/REVIEW.json`.
The read-only procedure is documented in [README_GUI_RESOURCES.md](README_GUI_RESOURCES.md).

The one-hour component run is especially relevant to the RAM purchase decision.
It kept one continuous model state and completed all 57,600,000 input samples.
Its ten-minute RTF values, including EOF in the last bin, were 0.781, 0.817,
0.898, 0.926, 0.941 and 0.944. Mean input backlog increased from 1.36 to
1.92 seconds; it remained below four seconds but did not demonstrate a flat
latency trend. Later memory was nearly flat while CPU temperature rose to
85.35 degrees C. This fails the preferred 0.8–0.85 headroom target for the
whole hour, despite average component RTF below one.

The subsequent firmware snapshot returned `throttled=0xe0000`: frequency
capping, throttling and the soft temperature limit had occurred during this
boot, with no current-state bits set at inspection. This snapshot does not
locate those events within the run. The temperature/timing trend is consistent
with thermal constraints; it is not a controlled cooling experiment.
See the [official Raspberry Pi bit definitions](https://www.raspberrypi.com/documentation/computers/os.html#get_throttled).
Cooling and shared CPU load therefore deserve attention before attributing
this slowdown to insufficient RAM. Neither more RAM nor this component pass
establishes whole-application sustainability.

* **Physical pressure:** falling system available RAM, growing RSS/PSS, swap,
  allocation failures and possible kernel OOM evidence. Report all processes,
  model residency, shared pages and the OS reserve.
* **Process address-space limit:** the current ordinary model envelope is
  768 MiB of virtual address space. Virtual mappings, shared libraries, stacks
  and allocations count. A failure at this limit with abundant available RAM
  does not prove a 2 GB hardware limitation. Installing more RAM does not change
  this policy; any new limit needs an explicit measured admission.
* **CPU throughput:** stable memory plus processing RTF above one and growing
  backlog. Extra RAM does not make an unchanged graph finish faster. Profile
  computation, thread contention and repeated context work first.
* **Storage/transport latency:** durable writes, acknowledgement frequency,
  slow storage or source transfer can cause backlog even when the model fits.
  Batch bounded writes while retaining sample clocks and durability; do not
  replace disk spooling with an hour of in-memory audio.
* **Long-term growth:** a five-minute peak cannot establish hour-long stability.
  Inspect rolling RSS/PSS, queue depth, file growth and latency throughout the
  soak, followed by final drain and process/lease closure.

RTF is processing wall time divided by represented audio duration. A component
RTF below one leaves some compute headroom, but is not proof that ASR, embeddings,
GUI, motion and capture together are sustainable.

The D1 adapter also reserves a reusable probability scratch array sized by the
**admitted maximum duration**, not the currently received audio. In exact13
[nemotron_binding.py](nemotron_binding.py), `expected_frames`, the
`_live_workspace` allocation and `copy_new_probabilities` give, for positive
maximum duration `T` seconds at16kHz:
`scratch_bytes = (floor(16000*T/160)+1) * 8 * 4`.
This is960,032 B for300s,11,520,032 B for3600s, and276,480,032 B for86400s,
per D1 workspace. `np.empty` reserves this float32 array; these calculated bytes
are not an observed RSS/PSS increase or proof that every page is resident.
It is probability scratch space, not retained all-audio RAM. The C ABI still
copies the full retained probability interval (`count-base`), then the adapter
copies only newly emitted rows into their immutable output. Reusing the array
does not create a range-copy API or prove bounded native history, low copy cost,
or successful long-duration memory fit. Existing finite duration/AS guards and
actual whole-unit measurements remain necessary.
First02's60 whole-unit samples, including52 combined-resource samples,
establish sampled residency for this exact short primary/child pair on2GB.
The maximum temperature was61.15 degrees C. Its paced required-consumer wall
time was56.236s; the child separately reported18.290s compute. The paced
wall time includes waiting and drain and is not a model-compute RTF. No
speaker-label quality, DER, live300 or sustained approval follows from this run.

The saved100ms path made447 durable append calls, with zero append failures:
5.268s total append wall time,0.223s maximum source-wall lag and0.012s
terminal lag. Append timing includes locks, durability and observers, not just
storage CPU. This short result does not establish that the hour04 slowdown is
fixed. Primary and child virtual sizes are separate per-process observations;
do not add them and call the result physical RAM. The768MiB per-model-process
AS guard still applies independently of available physical RAM.
Evidence: presets-preparation-first02-review-ea863b07ba804b90bf422003f60fc556/REVIEW.json.

The later live Followup01 separates resident fit from optional usefulness.
Its 298 whole-unit samples reached RSS 696,287,232 B (664.03125 MiB) and
PSS 651,709,440 B; system available RAM stayed above 1,189,969,920 B and owned
swap stayed zero. Temperature reached 63.35 degrees C. The primary completed
all 300 seconds and four-channel raw matched that clock, with routes restored
and all owners closed. The optional child was terminated after its label lag
no longer fitted the 30-second revision window. It did not reach EOF or show
a correction success; no physical-memory failure was reported. The displayed
child lag can continue increasing after its shutdown and must not be treated
as an actively growing native queue. A wider-window experiment needs new
explicit evidence; it cannot retrospectively pass the 30-second run.
Evidence: presets-preparation-followup01-final-review-b4e28b6b9c9949419b4fde83448163d7/REVIEW.json.

## What 4 GB or 8 GB might buy

| Capacity | Possible benefit to investigate | What it does not establish |
|---|---|---|
| 2 GB, current hardware | Establish the minimum deployable combination with bounded queues, disk spooling and an OS reserve | No assumption that every experimental pair of models fits |
| 4 GB | More headroom for simultaneous ASR/embedding/diarizer residency, reduced memory pressure if measured, and more room for larger or additional measured model combinations | No automatic RTF improvement for the measured CPU-bound diarizer; no removal of software limits |
| 8 GB | More development and multi-model residency headroom, larger deliberately chosen caches or additional concurrent tools if justified | No promised speaker-quality gain or real-time operation; no need to keep long recordings in RAM |

A hardware upgrade is worth recommending when a required useful combination
is repeatedly blocked by measured physical-memory pressure, or when avoiding
model eviction/reloading produces a measured usability improvement. Report the
benefit in seconds, peak memory and stable queue behavior. Do not infer a
"drastic speedup" solely from a larger RAM capacity.

The two-thread Chunk52 experiment is a concrete example: changing the native
graph thread argument from one to two reduced compute wall time by about 48.7%
on the same existing 2 GB CM5 without changing the model, geometry or output
probabilities. It used both admitted CPU cores while computing. Its total
workload still competes with ASR and embeddings, so this short isolated result
does not qualify the complete application or prove lower energy per session.
The exact private review is `chunk52-threads2-01-review-01/REVIEW.json` under
the evidence root in NATIVE_RESULTS; larger-RAM hardware was not involved.

## Measurement and operating policy

Native component receipts include RSS, virtual size, swap, cached PSS, system
available RAM, CPU time, temperature where available and queue/backlog. PSS is
read at most once per second; receipt ages make the cache explicit. Whole-unit
measurement must include child processes and distinguish shared pages; summing
RSS can double-count shared libraries. The normal initial available-memory
floor is 850 MiB and runtime stop floor is 192 MiB. These guards and the finite
CPU/time/storage allocations remain active.

The new source batching path is designed for at most about 100 ms of extra
audio grouping, not a growing backlog. Existing input rings, NumPy libraries,
models and the GUI still count separately. Raw storage is reserved independently
of processed audio. Current qualified packed-route format is four-channel
16 kHz signed PCM32, not four-channel 48 kHz PCM16.

For reproducible commands, inputs and outputs see
[README_NATIVE_BENCHMARK.md](README_NATIVE_BENCHMARK.md),
[README_QUALIFICATION_DISPATCH.md](README_QUALIFICATION_DISPATCH.md) and
[README_SOAK_DISPATCH.md](README_SOAK_DISPATCH.md). Those include PowerShell,
Command Prompt and Anaconda usage. Never launch a second native benchmark beside
a recording merely to collect a memory number.
