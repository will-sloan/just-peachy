# N4 comparison implementation and evaluation

README_PREPARATION_V2.md describes the regenerated preparation-v2 inputs from
the accepted 16-entry derivative. All 480 waveforms were reverified; the five
data/provenance payloads are byte-identical to v1, and all 16 matrix rows now
bind actual catalog entries. PREPARATION_V2_CHECK.json records zero inference
credit and 7,680 cells still NOT_TESTED.

N1/N2/N3 are accepted in their offline/component scopes. N4 has begun using the
accepted n3-common-a1controllerv2 source, not the historical 12-entry preparation.
The fresh local/releases/n4-catalog-v3 derivative preserves common UI/layout and
supports all 16 intended catalog tuples. Actual Controller selection/cleanup
passed 16/16 with model acquisition forbidden. See README_COMPOSITIONS.md,
ACCEPTED_SOURCE_CATALOG_CHECK.json and UPSTREAM_ACCEPTANCE_20260925.json.

N4 is not complete: zero of 7,680 integrated files have executed. The current
sole numerical run is `local/n4/asr-full-bank-v1`: 1,920 actual ASR component
cells, A0/A1/A2/A3 sequentially across all 480 admitted files. It started at
2026-09-25 04:30:24 UTC. ASR_FULL_BANK_START_V1.json binds its fresh admission,
source/runtime/code, 11 passing tests and initial exact ownership. Always read
fresh RESULT.json, panel progress and the supervisor heartbeat before model work.
README_ASR_FULL_BANK.md covers its 2-GiB cap, 32-MiB expanded per-cell limit,
full-bank admission and mandatory terminal review. Current private logical
inventory plus this run and conservative downstream reservations was 43.000 GiB
against the existing 50-GiB allowance. No competing model or waiter was started.

D0 full-bank component collection and review are complete: 960/960 cells,
480 per encoder, 13,006 exactly matched query windows per encoder (7,404 short,
5,602 mature). Eight files per encoder without admitted queries remain in the
denominator. Review verified 43,388 segmentation calls per encoder and all
2,621,822,924 expanded event bytes. D0_FULL_BANK_REVIEW_V1.json records
PASS_MATCHED_FULL_BANK_COMPONENTS_ONLY. This does not qualify a calibrated
D0/E1 profile, integrated application, full-stack resources or live latency.
README_D0_BANK.md and README_REVIEW_D0_BANK.md document collection and review.

The earlier C collection completed 734/734 jobs and passed paired review with
3,409 matched windows per encoder. The single predeclared C scale fit failed:
balanced error rose 2.583 percentage points versus E1 nominal, beyond the 2.0
limit. D0_C_SCALE_DECISION_V1.md/D0_SCALE_FIT_V1.json retain this failure; the
profile was not applied or retuned. Nominal D0/E1 remains an unqualified
engineering comparison. D0_COLLECTION_REVIEW_V1.json and the calibration,
review and scale-protocol READMEs retain exact evidence and commands.

The actual application ASR smoke passed 8/8 cells at 04:21:20 UTC, two per
variant. ASR_SMOKE_REVIEW_V1.json binds every complete log, raw/native final,
source tail, reset/drain and separate final-only formatting result. The actual
100-ms journal reads differ from the earlier N3 external 80-ms screen. The
new full-bank admission was made only after this review; the old smoke runner
still refuses full-bank scope. README_ASR_BANK.md and README_REVIEW_ASR.md
remain the reproducible smoke protocol, with 18 prior passing tests.

D1 smoke passed 4/4 cells at 04:29:22 UTC. Each E0/E1 pair matched all 4,470
native frames per file and 20 O0 / 19 O1 exact query windows. Two/four short
exclusive runs stayed explicit. D1_SMOKE_REVIEW_V1.json binds the results.
README_D1_COMPONENTS.md/README_REVIEW_D1.md document the unchanged actual N2
speaker loop, activity selector, native CPU1 owners and 22 passing tests.
Its timing remains modeled; full-bank D1 admission/runner and integrated
Controller/widget parity still need implementation. All smoke workers exited.

