# S4.5 H2 result durability fix

S4.5 section 8 authorizes a narrow lifecycle/export repair. The original daemon watcher announced COMPLETED before writing `session_summary.json`; the CLI could return zero and terminate that writer. Four S4 summaries were separately reconstructed from preserved completion evidence. Those historical files and recovery labels are not changed by this fix.

Only `Evaluation Tool/app/edge_speech_pipeline/runtime.py` and `cli.py` change. The writer now creates a unique temporary file in the destination directory, writes/flushes/fsyncs it, closes it, then atomically replaces the summary. CLI success requires a bounded explicit writer-thread join, which also waits for transcript/event handles to close. Writer errors and unfinished lane/writer joins produce failure rather than false success. A new session cannot replace state while the prior artifact writer is still running. The existing 30-second lane-drain timeout remains; the final CLI join allows 65 seconds for failure cleanup. These are lifecycle limits, not model/scientific parameters.

Revision 2 also orders RUNNING and `session_started` before starting the completion watcher. A deterministic short-source fixture demonstrated that revision 1 could finish the watcher first and then overwrite COMPLETED with RUNNING after closing the event file. Revision 2 preserves terminal completion and emits startup before completion. This is an additional lifecycle ordering repair, with no change to ASR, embeddings, thresholds, labels or source data. The 30-second per-lane drain limit is an effective completion bound independent of the outer runner's default 240-second process timeout.

Revision 3 establishes RUNNING and `session_started` before starting either model lane or the source. An immediate lane failure could previously be overwritten by the later startup assignment, allowing CLI success despite a failure event. Publishing startup before any worker starts gives a defined ordering and removes that race without a check-then-assignment or changes to worker algorithms. The deterministic before/after fixture retains the observed revision-2 false completion and verifies revision 3 produces FAILED, no completion event and CLI exit 2. ASR, speaker and source worker start order remains unchanged; the lifecycle startup event now precedes those workers' events.

Model assets, ASR/embedding/segmentation loops, timing windows, thresholds, labels, source normalization and scientific configuration remain unchanged. No extra wait is inserted between speaker/ASR lanes to alter their decisions. The source-time completion event retains its original meaning; successful CLI return additionally establishes completed artifact writing. Process wall time can increase by the actual finalization work and is not isolated model compute or live latency. The atomic write protects complete-file visibility; it does not claim immunity to hardware or filesystem failure. A failed replacement retains the prior destination and its diagnostic temporary file. Actual fixture runs also exposed Windows access/sharing conflicts on freshly created destinations. Only Windows errors 5/32/33 receive a bounded retry of the same atomic replacement: four attempts with 10/20/40-ms delays, then failure propagation. No permissions or destination contents are changed to force success.

## Versioned evidence and tests

`simulation/staging/s45_h2_fix/v1` contains:

- `START_STATE.json`: prior Git HEAD/status, exact original source hashes and unchanged scientific/baseline bindings.
- `original/runtime.py` and `original/cli.py`: exact pre-fix bytes, never overwritten.
- `test_h2_durability.py`: deterministic, model-free regression fixtures.
- `test_runs/<UTC>/`: retained journals, summary files, stdout and test result data.
- `durability.patch` and `FIX_RECEIPT.json`: exact authorized source diff and final verification evidence after testing.

The active repair receipt is now `simulation/staging/s45_h2_fix/v3/FIX_RECEIPT.json`. Revisions 1 and 2 retain their exact code, documentation, diffs and receipts. Revision 3 contains original S0 sources, `prior_v1` and `prior_v2` copies, the unchanged baseline manifest, the full current diff, the intentionally failing pre-fix reproduction and the passing 13-test model-free suite. `README_S45_H2_FIX.tested_v1.md` and `.tested_v2.md` preserve earlier documentation in their corresponding folders. The current runner accepts only the v3-bound source hashes.

Tests run an original-code subprocess whose delayed writer leaves an empty summary despite exit zero. Fixed-code fixtures demonstrate that the CLI waits for atomic replacement and handle closure, retains exact PCM16/text/labels/event ordering, preserves an existing summary on replacement failure, and propagates writer/lane/join failures. Source-AST/hash checks ensure scientific methods and other baseline files are unchanged. These fixtures do not execute neural models or audio/USB endpoints; later predeclared S4.5 development sentinels provide the real-model diagnostic.

## PowerShell

```powershell
$repo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$sim = "$repo\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
$py = "$repo\.edge-speech-env\python.exe"
& $py "$sim\staging\s45_h2_fix\v3\test_h2_durability.py"
# Existing lightweight runtime/science checks, without model inference:
Set-Location -LiteralPath "$repo\Software Validation from Datasets\Evaluation Tool"
& $py -m pytest 'tests/edge_speech_pipeline/test_edge_runtime.py' -q
```

## Anaconda Prompt or Command Prompt

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "..\..\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\staging\s45_h2_fix\v3\test_h2_durability.py"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -m pytest tests/edge_speech_pipeline/test_edge_runtime.py -q
```

Use the existing environment; no dependency installation is part of this change. The test helper discovers repository paths from its versioned staging location. It writes only its own small test-evidence folders.

## Later S4.5 sentinel use

After independent review and the coordinator's release, the new S4.5 runner will bind these repaired source hashes and use the same file CLI on explicit mono 16-kHz inputs. Select only the frozen development sentinels and approved dry-source checks. Use a fresh isolated `EDGE_SPEECH_DATA_ROOT` per job and the frozen O0/O1 host gains. Do not send references, names or seats to H2. Do not run reserve task scores or repeat historical S4 model jobs. The old S4 runner intentionally retains its old source contract and is not a launcher for the repaired S4.5 baseline.

No real model job is executed by the durability test commands. See `README_S45_H2_RUN.md` for the separate bounded sentinel/dry-control launch, validation and resume commands.
