# Summarize accepted ASR component observations

Purpose: `summarize_asr_components.py` produces a small descriptive timing/memory
report from the completed, strictly reviewed 1,920-cell ASR bank. It performs no
inference, playback, GUI operation or hardware access. It is safe as a CPU14
model-free helper beside the admitted CPU4 D1 component worker; do not overlap
controlled paced application measurements.

Inputs: the passed full ASR REVIEW.json, its exact source-code/admission/terminal
bindings and all 1,920 bound cell results. The exact original ASR coordinator
must have exited. Every variant must contain the same 480 unique audio-only
scene/tap jobs, positive measured durations/RSS, one finite first model-constructor
duration and the documented CPU4/actual-inference flags. A partial review or
changed input is refused. Raw transcripts and labels never enter the report.

Outputs: a fresh private ADMISSION.json and REPORT.json. The report includes each
variant's frame/audio total, sum/median/maximum recorded cell times, ratio of
summed cell time to summed audio duration, first model-constructor duration and
maximum end-of-cell sampled process RSS. It binds all aggregate values to the
strict review. It uses the existing helper lock, payload reservation, original
deadline and drive floors. Preserve previous outputs; use a new directory.

These are accelerated stateful component measurements, not source-paced latency
or whole-application throughput. End-of-cell RSS can miss peaks, includes runtime
and cached state, and differs from USS/private commit and physical memory. The
model-constructor sample is not proof of a cold OS file cache. Diarization,
embeddings, gallery, GUI, workers, history/logging and OS reserve still require
complete-stack accounting. Accuracy, controlled-stack/CM5 qualification and
integrated N4 acceptance remain false; deployment tier remains UNKNOWN. Do not
interpret an individual ASR RSS below 1.5 GiB as a 2-GB device success.

PowerShell (the strict ASR review must already exist):

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpCode\summarize_asr_components.py" --review "$jpLocal\n4\asr-full-bank-review-v1\REVIEW.json" --output "$jpLocal\n4\asr-component-report-v1"
```

Command Prompt and Anaconda Prompt (use the exact pinned interpreter directly):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_CODE%\summarize_asr_components.py" --review "%JP_LOCAL%\n4\asr-full-bank-review-v1\REVIEW.json" --output "%JP_LOCAL%\n4\asr-component-report-v1"
```

The full review command and its source/event/tail/drain checks are documented in
[README_ASR_FULL_BANK.md](README_ASR_FULL_BANK.md). Current numerical execution and
acceptance order are documented in [REMAINING_EXECUTION.md](REMAINING_EXECUTION.md).
