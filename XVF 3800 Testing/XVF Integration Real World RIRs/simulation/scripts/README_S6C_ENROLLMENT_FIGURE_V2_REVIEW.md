# Enrollment figure caption revision review

This read-only review verifies the exact V1 numeric review and V2 figure/source bindings, same scoring authority/table, identical canonical plot data and PNG bytes, and source AST equality after replacing only the single caption literal. It checks the corrected each-roster14/combined28 and whole-clip/template coupling wording. It does not recompute scores, inspect predictions, rerender or claim another visual review.

Inputs are the two figure receipts, prior738-check independent review, V2 visual/caption review, preserved V1 source, current source/README, exact source CSV and figure artifacts. Output is a fresh `independent_review/ENROLLMENT_DURATION_FIGURE_REVIEW_V2.json`; existing output is rejected. The preserved source resolves the original V1 source binding instead of pretending V1 ran the revised source. Run once for these exact bytes.

PowerShell:

```powershell
Set-Location -LiteralPath 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' test_s6c_enrollment_figure_v2_review.py
```

Anaconda Prompt / CMD:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" test_s6c_enrollment_figure_v2_review.py
```

No plotting imports, neural models, policy replay, native events, PCM or scoring are used. Canonical JSON comparison ignores object-key serialization order but preserves arrays, types and number representation.
