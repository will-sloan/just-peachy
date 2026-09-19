# Exact S6D width-score admission

Purpose: materialize the single root-reviewed offline scorer queue from exact hash-bound proposals and the completed3,840-cell prediction index. This creates data authority only; it does not start a scorer, model, or device. It preserves the original72-hour deadline,45-minute reserve, C50/G75GiB floors and40GiB payload policy.

Inputs: the immutable `reports/S6D/20260913T195357Z/runner/width_score_queue_preparation_v1` proposals, independent matrix/source reviews, actual prediction index and pinned scorer environment. The root has reviewed this specific queue; this helper is not a general authority generator. Outputs: new `runner/width_score_queue_v1/ROOT_SCORER_ADMISSION_V1.json`, `QUEUE.json`, `APPROVAL.json` and `ROOT_QUEUE_REVIEW.json`. Existing directories or scoring output cause refusal; never remove prior evidence to rerun.

PowerShell (Python standard library; no activation or installation):

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$sim\scripts\s6d_width_score_admit_v1.py"
```

Anaconda Prompt / Windows CMD:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6d_width_score_admit_v1.py"
```

Next, the root runs the existing reviewed supervisor with `--validate-only` and exact queue/approval hashes, then launches that same literal command with owned keepawake. See the generated queue folder's `README_RUN.md` for those actual commands and launch receipt. The child must use the pinned `staging/s5_text_metrics/analysis_env/Scripts/python.exe`; never substitute the Edge environment for MeetEval scoring. Inspect semantic scoring and supervisor closure, not only process exit. This queue does not complete the overall S6D study.