D0ActivityEvidence retains complete speech/silence/overlap masks, exact clean
track support, conflicts, unassigned speech and unobserved tails. Its two-cell
83-embedding probe matched incremental and batched nominal anonymous decisions;
33 tests passed. D0_IMPLEMENTATION_CHECK_V1.json and README_D0_ACTIVITY.md
bind that diagnostic. A global persistent-source decoder and actual S7 observed
policy/application integration remain pending; embedding windows are not DER.
The tested evidence_store.py helper has 12 passing lifecycle tests; production
integration and whole-stack storage bounds remain required.

The component-to-caption adapter calls actual frozen S7/N1 span state under an
explicit modeled replay contract; seven tests passed (COMPONENT_PRESENTATION_CHECK_V1.json,
README_COMPONENT_PRESENTATION.md). component_commands.py now reconstructs the
actual ASR/D0 prediction pushes and source watermarks. Seven actual-loop tests
and a 12-cell real-evidence reconstruction probe pass; COMPONENT_COMMANDS_CHECK_V1.json
and README_COMPONENT_COMMANDS.md bind that work. D1 command integration, causal
merge, observed S7 policy parity, Controller/GUI runs and full-bank scoring are
still required. Modeled values cannot be reported as first-visible latency.

The specification ceiling is 80 GiB; the shared resource-policy record retains
a more conservative 50-GiB payload allowance. Reconcile actual previous usage
and remaining allocation before admitting N4. Do not infer a fresh allowance
from a helper's maximum parameter. Preserve C:50 GiB/G:75 GiB and the deadline.
The user desktop remains available, the Pi stays off, and only saved audio is used.

`prepare.py` independently rehashes the 480 accepted PCM16 mono16k files, checks
their physical O0/O1 pair, gain and existing reference mapping, and freezes an
audio-only full bank plus 24-cell paced panel, separate evaluator strata and
the 16-composition preparation matrix. Its input is the existing N1 accepted
corpus and N2 reference manifest, not historical predictions. It runs no model.
Outputs include private paths/actor/source groups and remain outside Git.
It refuses to overwrite different evidence; use a new output folder for changes.
Existing `N2_...` job IDs intentionally preserve the audited reference joins.

From PowerShell:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research\nvidia_nemo_comparison\20260924_campaign\n4\prepare.py --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\preparation-v1'
```

From CMD or Anaconda Prompt (no environment activation required):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n4\prepare.py --output G:\Just_Peachy_N1\20260924_campaign\local\n4\preparation-v1
```

Optional `--local` and `--source` select an existing private campaign root and
frozen application. `--output` is required. Preparation does not run or admit a
matrix, install dependencies, start a second supervisor or update the shared
ledger. Do not start model jobs while N2/N3 own resources.

`common.py` is imported by the commands here. It provides strict bindings,
exclusive immutable JSON writes, the eight-field inference firewall and cache
keys. A key includes waveform, model/precision, preprocessing, streaming state,
history, scheduler and runtime. Embeddings additionally require exact waveform
span/hash; integrated records require parent evidence keys. A matching key alone
is not evidence of execution or authorization to reuse missing results.

The full bank is a seen engineering bank. Historical 180/60 partitions are
metadata. Source text, actor labels and noise metadata stay evaluator-only.
No new conversational gold, phonetic alignment or physical latency is inferred.

`check_readiness.py` is a read-only preparation inspector for the exact current
N2/N3 contracts and PID/creation identities. It writes one fresh status snapshot,
starts no watcher/model/LLM, and leaves the shared ledger untouched. It always
requires later N4 profile review; numerical completion is not acceptance.

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research\nvidia_nemo_comparison\20260924_campaign\n4\check_readiness.py --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\readiness-v1.json'
```

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n4\check_readiness.py --output G:\Just_Peachy_N1\20260924_campaign\local\n4\readiness-v1.json
```

## Separate composition release

