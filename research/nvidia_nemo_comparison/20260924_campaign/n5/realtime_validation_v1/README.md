# Held real-time and selective-diarization experiments

Purpose: retain 34 explicit methods for staged testing of caption-first ASR,
parallel speaker processing and reduced work during silence. Each is specified
for A0/D1/E0 (Sherpa/Nemotron diarization/ReDimNet) and A2/D1/E0 (Nemotron
English ASR/Nemotron diarization/ReDimNet). This gives 68 possible composition
instances, **not 68 executed tests or an instruction to launch a full sweep**.
TitaNet is retired. The separately qualified anonymous E0-bypass preview is an
optional control; it cannot establish persistent personal naming.

Inputs: `EXPERIMENTS.json`, original N1-N5 specifications in Downloads, current
accepted component bindings, exact saved-source manifests and prior aggregate
workload reports. Outputs now are this retained catalogue and the next-step
protocol. Future implementations must produce a new admission, exact code and
asset hashes, immutable observations, reviewed metrics and closure receipts.
No new optimized backend or production silence gate is implemented by a JSON
entry. Each entry starts `SPECIFIED_NOT_EXECUTED`; preserve this original file
and record later implementation/results separately with its catalogue hash.

## Methods to carry into implementation and real-world validation

| IDs | Methods | What the comparison isolates |
|---|---|---|
| P01-P08 | Unpaced, 1x, half-rate, 2x overload, jitter, burst delivery, 30-minute and 60-minute endurance | Throughput versus actual arrival-time latency, burst recovery and sustained queue growth |
| W01-W05 | Serial control, isolated ASR/D1 processes, on-demand E0, two overlapping D1 workers, independent-session pool | Publication independence, IPC/RAM costs, identity reconciliation and true scope of parallelism |
| G01-G11 | Exact zeros, two energy thresholds, adaptive energy, lightweight VAD, VAD/energy union, two ASR deadlines, three-cue union, ASR-only negative control, later XVF-positive cue | Work avoided versus quiet/short/overlap speech lost, with cue cost included |
| C01-C04 | Native 1.04s, 0.64s, 0.32s and 30.4s buffer profiles | Supported internal chunk geometry, label delay and compute; larger host pushes alone are insufficient |
| O01-O03 | Bounded FIFO, recent-first epoch restart, separate uncertain-span revisit | Explicit degradation and recovery without indefinitely growing latency |
| S01-S03 | Shadow decisions, speech-island resets, mapped silence removal | Cue safety first, then speaker-state and original-timeline correctness |

The default comparison is 1x saved-file arrival with existing separate ASR and
one ordered stateful D1 thread, continuous input, nominal chunking and bounded
FIFO. The serial row is a diagnostic control. Preserve equal total CPU/RAM
budgets when comparing workers; count every native math thread, not just Python
processes. A pool over independent sessions is not faster processing of one
conversation. Two D1 models on overlapping windows add duplicated inference,
state reconciliation and RAM; test this late, only if an admitted target budget
fits. Never split a single stateful cache into out-of-order parallel pushes.

The existing report `../CM5_PARALLEL_DIARIZATION_FEASIBILITY_20260928.md` and
its two aggregate JSON receipts remain the measured/model-free baseline. Their
linear savings are optimistic feasibility estimates. A shadow gate runs all
audio and logs proposed skips, so it does not itself save inference work.

## Safe state and fusion contract

ASR publishes captions independently with stable utterance/revision IDs and a
Pending/Unknown label. Speaker results update labels against source sample
intervals; gate decision delay never holds back caption publication. Keep source
time, actual availability time and model-compacted time distinct. Do not invent
word alignment from coarse ASR timestamps or average unrelated confidence types.

No ASR tokens is not proof of silence. ASR is positive support only in deployable
candidates. Quiet, uncertain, missing or stale cues retain audio. Exact digital
zeros are a narrow control; acoustic silence normally contains noise. Energy
alone is not a speech classifier. VAD, pre-roll, hangover, model warm-up and
context replay all have costs. Replacing samples with zeros still runs inference.

Applied skipping must first pass the matched shadow comparison. Speech-island
resets need new track epochs and identity reacquisition. Concatenated speech
needs a reversible mapping of every model interval to original source intervals;
spans crossing deleted gaps remain split or uncertain. Validate returning
speakers, cache ageing, overlap and final flush. Only use native fast-forward
if the pinned runtime actually supports it and its semantics are tested.

