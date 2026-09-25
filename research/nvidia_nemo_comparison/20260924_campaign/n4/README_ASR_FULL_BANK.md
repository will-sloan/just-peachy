# Full-bank ASR components after reviewed smoke

`asr_full_bank.py` prepares and supervises 1,920 actual ASR component cells:
A0/A1/A2/A3, each on the entire admitted 480-file bank. Its separate admission
requires the passed eight-cell smoke, verifies its source/runtime/assets and
complete event evidence, then independently rehashes every full-bank waveform.
The earlier smoke code, admission, results and failed attempts remain unchanged.
This is component collection; integrated N4 credit remains zero.

Inputs: the passed private smoke `REVIEW.json`, authoritative 480-file manifest
bound through that review, frozen application source, accepted CPU1 ASR/P0
assets/runtime, current supervisor state, and a fresh private output directory.
No references, roster, speaker evidence or scoring truth enter the predictor.
The same application loops read 100-ms source chunks and the exact tail, retain
native endpoint state, reset only between independent scenes, and flush once.
All four variants have one resident model each in sequence. The two smoke files
are recollected in the complete bank; their old timings are not silently reused.

Outputs: immutable `ADMISSION.json`/`worker.json`, per-cell result and complete
compressed event logs, variant indexes, terminal result and supervisor progress.
All text/events remain private. Actual P0 or native P1 final-only formatting uses
the same separate modeled FIFO as the reviewed smoke; it is not an observed
application queue or first-visible latency. RSS/load/elapsed samples are isolated
component diagnostics, not whole-stack memory/performance qualification.

The fresh logical inventory counts all private campaign bytes without deduplication
credit or traversal of reparse points. Preparation charges an additional 2 GiB
for this run, 2 GiB for pending D1 smoke, 2 GiB for future D1 bank and 1 GiB
contingency against the existing 50-GiB shared allowance. This is conservative:
existing partial runs are counted as well as their future reservations. Inventory
errors fail admission. The run enforces its 2-GiB cap, C:50/G:75-GiB floors and
the packaging reserve before each cell. A UTF-8 counting writer stops before a
cell exceeds 32 MiB of expanded event text. Failed cells and logs are preserved;
there is no silent retry, deletion, download or replacement of an admission.

Only the existing supervisor's exact coordinator PID/creation identity can
launch model children. Coordinator and supervisor use CPU14; the sole model
uses CPU4, one library thread, GPU disabled, below-normal priority and hidden
processes. Do not start this worker until previous numerical work and mandatory
review finish and fresh process identities confirm a free slot. No waiter is
created. Run `phase`/`start` from a caller already pinned to CPU14 so the hidden
supervisor inherits that affinity. No desktop, microphone, playback or Pi access.

PowerShell preparation and verification (no inference):

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpCode\asr_full_bank.py" prepare --smoke-review "$jpLocal\n4\asr-smoke-review-v1\REVIEW.json" --output "$jpLocal\n4\asr-full-bank-v1" --state "$jpLocal\supervision"
& $jpPython -B "$jpCode\asr_full_bank.py" check --admission "$jpLocal\n4\asr-full-bank-v1\ADMISSION.json"
```

Command Prompt / Anaconda Prompt uses the exact application interpreter:

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_CODE%\asr_full_bank.py" prepare --smoke-review "%JP_LOCAL%\n4\asr-smoke-review-v1\REVIEW.json" --output "%JP_LOCAL%\n4\asr-full-bank-v1" --state "%JP_LOCAL%\supervision"
"%JP_PY%" -B "%JP_CODE%\asr_full_bank.py" check --admission "%JP_LOCAL%\n4\asr-full-bank-v1\ADMISSION.json"
```

After all prior ownership has exited and its review passes, run these pinned
supervisor commands sequentially. They are launch instructions, not permission
to duplicate an active worker.

```powershell
& $jpPython -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name='__main__')" "$jpCode\..\supervision\supervisor.py" phase --root "$jpLocal\supervision" --phase inference --stage N4
& $jpPython -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name='__main__')" "$jpCode\..\supervision\supervisor.py" start --root "$jpLocal\supervision" --spec "$jpLocal\n4\asr-full-bank-v1\worker.json"
```

```bat
"%JP_PY%" -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name='__main__')" "%JP_CODE%\..\supervision\supervisor.py" phase --root "%JP_LOCAL%\supervision" --phase inference --stage N4
"%JP_PY%" -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name='__main__')" "%JP_CODE%\..\supervision\supervisor.py" start --root "%JP_LOCAL%\supervision" --spec "%JP_LOCAL%\n4\asr-full-bank-v1\worker.json"
```

`review_asr_full_bank.py` requires terminal 1,920/1,920 coverage and an exited
exact coordinator. It checks the full indexes, all cell/source/profile/cache
bindings, every gzip through EOF/CRC, expanded hashes, source dispatch/tail/drain
censuses, original raw/native finals and formatting parent/FIFO integrity.
Output is a fresh `REVIEW.json` plus small `REDACTED_REVIEW.json`; the latter
contains aggregate counts and evidence bindings without utterance text.
`PASS_ASR_FULL_BANK_COMPONENTS_ONLY` does not establish coupled policy, naming,
Controller/widget parity, accuracy, resource tier or paced latency.

```powershell
& $jpPython -B "$jpCode\review_asr_full_bank.py" --run "$jpLocal\n4\asr-full-bank-v1" --output "$jpLocal\n4\asr-full-bank-review-v1"
```

```bat
"%JP_PY%" -B "%JP_CODE%\review_asr_full_bank.py" --run "%JP_LOCAL%\n4\asr-full-bank-v1" --output "%JP_LOCAL%\n4\asr-full-bank-review-v1"
```

Tests exercise full-bank and tap census, reference/gain firewall, exact UTF-8
budget enforcement, actual frozen loop endpoint/tail capture, payload counting,
disk/deadline guards and refusal of incomplete smoke. The reviewer test constructs
1,920 temporary cells from actual-loop stub events and verifies every complete
log; it also rejects 1,919 cells, a missing indexed job and a live child. These
fixtures are unit tests with no neural inference or saved recording access.
Their placeholder audio bindings do not supply waveform/header qualification;
real admission independently checks the actual bank headers and hashes.

```powershell
& $jpPython -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_*asr_full_bank.py','-v']; runpy.run_module('unittest',run_name='__main__')" $jpCode
```

```bat
"%JP_PY%" -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_*asr_full_bank.py','-v']; runpy.run_module('unittest',run_name='__main__')" "%JP_CODE%"
```
