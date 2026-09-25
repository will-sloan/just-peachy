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

N4 is not complete: zero of 7,680 integrated files have executed. The supervised
`local/n4/d0-bank-v1` now collects D0 component evidence on all 480 saved
scene/tap files, E0 then E1 sequentially (960 component jobs). Read its fresh
RESULT.json and the supervisor heartbeat before starting any model work.
README_D0_BANK.md covers bounded compressed storage and launch commands.
The earlier `d0-calibration-v1` completed 734/734 encoder/clip jobs; strict review
passed 3,409 matching windows per encoder. D0_COLLECTION_REVIEW_V1.json records
that result. The one frozen C-scale proposal failed its validation tradeoff and
remains UNQUALIFIED_C_SCALE: see D0_C_SCALE_DECISION_V1.md/D0_SCALE_FIT_V1.json.
It was not retuned or applied; nominal D0/E1 remains an unqualified comparison.
README_D0_CALIBRATION.md gives purpose, inputs, outputs and run commands;
eight tests passed. README_D0_REVIEW.md describes strict paired evidence review
with six passing tests. D0_C_SCALE_PROTOCOL_V1.json was frozen before inspecting
new C score values; collection alone does not qualify an association profile.
The fitting and bank runner add eight and five passing tests respectively.
The new full-bank reviewer and activity observer passed 33 tests including the
six reused geometry tests. README_REVIEW_D0_BANK.md gives the terminal-only
review command; do not run the C-population reviewer on these bank results.
README_D0_ACTIVITY.md describes the observer and its real closed-cell probe:
83 actual E0 O0/O1 embeddings gave identical anonymous decisions under the
native scheduler's incremental and batched causal ordering. Full speech masks,
unassigned speech, conflicts, overlap and the unobserved tail remain explicit.
D0_IMPLEMENTATION_CHECK_V1.json binds the code, tests and private probe.
This is two-cell development evidence, with no neural model loaded, no ASR or
gallery, and modeled clocks. It is not S7 Controller parity, a global-source
diarization decoder, paired full-bank review or an integrated result. Complete
D0 activity/application integration and the full-bank runner/cache replay still
need implementation; D0/E1 calibration remains unqualified. README_EVIDENCE_STORE.md
covers the tested new-run-only storage helper (12 tests); production integration
and measured cell/storage bounds remain. Existing evidence was not removed.

E0 has completed all 480 bank files and E1 is the active model worker. The first
two closed O0/O1 pairs passed exact geometry, full segmentation/admission and
event checks (D0_PAIR_PREFIX_CHECK_V1.json); this is not the final 960-cell review.
The next ASR smoke is prepared at `local/n4/asr-smoke-v1`, not started.
ASR_SMOKE_PREPARATION_V1.json binds its admission and 18 passing protocol/review
tests. README_ASR_BANK.md covers the unchanged application streaming loops,
accepted A0/A1/A2/A3 owners and separate final-only formatting. The actual source
reads 100-ms chunks, so the earlier 80-ms N3 screen is not silently reused.
README_REVIEW_ASR.md describes the mandatory terminal eight-cell integrity review.
After the D0 worker exits and its full-bank review passes, dispatch this ASR smoke
through the existing supervisor. Do not start a competing worker. Full-bank ASR
admission and integrated application/presentation parity remain pending.

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
