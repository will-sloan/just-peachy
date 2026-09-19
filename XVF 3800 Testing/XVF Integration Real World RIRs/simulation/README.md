# Post-measurement simulation stages

The current S4 run is [reports/S4/20260909T002140Z](reports/S4/20260909T002140Z/START_HERE.md). Its [S4_REPORT.md](reports/S4/20260909T002140Z/S4_REPORT.md) and machine-readable completion/package receipts govern actual completion; [README_S4_PIPELINE.md](scripts/README_S4_PIPELINE.md) gives purpose, inputs, outputs and exact PowerShell/Anaconda Prompt commands. The active human guide is the bound V8 workbook in Downloads. S3 physical transport proof is preserved at [reports/S3/20260908T214914Z](reports/S3/20260908T214914Z/S3_REPORT.md). Do not infer the current phase from older S0 instructions below, replay completed hardware passes, or start S5/S6 without a later request.

The full 121-record library remains **95 EXTRACTED, 26 EXTRACTED_WITH_LIMITATIONS, zero FAILED**. The sole canonical set is [rir_library/v1](rir_library/v1/README.md), defined by its RIR_MANIFEST.json. [S2_README.md](S2_README.md) records extraction commands and [RESULTS.md](rir_library/v1/RESULTS.md) its outcomes. All original/S0/S1/S2/S3 evidence remains unchanged; S4 reuses the library and demonstrated physical transport rather than regenerating either.

S1 is the historical bounded 12-record pilot: four provisional limited-band/tail and eight timing-review candidates. See [S1_README.md](S1_README.md) and [S1_REPORT.md](reports/S1/20260908T185148Z/S1_REPORT.md) for its preserved evidence. The subsequent full-library request superseded its stop gate; the S2 library above is now authoritative. Exact `Loeb Caf` exclusions, retained `Upper Loeb`, 121 active candidates, original 52 exclusions, room descriptions and ±5 degree angle context remain in force. Do not rerun completed S0/S1 from the historical commands below.

## S0: local input binding and baseline inventory

The S0 scripts implement input binding and inventory only. S1 separately adds the bounded RIR pilot described above. Audio scene synthesis, HIL, training and deployment are later stages. Reference packs and recorded evidence remain unchanged.

Inputs are the explicit 127-record allowlist, 52 exclusions, supplied correction overlays, current Word workbook, local H2 source/assets, and existing dataset indexes. Outputs are JSON/CSV/Markdown receipts under `reports/S0/<run_id>` and a compact handoff ZIP under `handoffs`. The completed run is `20260908T181703Z`; start with its `S0_REPORT.md` and `NEXT_PHASE_INPUTS.md`.

Dependencies: existing Anaconda base for parquet metadata; existing `.edge-speech-env` for H2; the recorder's bundled Python for XVF control/enumeration. No installation is required. Scripts use a cached SHA-256 receipt keyed by absolute path, size, mtime and ctime. Changed files are rebound; an expected-hash mismatch is never repaired. Cache receipts are local optimization evidence, not a replacement for externally supplied expected hashes. Keep scripts sequential: they share one cache/status writer. Do not run them simultaneously against one report.

## Script contracts

| Script | Purpose, inputs and outputs |
| --- | --- |
| `scripts/capture_inventory.ps1` | Read Git/desktop resources before work; takes `-Report`; creates git_before.json/resource_observations.json; refuses an existing snapshot. |
| `scripts/s0_catalog.py` | Explicit allowlist and supplied workbook -> bound catalogue, unchanged 12-record pilot, versioned angle overlay, source and cached hash receipts. Reads only needed source bytes and WAV headers. No extraction. |
| `scripts/s0_baseline.py` | Existing H2 config/assets and short known WAV -> current model/config manifest, one accelerated offline CLI smoke and local journal. Uses an isolated empty profile gallery. Refuses a second smoke in the same report. |
| `scripts/s0_datasets.py` | Existing six parquet indexes and bounded local licence-document scan -> dataset CSV/details/rights receipts. Index counts, sample path checks and a few separate-file enrollment/probe examples; no full audio scan or embeddings. |
| `scripts/s0_device.py` | Existing recorder getters under the existing lock -> endpoint/current state inventory and command receipts. No setters, stream, reset, or flash. Use the bundled recorder Python; its vendor dependencies do not match H2 Python. |
| `scripts/s0_common.py` | Shared paths, SHA cache, atomic receipts, 15 s heartbeat, manifest/path checks; imported helper, not a standalone command. |
| `tests/test_s0.py` | Eight failure-oriented hash/path/correction/wrap tests on temporary fixtures. |
| `scripts/verify_s0.py` | Read reports and optional ZIP; validate catalogue contracts and all ZIP payload hashes; no raw audio rehash or device action. Exit 2 on failure. |
| `scripts/package_s0.py` | Assemble the executed S0 report, active context/log, resource recommendation, next-input hashes, small source evidence and verified ZIP. Takes `--report` and actual `--started-utc`. It does not run S1. The prose is specific to this S0 campaign: review/revise it if new evidence differs rather than treating it as a generic future report generator. |

The report keeps capture audit, local file binding, RIR qualification and simulation readiness as separate fields. All current RIR and simulation-ready flags remain false. Both 100 m originals are assigned effective 1.00 m only after exact correction bindings; angle centers remain unchanged, with a circular ±5° user-estimated interval. `CONTEXT.md`, `DECISIONS.md` and `config/user_context_overlay.v2.json` carry the corrected units forward.

