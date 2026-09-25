# N4 comparison preparation and evaluation

N2 is accepted; N4 is pending N3 numerical review and its own admission. Nothing in this
directory changes the active N2/N3 source, personal profiles or Windows desktop.
The Pi stays off. Only accepted saved audio is used; there is no device access.
README_EVIDENCE.md documents the later archive reader and scorer integration;
this is supporting implementation, not full-bank execution or stage acceptance.

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
