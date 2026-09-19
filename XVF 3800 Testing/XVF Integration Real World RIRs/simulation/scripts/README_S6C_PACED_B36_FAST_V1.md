# Fast outer observer: B36 exact historical original_common profile

Purpose: use the separately bound current regular-file scanner for the historical outer storage guard. This is a new observer version. Original native execution, profiles, APP/assets, inputs, job objects, gain, ordering, timeouts, state caps and admission/between-cell/terminal scan call sites remain unchanged. The one authorized periodic timer change restarts the20-second interval after the prior full scan completes. Historical paced RAM is explicitly strengthened to12GiB; continuous was already12GiB. Read `README_S6C_HISTORICAL_FAST_OBSERVER_V1.md` for exact scan/link/error, ownership and timing limitations.

Inputs: exact held parent source; the original prepared manifest below and its SHA; a fresh namespace ending `_fast_v1`. Checks/prepare consume metadata only. Run independently rehashes original native dependencies and requires an explicit quiet admission. Output checks are immutable; use a new output filename to repeat. New plan directory is separate from the original. No source/PCM is copied or regenerated.

Original authority: `G:\Just_Peachy_S6C\20260910T123540Z\paced_controls\b36_v1\MANIFEST.json` SHA `dd55f7fb64182e7c90eca2cbaf58fe41b1589937e14c96ad38f7b5dae2bee14f`.
New plan: `G:\Just_Peachy_S6C\20260910T123540Z\paced_controls\b36_fast_v1\MANIFEST.json`.
Helper: `C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6c_paced_b36_fast_v1.py`.
Shared utilities: `C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6c_historical_fast_observer_v1.py`.

## PowerShell

```powershell
Set-Location -LiteralPath 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B 's6c_paced_b36_fast_v1.py' checks --source-manifest 'G:\Just_Peachy_S6C\20260910T123540Z\paced_controls\b36_v1\MANIFEST.json' --source-sha256 'dd55f7fb64182e7c90eca2cbaf58fe41b1589937e14c96ad38f7b5dae2bee14f' --output 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6C\20260910T123540Z\historical_fast_observers\CHECKS_B36_V3.json'
# Only when root requests a fresh metadata-only preparation:
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B 's6c_paced_b36_fast_v1.py' prepare --source-manifest 'G:\Just_Peachy_S6C\20260910T123540Z\paced_controls\b36_v1\MANIFEST.json' --source-sha256 'dd55f7fb64182e7c90eca2cbaf58fe41b1589937e14c96ad38f7b5dae2bee14f' --namespace 'b36_fast_v1'
# After separate explicit root authorization and a completed exact quiet admission:
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B 's6c_paced_b36_fast_v1.py' run --manifest 'G:\Just_Peachy_S6C\20260910T123540Z\paced_controls\b36_fast_v1\MANIFEST.json' --quiet-admission 'C:\absolute\path\ROOT_AUTHORIZED_QUIET_ADMISSION.json'
```

## Anaconda Prompt / CMD

Open Anaconda Prompt. The explicit EDGE Python supplies the fixed environment; do not substitute the active Conda Python. No conda activation/install is required.

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "s6c_paced_b36_fast_v1.py" checks --source-manifest "G:\Just_Peachy_S6C\20260910T123540Z\paced_controls\b36_v1\MANIFEST.json" --source-sha256 "dd55f7fb64182e7c90eca2cbaf58fe41b1589937e14c96ad38f7b5dae2bee14f" --output "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6C\20260910T123540Z\historical_fast_observers\CHECKS_B36_V3.json"
rem Only when root requests fresh metadata-only preparation:
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "s6c_paced_b36_fast_v1.py" prepare --source-manifest "G:\Just_Peachy_S6C\20260910T123540Z\paced_controls\b36_v1\MANIFEST.json" --source-sha256 "dd55f7fb64182e7c90eca2cbaf58fe41b1589937e14c96ad38f7b5dae2bee14f" --namespace "b36_fast_v1"
rem After separate exact root quiet authorization; replace the explicit admission placeholder:
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "s6c_paced_b36_fast_v1.py" run --manifest "G:\Just_Peachy_S6C\20260910T123540Z\paced_controls\b36_fast_v1\MANIFEST.json" --quiet-admission "C:\absolute\path\ROOT_AUTHORIZED_QUIET_ADMISSION.json"
```

The quiet-admission placeholder is not a supplied authorization. Original source deadlines remain unchanged; this adapter does not extend the study deadline. Original plan must be unexecuted; any prior physical attempt requires a separate disposition. New plan is PREPARED metadata only, not an actual measurement. Model calls, native launch, gallery or output success are not inferred from preparation. The new fast schema is an explicit additive declaration; held V4/V5 collectors must not silently pretend the new entry point is the old one.

Outputs: `PREPARATION.json`, the new `MANIFEST.json`; later original job and invocation records, plus `observer_invocations/<id>/SCANNER_OUTCOME.json` for measured scan call counts/wall/CPU/error totals. That supplementary report does not establish worker closure or quiet lease release. Source checks print their own exact path/size/SHA binding.