## PowerShell: recheck the existing catalogue only

These commands read/hash audited inputs and refresh derived S0 catalogue files; they do not extract a response or run H2/hardware. The completed handoff ZIP remains the delivered snapshot unless explicitly repackaged.

```powershell
$s0Sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s0Report = Join-Path $s0Sim 'reports\S0\20260908T181703Z'
& 'C:\Users\amiri\anaconda3\python.exe' "$s0Sim\scripts\s0_catalog.py" --report $s0Report --workbook 'C:\Users\amiri\Downloads\XVF_Measurement_V5.docx'
& 'C:\Users\amiri\anaconda3\python.exe' -m unittest discover -s "$s0Sim\tests" -v
& 'C:\Users\amiri\anaconda3\python.exe' "$s0Sim\scripts\verify_s0.py" --report $s0Report
```

To preserve the delivered report during a recheck, point `--report` at a new directory instead. Catalogue generation creates that directory; the full verifier additionally needs a baseline manifest.

## PowerShell: reproduce the other S0 inventories in a NEW run

Run sequentially. No activation is needed because each interpreter is explicit. Record a new actual start time and report directory; do not rerun the smoke over the completed evidence run.

```powershell
$s0Sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s0Started = [DateTime]::UtcNow.ToString('o')
$s0Run = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$s0Report = Join-Path $s0Sim "reports\S0\$s0Run"
& "$s0Sim\scripts\capture_inventory.ps1" -Report $s0Report
& 'C:\Users\amiri\anaconda3\python.exe' "$s0Sim\scripts\s0_catalog.py" --report $s0Report --workbook 'C:\Users\amiri\Downloads\XVF_Measurement_V5.docx'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' "$s0Sim\scripts\s0_baseline.py" --report $s0Report
& 'C:\Users\amiri\anaconda3\python.exe' "$s0Sim\scripts\s0_datasets.py" --report $s0Report
& 'C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 "$s0Sim\scripts\s0_device.py" --report $s0Report
& 'C:\Users\amiri\anaconda3\python.exe' -m unittest discover -s "$s0Sim\tests" -v 2>&1 | Tee-Object -FilePath "$s0Report\unit_tests.txt"
& 'C:\Users\amiri\anaconda3\python.exe' "$s0Sim\scripts\verify_s0.py" --report $s0Report
```

Only after reviewing results and updating this campaign-specific report prose if anything changed:

```powershell
& 'C:\Users\amiri\anaconda3\python.exe' "$s0Sim\scripts\package_s0.py" --report $s0Report --started-utc $s0Started
```

## Anaconda Prompt / Command Prompt

No conda activation or pip installation is necessary. The commands below recheck the completed run. To collect a new smoke, use a new S0REPORT directory and first run the equivalent PowerShell inventory commands above.

```bat
set "S0SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S0REPORT=%S0SIM%\reports\S0\20260908T181703Z"
"C:\Users\amiri\anaconda3\python.exe" "%S0SIM%\scripts\s0_catalog.py" --report "%S0REPORT%" --workbook "C:\Users\amiri\Downloads\XVF_Measurement_V5.docx"
"C:\Users\amiri\anaconda3\python.exe" -m unittest discover -s "%S0SIM%\tests" -v
"C:\Users\amiri\anaconda3\python.exe" "%S0SIM%\scripts\verify_s0.py" --report "%S0REPORT%" --zip "%S0SIM%\handoffs\S0_CHATGPT_HANDOFF_20260908T181703Z.zip"
```

For a new report directory, the same interpreter/argument contracts work in Command Prompt:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%S0SIM%\scripts\s0_baseline.py" --report "%S0REPORT%"
"C:\Users\amiri\anaconda3\python.exe" "%S0SIM%\scripts\s0_datasets.py" --report "%S0REPORT%"
"C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -X utf8 "%S0SIM%\scripts\s0_device.py" --report "%S0REPORT%"
```

## Monitoring, recovery and package contents

`status.json` and `heartbeat.jsonl` record stage/item counts, elapsed time, rate and ETA only when estimable. Long stages emit every 15 seconds; fast stages have start/end receipts. Atomic report renames tolerate brief Windows sharing locks. The catalogue caches successful hashes per record; rerunning preserves previous catalogue metrics and does not scale corrected values again. A stale/missing/mismatched file is explicit, never substituted. Device attempts are preserved and its lock always released. No commands kill unrelated programs.

The ZIP contains report/manifests, dataset rights excerpts, workbook text, small H2 source/context evidence, scripts/tests, corrected context and file hashes. It excludes audio, weights, profile vectors/names/enrollment audio, cache and vendor packages. Local smoke audio stays under that run's `smoke_data`. `FILE_LIST_AND_HASHES.json` and `SHA256SUMS.txt` inside the ZIP identify all payloads; the external `.receipt.json` identifies the ZIP and final validation time without circular hashing.

The code and reports sit inside an existing nested unborn measurement repository. Main H2 tracked files remain unchanged. There is no automatic commit or push.

**Future phases:** No S1/extraction command exists in this implementation. A later prompt must authorize the 12-case timing/RIR/noise pilot using `NEXT_PHASE_INPUTS.md`. Do not run hardware setters or packing/HIL merely because those plans appear in copied reference text.
