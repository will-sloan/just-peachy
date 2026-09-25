# Complete A0–A3 composition builder

`compose_release_v3.py` extends the earlier A0/A2/A3 preparation to all 16
intended A0–A3 × D0/D1 × E0/E1 combinations, using the implemented portable A1
adapter. It preserves the existing baseline and original model/precision,
streaming, P0/P1, input and identity assets. New rows copy only the exact identity
components from the matching A0 donor; A1 retains its qualified bundle hash and
inference-only frontend. Modes, taps, rosters and evaluator truth are forbidden
in the composition. An absent A1 adapter is an error, not a silent 12-row matrix.

Inputs: the **accepted** N3 SOURCE_RECEIPT.json and a fresh derivative directory.
Outputs: copied source, full source receipt and backend catalog. Only the catalog
and its expected-set test are changed; all shared UI hashes and auxiliary files
are checked/preserved. It runs no inference, calibrates no threshold and confers
no compatibility or performance acceptance. The executable does not decide N3
acceptance: the campaign reviewer must first verify the final handoff and supply
that exact accepted source. No new derivative was generated during this code
preparation; the pending A1 Controller source is not yet accepted for N4.

`test_compositions.py` uses the current source catalog without loading models.
It tests all 16 unique tuples, source/baseline preservation, exact family-specific
ASR/PnC and identity donor fields, missing A1, invalid bundle/dither settings,
duplicate compositions and truth-field rejection. It neither freezes a release
nor gives any integrated N4 execution credit.

PowerShell tests from the campaign worktree:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B research/nvidia_nemo_comparison/20260924_campaign/n4/test_compositions.py
```

CMD or Anaconda Prompt (explicit interpreter; no activation):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n4/test_compositions.py
```

After N3 acceptance, set N3_ACCEPTED_RECEIPT to the reviewed absolute receipt
path and N4_FRESH_RELEASE to a fresh private release directory. Do not substitute
the historical n3-common-v2 or an unreviewed pending source. PowerShell:

```powershell
& $py -B research/nvidia_nemo_comparison/20260924_campaign/n4/compose_release_v3.py --source-receipt $env:N3_ACCEPTED_RECEIPT --output $env:N4_FRESH_RELEASE
```

CMD/Anaconda:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n4/compose_release_v3.py --source-receipt "%N3_ACCEPTED_RECEIPT%" --output "%N4_FRESH_RELEASE%"
```

`check_catalog_v3.py` selects each of the 16 actual Controller entries and closes
it, with model acquisition/enrollment forbidden and no file/GUI/microphone start.
It uses CPU4/BelowNormal. Inputs are `--source` (new derivative prototype),
`--n2-runtime`, `--n3-runtime` (including the accepted A1 bundle), `--models`
(existing baseline model root), and fresh `--output`. Outputs: private
RESULT.json with selection/cleanup, modes, zero model loads and bound inputs.
It is prepared but has not yet run against an accepted N4 derivative.

Using reviewed environment paths, PowerShell:

```powershell
& $py -B research/nvidia_nemo_comparison/20260924_campaign/n4/check_catalog_v3.py --source "$env:N4_FRESH_RELEASE/prototype" --n2-runtime $env:N2_RUNTIME --n3-runtime $env:N3_RUNTIME --models $env:BASELINE_MODELS --output $env:N4_CATALOG_CHECK
```

CMD/Anaconda:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n4/check_catalog_v3.py --source "%N4_FRESH_RELEASE%\prototype" --n2-runtime "%N2_RUNTIME%" --n3-runtime "%N3_RUNTIME%" --models "%BASELINE_MODELS%" --output "%N4_CATALOG_CHECK%"
```

D0/E1 still requires its own C-only association profile. D0 activity, bounded
archive lifecycle, integrated runner, full-bank scoring, GUI/resource checks and
shortlist remain separate required work. Keep earlier 12-composition releases,
failed runs and all accepted source unchanged. No default model promotion, user
desktop control, personal profile modification or Pi connection is performed.
