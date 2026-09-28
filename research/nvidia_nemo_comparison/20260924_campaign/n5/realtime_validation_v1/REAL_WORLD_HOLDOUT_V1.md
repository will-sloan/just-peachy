# Real-world validation requirement: sparse synthetic audio

Purpose: record the user's September 28 clarification that long silence in
simulated scenes may exaggerate the practical benefit of selective diarization.
This addendum accompanies the immutable EXPERIMENTS.json catalogue and prior
workload reports. It changes interpretation and future validation requirements,
not their historical results or acceptance status.

Inputs: the 34-method catalogue, existing component/combination results and
workload analyses, and later independently held-out real-world recordings.
Outputs now: this protocol and links from the campaign handoff. No new audio,
inference, model optimization, training, enrollment or hardware access occurs.

## Interpreting existing results

The current synthetic bank contains substantial silence. Its low speech duty
cycle is a workload property, not a demonstrated real-world saving. Existing
proposed-gate retained fractions, speech-loss estimates and linear RTF/backlog
projections apply to that bank and its stated assumptions only. They do not
establish optimized neural inference speed, representative conversational
performance or native CM5 performance. Preserve the raw results and these
limitations together; do not turn projected savings into measured speedups.

Keep the ASR/diarizer/embedding combinations, supported diarizer profiles,
parallel-worker strategies and gating candidates available for later real-world
validation. Their status remains candidate, implemented, tested, or blocked as
supported by individual receipts. Holding a candidate does not qualify a failed
implementation or require an indiscriminate Cartesian sweep. TitaNet remains
retired from new development while its evidence is preserved.

## Matched real-world comparisons

1. Reserve recordings that were not used to choose thresholds, chunks, worker
   counts or fusion policies. Freeze those choices and acceptance tolerances
   before examining held-out outcomes. If results are used to retune a method,
   call that set development data and require a fresh final holdout.
2. Cover dense continuous speech, ordinary conversation with natural pauses,
   long pauses and returning speakers, quiet/distant or short speech, overlap,
   and background noise. Report the source speech duty cycle, pause-length
   distribution and longest continuous speech interval. Group results by
   workload; a favorable sparse-file average cannot mask dense-speech failure.
3. Compare each candidate with the same ungated ASR/diarizer/embedding
   composition on the same original audio, at the same total CPU/RAM budget.
   Keep all original source time, including natural silence, in 1x arrival
   schedules and end-to-end denominators. Do not pre-trim the test files and
   present a shorter or differently paced stream as representative real time.
4. Deliberately inserted/removed silence or repeated clips can test mechanisms,
   duty-cycle sensitivity and endurance. Label those as constructed diagnostic
   workloads, not independent natural-conversation accuracy evidence. Declare
   joins, source-to-model time mapping and speaker epochs.
5. Start with shadow gates, which feed every sample while recording proposed
   skips. Applied skips require separate actual model runs and checks for quiet,
   short and overlapping speech, false activity, returning-speaker continuity,
   source timestamps, state/cache behavior and final drain. Never treat missing
   ASR tokens or an uncertain cue as proof of silence.
6. Measure total elapsed and actual inference time, gate/IPC/context overhead,
   caption and speaker latency, corrections, backlog slope/max/drain, CPU and
   memory, plus native target clocks/thermals when available. A real-time claim
   needs usable latency and sustainable backlog on dense workloads as well as
   ordinary conversations. Caption-first behavior alone does not prove speaker
   processing keeps pace.

The intended held combinations remain A0 Sherpa + D1 Nemotron diarization + E0
ReDimNet and A2 Nemotron English ASR + D1 + E0, with the anonymous embedding
bypass as a separate control. Assess accuracy and latency for each supported
combination rather than assuming a gate's benefit transfers between them.

The Pi remains off for this campaign. Later real-world recordings and native
CM5 30/60-minute runs require their own input/admission records after
reconnection. No new capture or enrollment is authorized by this note. Keep
unfinished comparisons in the final handoff without extending the fixed reserve
or campaign deadline.

## Read this protocol

Documentation only; these commands do not run an experiment.

PowerShell:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\realtime_validation_v1
Get-Content .\REAL_WORLD_HOLDOUT_V1.md
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\realtime_validation_v1
type REAL_WORLD_HOLDOUT_V1.md
```
