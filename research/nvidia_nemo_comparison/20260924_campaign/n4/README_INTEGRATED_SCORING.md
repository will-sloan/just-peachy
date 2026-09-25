# Score sealed N4 method predictions without changing inference

Purpose: `integrated_scoring_adapter.py` converts the actual saved publication
and Controller outputs to the existing pinned evaluator contract. It rejoins
raw fragments in token order and requires exact agreement with both caption
state and the Controller's raw rows. Missing, duplicated, hidden, overlapping
or changed fragments fail validation. Numeric tracker zero is retained; Unknown
is used only for a missing track. Raw ASR words always remain primary.

Inputs are verified publication/projection gzip bindings, the matching sealed
speaker-component events and the original audio-only job. The evaluator receives
the frozen Q reference only after conversion/prediction closure. This adapter
imports no application, neural model, microphone or GUI code. It runs in the
existing isolated metric environment, not the application's environment.

Outputs are lexical and speaker-stream edit counts, appropriate activity scores,
formatting word-preservation diagnostics and explicit unavailable statuses.
MeetEval 0.4.3 and pyannote.metrics 4.1 remain unchanged. Primary WER is only for
complete nonoverlap references. Overlap uses established cp/MIMO-WER; incomplete
ambient references remain target-only diagnostics. Empty controls report word
insertions per minute. A successful empty hypothesis counts missed words;
failed/not-tested execution retains unavailable WER and its reference denominator.

D1 uses actual eight native slot probabilities at the frozen .5 threshold,
including simultaneous speakers. Frames must be contiguous, finite and bound
to the same session. Support is intersected with audio actually delivered to
the model; the original native timestamps are retained and excluded overhang
is reported. D0's binary masks and sparse embedding tracks do not constitute a
global speaker timeline: D0 DER/JER remains unavailable. No reference-fitted
alignment, invented speaker activity or phonetic timing is introduced.

Formatting diagnostics compare canonical display words with actual raw ASR
words. They measure lexical preservation, not punctuation accuracy without
valid gold. The all-Unknown and all-one-name speaker-stream controls deliberately
produce the same permutation-invariant scores; neither demonstrates successful
naming. Actual first-visible/naming/resource metrics remain unavailable for
modeled method replays. No result grants N4 stage acceptance.

Both gzip readers verify compressed hashes, CRC, complete expanded SHA-256 and
a 32-MiB per-artifact bound. Detailed inputs and scoring output remain private.
The full-bank scoring driver, terminal admission and paired/stratified report
integration remain separate work; this library alone does not score the bank.

Tests cover token loss/corruption, numeric zero IDs, empty versus failed counts,
overlap/incomplete references, lexical formatting changes, native overlap/tail
support and corrupt frames. Two existing real baseline/A3-D1-E1 saved results
validate the conversion boundary; dictionary fixtures are not new audio.

PowerShell from the campaign worktree, CPU14 below normal (CPU4 stays available
to the sole neural worker):

```powershell
$jpMetrics='G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\env\Scripts\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
& $jpMetrics -B -c "import os; [os.environ.__setitem__(k,'1') for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')]; os.environ['CUDA_VISIBLE_DEVICES']=''; import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_integrated_scoring.py','-v']; runpy.run_module('unittest',run_name='__main__')" $jpCode
```

Command Prompt / Anaconda Prompt (use the existing isolated interpreter; do not
reinstall dependencies into an active environment):

```bat
set "JP_METRICS=G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\env\Scripts\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
"%JP_METRICS%" -B -c "import os; [os.environ.__setitem__(k,'1') for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')]; os.environ['CUDA_VISIBLE_DEVICES']=''; import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_integrated_scoring.py','-v']; runpy.run_module('unittest',run_name='__main__')" "%JP_CODE%"
```

Library sequence: read_artifact on both verified method bindings;
read_component_events on the sealed speaker cell; convert with the exact job
and diarizer; only then score_prediction with evaluator-only truth. Retain the
input bindings and use metrics.aggregate to pool integer errors/reference words
instead of averaging scene percentages. Keep independent mode/tap populations
and missing denominators distinct. README_METRICS.md binds installed dependencies.

`probe_integrated_scoring.py` validates the boundary on the existing 32
open-with-names method checks (16 tuples x both smoke taps) and all 19 closed A0
empty-output cases in anonymous mode. This is 51 development checks, not the
complete bank or independent scene coverage. It verifies every installed
evaluator code/native-file hash, the frozen truth/preparation and all saved
input/closure bindings before scoring. No predictor is called. Outputs are a
fresh private ADMISSION.json with exact owner identity, per-check SCORE.json,
then RESULT.json or FAILED.json. Detailed references and captions are not printed.

The probe uses CPU14, single-thread math, no GPU/models, a 128-MiB output bound,
C50/G75-GiB floors plus 256-MiB headroom, and the shared private allowance with
6-GiB pending reservations. A 12-minute budget is checked between cells; it is
not a hard interruption of an individual native library call. The production
bank scoring driver still requires separate per-cell timeout/ownership admission.

PowerShell (variables above):

```powershell
& $jpMetrics -B "$jpCode\probe_integrated_scoring.py" --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\integrated-scoring-probe-v1'
```

Command Prompt / Anaconda Prompt:

```bat
"%JP_METRICS%" -B "%JP_CODE%\probe_integrated_scoring.py" --output "G:\Just_Peachy_N1\20260924_campaign\local\n4\integrated-scoring-probe-v1"
```

Preserve previous output directories and all receipt-bound code. Do not run
this helper alongside controlled complete-stack timing/resource qualification.
