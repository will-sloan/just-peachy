# S6D current-state handoff packager

Status: historical preparation only; do not run for the current study. Width execution started on 2026-09-14 at04:47 UTC, making this zero-width narrative obsolete. No package was built with this helper.

Purpose: create a compact, clearly INCOMPLETE S6D checkpoint handoff while physical capture and the operational-width experiments have not run. This is not a substitute for finishing S6D. The helper refuses a new physical ledger, any existing width execution directory (including partial/running work), or any existing output/ZIP path. A later handoff must use updated analysis reflecting actual execution.

Inputs: current fixed S6D local receipts, original240-scene bank/listening/pacing data,13-pair native pilot analysis and correction receipt,75prepared-input provenance, exact reviewed source epochs, final independent score-protocol review, and the two bounded Markdown handoff sections under reports/S6D/20260913T195357Z/handoff_preparation_v1. The original Revision20 Word workbook is bound but never edited. No audio, vendor documents, vectors or full logs are copied into the ZIP.

Outputs: a fresh curated Markdown/JSON/CSV folder, one ZIP at a new simulation/handoffs filename, member SHA256 checksums and an external DELIVERY.json with ZIP hash/size/count and verification status. CSVs are machine-readable evidence/coverage exports, not new modeled results. All zero-capture rows explicitly say NOT_RUN. The helper verifies240coverage rows,13native pair rows, all JSON, ZIP CRC and every member hash; <=80members and<=20MiB hard cap, <=10MiB target. No statistical analysis or model/hardware job is launched. Root must still read the narrative and final review before delivery.

Uses Python3 standard library only; no installation or activation is needed. Replace PROTOCOL_REVIEW with the actual final independent receipt path. Use new v2/v3 suffixes if any prior build exists; partial artifacts are retained. Current code is deliberately for zero-capture/zero-width-prediction checkpoints and must be reviewed/updated before packaging a later completed study.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$review = '<PROTOCOL_REVIEW: actual independent score-protocol receipt path>'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$sim\scripts\s6d_checkpoint_handoff_v1.py" --output "$sim\reports\S6D\20260913T195357Z\handoff_preparation_v1\package_v1" --archive "$sim\handoffs\S6D_JOINT_CHATGPT_HANDOFF_20260913T195357Z_PARTIAL_20260914_v1.zip" --protocol-review $review
```

Anaconda Prompt / Windows CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PROTOCOL_REVIEW=actual independent score-protocol receipt path"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%SIM%\scripts\s6d_checkpoint_handoff_v1.py" --output "%SIM%\reports\S6D\20260913T195357Z\handoff_preparation_v1\package_v1" --archive "%SIM%\handoffs\S6D_JOINT_CHATGPT_HANDOFF_20260913T195357Z_PARTIAL_20260914_v1.zip" --protocol-review "%PROTOCOL_REVIEW%"
```

The exact completed command and accepted protocol path will be saved in the package staging parent once available. This documentation does not authorize the proposed external installer move or physical playback. Existing50GiB C/75GiB G experiment floors remain unchanged; this small file-only packaging operation runs within the authorized metadata-preparation scope.