Bound queued samples, estimated outstanding compute and pending-label age
separately. Log every dropped/unanalyzed interval. Recent-first recovery must
declare discontinuity rather than carry an old speaker name forward. Selective
retrospective work uses an independent context/state job; it cannot reorder
the primary D1 stream. GUI labels must show uncertain or unavailable evidence.

## Staged execution and evidence

1. Clear existing correctness and shutdown blockers before benchmarking new
   production candidates. The current bounded native run is
   `local/n5/native-stream-cpu-v2`; follow its terminal evidence and independent
   review. Do not duplicate it or change its source while active. N4's actual
   application panel remains partial; working previews are narrower evidence.
2. Audit the 1x source clock and final remainder. Schedule chunk availability
   against a monotonic clock, never relative sleeps that accumulate drift.
   Log actual release, ASR availability, model start/end and publication times.
   A delayed batch is not permission to release future audio early. No microphone
   is needed: consume existing saved audio without playback.
3. Use a small declared smoke set first, then the eligible full saved bank for
   shadow decisions. Freeze thresholds before evaluating held-out recordings.
   Gate decisions cannot read truth, final transcripts from the future or global
   file statistics. Estimated activity labels and incomplete ambient references
   must retain their stated scoring limitations.
4. First candidates: P01/P02 controls, S01 shadow, G01/G02/G05-G08,
   W02/W03, C01/C02 and O01. Build and test one change at a time. Combine only
   independently qualified choices, then compare the combination against the
   same ungated composition. No combinatorial sweep is automatically admitted.
5. Applied skip methods S02/S03 and aggressive scheduling require extra state,
   timestamp, overlap and missing-evidence checks. G10 remains a negative
   control and is never selected for production alone. G11 waits for actual
   device/firmware mapping and timestamped XVF observations after reconnection.
6. Reserve a separate real-world held-out set. Cover dense continuous speech,
   long pauses and returning speakers, distant/quiet speech, brief replies,
   overlap, music/noise/babble, overload and recovery. Repetition of existing
   clips may test endurance, but is not new independent accuracy evidence.
   Declare clip joins and expected speaker epochs; do not silently reinterpret
   unrelated recordings as one naturally continuous meeting.
7. After actual Pi reconnection, verify install/model hashes and short saved-file
   operation before 30/60-minute finalist runs. Measure target RAM, clocks,
   temperatures, throttling and CPU contention. Emulation timings are not Pi
   performance. Live capture/enrollment needs the user's later authorization.

For every result report WER/deletions, DER with explicit collar and overlap
policy, speaker-attributed/cpWER where references support it, false names,
Unknown/pending fraction, quiet/short/overlap speech lost, caption and speaker
latency p50/p95/p99, corrections, inference calls, effective RTF, all gate/IPC/
fusion/context overhead, backlog slope/max, tail drain and total peak RSS.
Record source duration and wall time including waits separately from model
service time. Empty controls must expose false activity, not disappear from
the aggregate. Paired taps share scenarios; do not count them as independent
speakers or independent experimental replications.

Keep original N1-N5 quality/latency gates. Preregister any additional numeric
quality-loss/latency/headroom margin before running a comparison. Do not choose
a tolerance after seeing a failure. A real-time claim needs sustained throughput
with usable label delays and non-growing backlog under the admitted resource
budget; merely displaying fast captions or truncating pending work is insufficient.
Release acceptance still requires the complete relevant N4/N5 checks.

## Inspection commands

These commands inspect the catalogue only; they do not launch models or claim
that all proposed methods already have runners. Each new implementation must
have its own updated README with actual commands, inputs, outputs and admission.

PowerShell:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\realtime_validation_v1
$jpPlan = Get-Content -Raw .\EXPERIMENTS.json | ConvertFrom-Json
$jpPlan.experiments | Select-Object id,title,priority,status | Format-Table -AutoSize
$jpPlan.experiments | Where-Object priority -eq 1 | ConvertTo-Json -Depth 8
```

CMD / Anaconda Prompt, using the existing pinned interpreter:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\realtime_validation_v1
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%JP_PY%" -B -m json.tool EXPERIMENTS.json
```

Current Windows admission stays two logical CPUs total, GPU off, C: >=50 GiB
and G: >=75 GiB free. Do not increase limits to fit a worker experiment. Actual
Pi allocation requires fresh measurement/admission. The hourly follow-up carries
this catalogue and the previous changes, prioritizes blockers and qualified
paths, and keeps quiet when unchanged. It must preserve the fixed packaging
reserve (2026-09-28 02:48:19 UTC) and deadline (2026-09-28 14:48:19 UTC).
Unfinished experiments remain explicitly held in the final handoff; this user
request does not extend the campaign or authorize training/device access now.
