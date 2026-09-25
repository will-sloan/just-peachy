# Review the actual application ASR smoke

`review_asr_components.py` validates the eight completed component cells from
`asr_bank_components.py`: A0/A1/A2/A3, first admitted scene, both taps. It loads
no inference model, touches no devices and changes no producer evidence. A
terminal result with an exited exact coordinator is mandatory. It does not
admit a full-bank run, score accuracy, validate GUI timing or complete N4.

Inputs: private terminal run root, its immutable admission and component
contract, source/model/runtime hashes, both waveform hashes, four variant
indexes, all eight results and complete gzip logs. Checks include exact cache
keys, source/gain/reset/profile/CPU policy, every actual journal dispatch and
partial tail, one complete flush, all raw observations/finals, native final text
preservation, separate final-only formatting and its explicitly modeled FIFO.
Truncated gzip or changed compressed/expanded bytes fail. Native punctuation
cannot be replaced; raw text cannot be silently replaced by P0's formatted text.
Actual P0 fallback statuses remain counted, not suppressed as successful quality.

Output: a fresh directory with `REVIEW.json`, containing aggregate counts and
bound private evidence paths/hashes but no utterance text. Review this small
receipt before copying it into Git. `PASS_ASR_COMPONENT_SMOKE` means these eight
component cells passed integrity checks only. Formatting accuracy/lexical
preservation, integrated event parity and live/widget timing remain separate.
Failures never become an empty successful hypothesis or disappear from counts.

PowerShell, after the model/coordinator have exited:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local\n4'
& $jpPython -B "$jpCode\review_asr_components.py" --run "$jpLocal\asr-smoke-v1" --output "$jpLocal\asr-smoke-review-v1"
```

Command Prompt / Anaconda Prompt:

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local\n4"
"%JP_PY%" -B "%JP_CODE%\review_asr_components.py" --run "%JP_LOCAL%\asr-smoke-v1" --output "%JP_LOCAL%\asr-smoke-review-v1"
```

The command restricts itself to CPU14 with one BLAS thread and below-normal
priority. Run from the exact application Python, whose version/package receipts
are checked. All original ASR events/transcripts remain private and unchanged.

`test_review_asr_components.py` uses the actual frozen loop fixtures from
`test_asr_lane_components.py` with stub models. It verifies all four schemas,
tail and final omission rejection, raw/formatting separation, native punctuation,
gzip truncation, false completion and impossible clocks. It loads no models or
saved recordings and performs no capture/synthesis.

```powershell
& $jpPython -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_review_asr_components.py','-v']; runpy.run_module('unittest',run_name='__main__')" $jpCode
```

```bat
"%JP_PY%" -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_review_asr_components.py','-v']; runpy.run_module('unittest',run_name='__main__')" "%JP_CODE%"
```