`compose_release.py` copies only the hash-bound files from the N3 frozen source
to a fresh release. It adds six catalog compositions using the existing generic
Controller wiring: A2/A3 with D0/E0, D0/E1 and D1/E1. A0's four and A2/A3's D1/E0
already exist. Only `config/backends.json` and its expected-set test change. Outputs are a runnable source
tree, full file receipt and catalog; no weights or personal profiles are copied.
This is wiring preparation, not validated compatibility. D0/E1 still needs its
own C-only association profile; A1 still needs its integrated adapter. Do not
launch model validation until N2/N3 prerequisites are reviewed and resources free.

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research\nvidia_nemo_comparison\20260924_campaign\n4\compose_release.py --source-receipt 'G:\Just_Peachy_N1\20260924_campaign\local\releases\n3-common-v2\SOURCE_RECEIPT.json' --output 'G:\Just_Peachy_N1\20260924_campaign\local\releases\n4-catalog-v2'
```

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n4\compose_release.py --source-receipt G:\Just_Peachy_N1\20260924_campaign\local\releases\n3-common-v2\SOURCE_RECEIPT.json --output G:\Just_Peachy_N1\20260924_campaign\local\releases\n4-catalog-v2
```

The normal Windows entry point in that source tree is `prototype\Start-Prototype.cmd`;
use the documented isolated data-root launch in the inherited `app/README_N3.md`.
Do not use your personal root for research galleries. For rollback use the original
checkout/launcher, or select Baseline in the isolated app and start a fresh epoch.

The earlier `n4-catalog-v1` preparation is preserved. V2 adds the matching catalog
test expectation for 12 wired entries; no application algorithm changed. Both
the actual Controller-selection check and 15 catalog/ASR/text tests passed on v2.

`plot_bank.py` turns evaluator-only metadata into PNG/SVG reference-coverage and
dependency-group figures, plus a binding receipt. It scores no model. Inputs are
EVALUATOR_STRATA.json and a fresh output folder. Use the isolated metric Python:

```powershell
& 'G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\env\Scripts\python.exe' -B research\nvidia_nemo_comparison\20260924_campaign\n4\plot_bank.py --strata 'G:\Just_Peachy_N1\20260924_campaign\local\n4\preparation-v1\EVALUATOR_STRATA.json' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\plots-v1'
```

```bat
"G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\env\Scripts\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n4\plot_bank.py --strata G:\Just_Peachy_N1\20260924_campaign\local\n4\preparation-v1\EVALUATOR_STRATA.json --output G:\Just_Peachy_N1\20260924_campaign\local\n4\plots-v1
```

`check_catalog.py` checks actual Controller selection and cleanup for all 12 wired
compositions. It forbids model acquisition, uses fresh research data roots and
starts no file, microphone or GUI. Inputs are the derivative source, CPU runtime
JSON catalogs and existing baseline model root. Output is a private RESULT.json
with composition IDs, mode availability and zero-load checks. This checks wiring,
not inference correctness or a Windows GUI launch with loaded models.

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research\nvidia_nemo_comparison\20260924_campaign\n4\check_catalog.py --source 'G:\Just_Peachy_N1\20260924_campaign\local\releases\n4-catalog-v2\prototype' --n2-runtime 'G:\Just_Peachy_N1\20260924_campaign\local\n2\runtime\cpu\n2_runtime.json' --n3-runtime 'G:\Just_Peachy_N1\20260924_campaign\local\n3\runtime\v2\cpu\n3_runtime.json' --models 'C:\Users\amiri\JustPeachy\shared\models' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\catalog-check-v2'
```

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n4\check_catalog.py --source G:\Just_Peachy_N1\20260924_campaign\local\releases\n4-catalog-v2\prototype --n2-runtime G:\Just_Peachy_N1\20260924_campaign\local\n2\runtime\cpu\n2_runtime.json --n3-runtime G:\Just_Peachy_N1\20260924_campaign\local\n3\runtime\v2\cpu\n3_runtime.json --models C:\Users\amiri\JustPeachy\shared\models --output G:\Just_Peachy_N1\20260924_campaign\local\n4\catalog-check-v2
```
