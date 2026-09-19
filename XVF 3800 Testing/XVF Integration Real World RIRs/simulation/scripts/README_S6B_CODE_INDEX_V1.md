# S6B code and run-documentation index, version 1

This is a documentation-only supplement to the existing S6B READMEs. It does
not change an executable, an execution identity, a profile, or a result. The
audit covers all 27 `simulation/scripts/s6b*.py` files, the four APP modules
added since the preserved S6A V2 snapshot, the four changed APP integration
modules, and the frozen `atomic_io_v1` launch adapter. Snapshot copies and the
preserved pre-correction mechanism extractor are historical source versions,
not additional public programs.

The report `CODE_AND_README_INDEX.json` maps every program/module to its run
README, records absolute paths and SHA256 hashes, and identifies any frozen
epoch2 counterpart. `CODE_AND_README_REVIEW.md` records the review boundary.
Library modules use their documented caller and checks; they do not need an
invented standalone CLI. `s6b_common.py` and `s6b_inputs.py` share
`README_S6B.md`. All mapped READMEs include purpose, inputs, outputs and commands
for PowerShell and Anaconda Prompt/Command Prompt.

## Scope of this documentation supersession

Earlier READMEs remain byte-for-byte preserved. Their dated statements that a
pilot or challenge is running describe earlier checkpoints. The current
challenge prediction index is complete at 3,872 outputs. Full confirmation,
paced qualification, final review and packaging each require their own
completion receipts; this documentation audit grants none of those statuses.

For this run's eventual combined analysis, explicitly use
`FULL_PREDICTION_INDEX.json`. Generic `PREDICTION_INDEX.json` examples in the
earlier analysis, revision and uncertainty READMEs are superseded only for that
final combined index argument. Their metric definitions and other instructions
remain applicable. Run these commands only after the named index and its
required upstream work are complete; use a new output version for corrections.

## PowerShell: final combined core analysis

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$analysisPython = "$sim\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
& $analysisPython "$sim\scripts\s6b_analysis.py" --index FULL_PREDICTION_INDEX.json --output-subdir full_analysis_v1 --require-complete
```

Inputs are the complete, guarded combined prediction index, bound source
support and frozen metric dependencies. Outputs are per-output scores, pooled
and paired tables, coverage and `ANALYSIS_RECEIPT.json` in `full_analysis_v1`.
Source-verified score transfers must finish before that analysis starts; see
`README_S6B_SCORE_TRANSFER.md`. The existing pinned analysis interpreter is
required; no installation or activation is needed.

## Anaconda Prompt / Command Prompt: the same analysis

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "ANALYSIS_PY=%SIM%\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
"%ANALYSIS_PY%" "%SIM%\scripts\s6b_analysis.py" --index FULL_PREDICTION_INDEX.json --output-subdir full_analysis_v1 --require-complete
```

The mapped execution and replay READMEs select the frozen epoch2 sources and
the separately bound atomic writer adapter. The APP README's manual live-source
example is a separate development entry point and does not reproduce the frozen
campaign simply by using the same profile name. Do not rerun admission,
compilation, or fixture commands into already-bound output names.

The paced README intentionally leaves the finalist IDs pending. Its existing
preparation is model-free; a future final study must explicitly pass the single
comma-separated value `--streams O0,O1`, both repetitions and the owner's exact
four-profile list. The final exact command belongs to the prospective paced
methodology after selection and before launch.

## Verify this documentation index without running models

PowerShell, using the same `$sim` value above:

```powershell
$indexPath = "$sim\reports\S6B\20260909T230840Z\CODE_AND_README_INDEX.json"
$codeIndex = Get-Content -LiteralPath $indexPath -Raw | ConvertFrom-Json
foreach ($binding in $codeIndex.bindings) {
    $actual = (Get-FileHash -LiteralPath $binding.path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $binding.sha256) { throw "Changed indexed file: $($binding.path)" }
}
Write-Output 'All indexed code and documentation hashes match.'
```

Anaconda Prompt / Command Prompt, using the same `SIM` value above:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -c "import hashlib,json,pathlib; p=pathlib.Path(r'%SIM%\reports\S6B\20260909T230840Z\CODE_AND_README_INDEX.json'); j=json.loads(p.read_text(encoding='utf-8')); bad=[b['path'] for b in j['bindings'] if hashlib.sha256(pathlib.Path(b['path']).read_bytes()).hexdigest()!=b['sha256']]; assert not bad,bad; print('All indexed code and documentation hashes match.')"
```

These verification commands read the indexed compact source/document files and
print success or fail on changed bytes. They do not regenerate the index or
run any model, replay, scoring, or packaging work. A later legitimate source or
documentation update needs a newly reviewed index version; it does not make
the earlier audit an assertion about the changed files. The index excludes its
own bytes, and the review note does not embed the index hash, keeping provenance
finite.
