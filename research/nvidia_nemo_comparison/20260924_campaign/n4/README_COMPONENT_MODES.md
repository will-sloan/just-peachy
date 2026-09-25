# Catalog-correct modeled naming and display replay

`component_mode_replay.py` integrates the existing causal ASR/D0 or ASR/D1
replay with fixed model-bound galleries and the actual application's mode
resolver. It calls the unchanged mode `begin()` methods through the separately
verified seam in `mode_galleries.py`. The original anonymous helpers, component
collectors and accepted source remain unchanged.

Inputs: the bound private GALLERIES.json from README_MODE_GALLERIES.md; catalog
backend key; explicit mode/tap; exact component namespace; verified complete
ASR commands and final formatting; D0 commands or D1 event log/summary/waveform;
original session ID. All five nonspatial modes have independent state. Names,
scores and evaluation references never select a query, ASR result or roster.
Namespace mismatch, mutated gallery, wrong diarizer and missing raw-final parent
fail explicitly. The caller first verifies all source/component evidence bytes.

Outputs: private raw/policy/native history, exact presentation states, and a
separate display-event history recording each state row and its immediate actual
`annotate_caption` result. State rows are never retroactively relabeled with
later names. The native caption state and annotation methods execute unchanged;
display history does not establish Controller label projection or widget receipt.
All times are explicitly modeled independent component FIFOs. Policy/name compute,
queue and publication delays remain zero assumptions. D1 native host timestamps
and costs remain diagnostic, outside the modeled chronology. No physical visible
name latency, full-stack resource measurement or Controller parity is claimed.

D0 retains actual tracking and catalog-specific naming. The original baseline
uses ResearchIdentityResolver when anonymous and PrototypeIdentityResolver when
named. The other 15 catalog entries use N2NameMap, including A1/A2/A3 D0/E0.
D0/E1 association remains nominal and unqualified after its failed C scale fit.
D1 uses the exact native slot timeline, query selector, held RLock, temporal
name history and target-span revisions. No D0 tracker receives a D1 embedding.
The same cooperative worker used by the anonymous helper holds the actual lock
while a cached embedding waits; raw text may arrive but cannot borrow its name
before completion. Actual query/short-run census must reproduce the parent.

Open N2 names retain reject-all. Closed N2 names are explicit unverified cosine
assumptions. Original baseline thresholds and closed display fallback remain
unchanged and unqualified for processed-query recognition. Baseline can publish
an assumed roster name without voice; N2 lacks that fallback. See
README_MODE_GALLERIES.md for this observed product-mode discrepancy. Counters in
these checks are diagnostic output counts, not accuracy or visible-name metrics.

`test_component_modes.py` tests actual D0 routing, D1 names/history and exact
queries, named text arriving during the identity lock, overlap staying unassigned,
separate state/display fallback, raw/final preservation, input corruption and
real worker cleanup. Synthetic profiles/stub model observations are confined to
temporary test folders. No private bank truth or new model inference is used.

`probe_component_modes.py` reuses reviewed eight-cell ASR smoke, two D0 cells per
encoder from the reviewed full bank, four D1 smoke cells and the passed gallery
preparation. It runs 16 catalog tuples x 5 modes x 2 taps = 160 development
replays, checking exact raw/final census and N2 open rejection. It rehashes all
source files, admissions, results, full compressed/expanded logs and waveforms.
No model constructor is allowed. It runs CPU14 below normal with one-thread
math settings while the sole numerical worker keeps CPU4. C50/G75-GiB floors
and a 512-MiB private output reservation apply within the shared campaign budget;
each expanded result is capped at 32 MiB. Every compressed artifact is round-trip
checked. RESULT.json binds all inputs/code/outputs; FAILED.json preserves failures.
Choose a fresh directory for each attempt. No download, desktop, Pi, capture,
playback, enrollment or adaptation occurs. Detailed text/names/vectors stay private.

These are method-level development replays. The integrated acceptance counter
remains 0/7,680 until actual Controller parity, global activity, admitted full-bank
execution/scoring and required paced GUI/resource checks pass. Do not substitute
the repeated 160 smoke combinations for 160 new neural inferences or bank coverage.

PowerShell:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local\n4'
& $jpPython -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_component_modes.py','-v']; runpy.run_module('unittest',run_name='__main__')" $jpCode
& $jpPython -B "$jpCode\probe_component_modes.py" --asr-review "$jpLocal\asr-smoke-review-v1\REVIEW.json" --d0-review "$jpLocal\d0-bank-review-v1\REVIEW.json" --d1-review "$jpLocal\d1-smoke-review-v1\REVIEW.json" --gallery-review "$jpLocal\mode-galleries-v1\RESULT.json" --output "$jpLocal\component-modes-probe-v1"
```

Command Prompt / Anaconda Prompt (use existing interpreter, no installation):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local\n4"
"%JP_PY%" -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_component_modes.py','-v']; runpy.run_module('unittest',run_name='__main__')" "%JP_CODE%"
"%JP_PY%" -B "%JP_CODE%\probe_component_modes.py" --asr-review "%JP_LOCAL%\asr-smoke-review-v1\REVIEW.json" --d0-review "%JP_LOCAL%\d0-bank-review-v1\REVIEW.json" --d1-review "%JP_LOCAL%\d1-smoke-review-v1\REVIEW.json" --gallery-review "%JP_LOCAL%\mode-galleries-v1\RESULT.json" --output "%JP_LOCAL%\component-modes-probe-v1"
```

Tests use the verified n4-catalog-v3 source (`JP_N4_SOURCE` may select an
equivalent test source). Production probes derive source from reviewed inputs.
Read both method receipts and limitations before building a full matrix runner.
