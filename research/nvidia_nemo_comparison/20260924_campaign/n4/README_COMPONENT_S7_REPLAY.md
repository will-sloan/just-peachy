# Modeled causal replay through the actual S7 policy

`component_s7_replay.py` merges the reconstructed ASR and D0 commands and runs
the frozen application's real S7 observed-eligibility scheduler, bounded worker,
anonymous tracker, publication-expiry function and timestamped caption spans.
The purpose is to implement and check this part of joint integration without
silently substituting the older batch policy. This first API supports Balanced
anonymous D0/E0 only. It does not implement D1's separate native activity/name/
span-revision path, named galleries or D0/E1 calibration.

Inputs are the complete, previously verified commands from
`component_commands.py`, exact source duration, original Balanced anonymous
profile, fresh scene identity and optional actual final formatting records.
No reference transcript, activity truth, actor identity or evaluator label
enters the policy. The caller must verify the component source/model/cache
bindings; this in-memory API is not a replacement for the component reviewers.

The clock contract is explicit:

- Each lane retains the captured isolated component FIFO availability and
  original source-progress watermarks. Equal-time ties use speaker, ASR, then
  formatting, preserving every lane's own command order.
- The source epoch is zero. The real bounded policy worker drains after each
  command while the injected clock stays fixed. Modeled policy queue, policy
  execution and publication delays are zero. Actual host execution costs are
  diagnostic and do not enter that chronology. Independent lane costs omit
  contention; this is not an actual complete-stack timing measurement.
- Infinite closure is admitted only after the real duration has been delivered.
  In particular D0's unchanged last-ready argument can precede its unanalyzed
  partial tail. Both that original argument and the separate delivery constraint
  remain recorded. No prediction timestamp is clamped or rewritten.
- Actual S7 eligibility and publication freshness run on the injected clock.
  Native fields containing `observed`, `monotonic`, or GUI freshness terminology
  remain under `MODELED_S7_REPLAY_NOT_OBSERVED_CONTROLLER_OR_WIDGET`. They do
  not become measurements because the frozen implementation named them so.
  Worker age fields mix native/injected epochs and are excluded from output.
- Independent raw text is consumed before policy admission. Actual token/span
  revision checks and exact-final formatting parents remain in force. The
  original simpler presentation helper is unchanged.

Output includes the modeled contract, exact execution census, native policy
records, caption-state/history snapshots and real worker completion counts.
Private output contains transcripts; never commit or upload it. The API always
reports zero integrated N4 acceptance cells, unavailable first-visible latency,
and false observed Controller/widget parity. A successful replay is development
evidence. Named/D1 integration, complete activity mapping, Controller parity,
full-bank scoring and actual paced/continuity/resource evaluation remain needed.

`test_component_s7_replay.py` tests the real frozen scheduler/worker without
models. It exercises strict watermark equality, evidence that expires while
waiting for the other lane, publication expiry, source-tail closure, older
caption rejection, full-word preservation, formatting parents, deterministic
ties, invalid/reference inputs and worker failure cleanup. One initial fixture
expected the wrong rejection-counter name; inspection confirmed the actual
span/older-word rejection and the assertion was corrected. No production
behavior was changed to satisfy the test.

`probe_component_s7.py` reuses exactly the eight accepted ASR smoke cells and
their two matching D0/E0 bank cells. It verifies the completed review bindings,
both admissions, every source-receipt file, exact paired waveform/profile,
compressed and full expanded event hashes/CRC, and raw/final census. ONNX model
construction is forbidden. It executes eight modeled joint development replays,
with fresh state per composition/tap, and writes private lossless JSON gzip
files plus `RESULT.json`. Each output is round-trip verified and limited to
32 MiB expanded; reserve 256 MiB total beneath the existing shared allowance.
C/G free-space floors plus that reservation are checked. Existing output
directories are refused; exceptions leave `FAILED.json` and all prior evidence.
Only a compact redacted receipt belongs in the repository.

PowerShell (tests use CPU14; the probe pins itself there, below normal):

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local\n4'
& $jpPython -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_component_s7_replay.py','-v']; runpy.run_module('unittest',run_name='__main__')" $jpCode
& $jpPython -B "$jpCode\probe_component_s7.py" --asr-review "$jpLocal\asr-smoke-review-v1\REVIEW.json" --d0-review "$jpLocal\d0-bank-review-v1\REVIEW.json" --output "$jpLocal\component-s7-probe-v1"
```

Command Prompt / Anaconda Prompt (explicit application interpreter; no Conda
environment mutation):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local\n4"
"%JP_PY%" -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_component_s7_replay.py','-v']; runpy.run_module('unittest',run_name='__main__')" "%JP_CODE%"
"%JP_PY%" -B "%JP_CODE%\probe_component_s7.py" --asr-review "%JP_LOCAL%\asr-smoke-review-v1\REVIEW.json" --d0-review "%JP_LOCAL%\d0-bank-review-v1\REVIEW.json" --output "%JP_LOCAL%\component-s7-probe-v1"
```

Tests select the frozen `local/releases/n4-catalog-v3/prototype` by default.
`JP_N4_SOURCE` is only for a verified equivalent test source. The probe gets its
source exclusively from the verified ASR admission. No microphone, playback,
desktop window, network/Pi contact, model download or inference is performed.
