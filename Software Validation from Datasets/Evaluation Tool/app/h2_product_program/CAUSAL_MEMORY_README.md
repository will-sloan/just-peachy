# H2 causal session-memory and short-turn evidence

## Purpose

`causal_memory.py` executes restart-safe, development-only session-memory
cells through the real `SessionIdentityManager` primitive. It evaluates M0-M5
at 15, 30, 60, and 120 seconds and end-of-session expiry, and evaluates
short-turn policies A-E from actual runtime events. Reference identity is
joined only after each runtime decision for scoring.

The protocol never narrows the enrolled gallery. M4 orders the active roster
first as a compute/search prior, asserts exact full-gallery membership, then
waits for every score before deciding. Its source-time exponential decay can
only release a tentative/confirmed identity; it cannot confirm or strengthen
one. M5 additionally reconciles a later non-overlapping fragment with an older
cluster using averaged full-gallery score signatures, a bounded time gap, and
at least two embeddings per fragment. Its similarity threshold targets at most
1% false merges on development-calibration identities and is frozen before the
development-selection cohort runs. It uses no future events, reference labels,
or spatial/XVF signal at decision time. Short-turn A-E results remain advisory
because no A-E axis is frozen into product tuning.

## Inputs and outputs

Inputs are a completed development post-promotion integration result containing
`events/events.jsonl.gz`, `diagnostics/cache_regime.json`, frozen speaker-
disjoint calibration/selection assignments, and reference observations. Every
cell binds the source result, cases, configuration, implementation, runtime
events, references, partition, and shared neural-cache manifest by SHA-256.

Outputs are immutable evidence files below each science job's
`artifacts/causal_memory_runtime_evidence/` or
`artifacts/causal_short_turn_runtime_evidence/` directory plus memory and
short-turn frontier CSVs. Metrics include first/returning name latency, warm
reacquisition, short-turn correctness by duration, stale/false inheritance,
new-speaker lockout, fragmentation, re-entry consistency, compute avoided,
contradiction outcomes, expiry/decay releases, active-roster use,
full-gallery-completion rate, reconciliation application/contamination,
effective post-reconciliation fragmentation, and bounded-state maxima.
Metrics are end-to-end on exact observed turns and conditional on the source
runtime's segmentation and clustering. If the calibration cohort has no causal
same-speaker fragment pair, M5 stays explicitly unsupported instead of using a
fabricated threshold.

## Run from PowerShell

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
.\scripts\run_h2_product_program.ps1 -Action Run -Background -OpenMonitor
```

The controller schedules `memory_policy_replay` and `short_turn_replay` after
the development integration dependency completes. Re-running the action reuses
only checksum-identical complete cells and fails closed on partial or changed
evidence.

## Run from Anaconda Prompt or Command Prompt

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" -m app.h2_product_program.cli run
```

## Verify without launching the neural campaign

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe' -m pytest -q tests\test_h2_causal_memory.py tests\test_h2_product_program_science.py tests\test_h2_product_program_controller.py tests\full_pipeline\test_h2_product_modes.py
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe' -m compileall -q app\h2_product_program\causal_memory.py app\h2_product_program\science.py app\h2_product_program\controller.py
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe' -m ruff check app\h2_product_program\causal_memory.py app\h2_product_program\science.py app\h2_product_program\controller.py tests\test_h2_causal_memory.py tests\test_h2_product_program_science.py tests\test_h2_product_program_controller.py
```
