# N1 note traceability and source examples

`../NOTE_COVERAGE.csv` maps the 13 numbered sections in the supplied `C:\Users\amiri\Downloads\NOTE_COVERAGE.md` summary plus the granular N1 attachment requirements. The underlying full original notes were not supplied in this task. Item wording is a traceable paraphrase of those two sources, not an invented verbatim quote. Observations, proposals and the current user's instructions are kept separate. Evidence paths are relative to the campaign worktree unless they begin with a drive letter. `IMPLEMENTED` identifies inspected code, while `ACTUALLY_RUN` requires an execution receipt. N2-N5 research efficacy is not implied by passing source tests.

`test_note_examples.py` checks source text and event invariants for WD-40 and Amir against the frozen prototype. It uses an isolated temporary vocabulary, synthetic IDs and no audio. It verifies original text/hash retention, explicit context/approval safeguards, ambiguity/protected-number abstention and stable span IDs. WD-40 reconstruction is explicitly unavailable in the existing letters-only vocabulary rules and remains N3 work. The tests do not change the prototype, train models, read a personal gallery, open a microphone or create GUI windows.

PowerShell:

```powershell
$review = 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\review'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$review\test_note_examples.py"
```

Command Prompt or Anaconda Prompt (no activation needed):

```bat
set "REVIEW=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\review"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%REVIEW%\test_note_examples.py"
```

Inputs are embedded source-text/event fixtures and the frozen prototype modules. Outputs are console test results and `NOTE_EXAMPLE_TESTS.json`. Temporary vocabulary files are removed after each test. No acoustic scenes are created.

The coverage builder also refreshes baseline, supervisor and Git execution states from completed analysis/GUI receipts, the final supervisor test log and `GIT_RECEIPT.json` when available. Missing or incomplete baseline receipts keep that row `IMPLEMENTED`. A verified source push is distinguished from a still-pending report payload push. The audit records hashes of receipts used for these updates. Rebuild the CSV after final receipt changes and before assembling/package validation; this never changes the frozen screen or application.

`build_note_coverage.mjs` authors the CSV through the bundled spreadsheet Artifact Tool from a static, reviewed note-to-evidence mapping. It also validates the column schema, all 13 source sections and unique section/item keys. It writes `NOTE_COVERAGE_AUDIT.json`; the local render is an authoring check, not an extra delivered workbook. Re-run only when intentionally revising the mapping. Use the bundled Node executable and a `node_modules` junction to the path returned by `load_workspace_dependencies`; dependencies are never installed into the application environment.

```powershell
& 'C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' "$review\build_note_coverage.mjs"
```

CMD or Anaconda Prompt:

```bat
"C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe" "%REVIEW%\build_note_coverage.mjs"
```

If the junction is absent, create it from PowerShell with `New-Item -ItemType Junction -Path "$review\node_modules" -Target 'C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules'`. The ignored junction is tooling only and must never be committed or packaged. No formulas or extra XLSX output are needed for this flat research catalogue.

## Full application checks with physical audio disabled

`hardware_blocked_suite.py` loads all prototype unittest modules after disabling
real audio enumeration/capture/playback. Synthetic adapter fixtures still run.
The Windows private-desktop launcher never switches the input desktop or sends
input. Inputs are source and isolated test fixtures; outputs are unittest, JSON
isolation, hardware guard and app-render receipts in a new evidence directory.
Models and private profiles are not needed. The source root is the worktree.

PowerShell, from the worktree root:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B -m prototype.tests.run_private_desktop --receipt-dir 'G:\Just_Peachy_N1\20260924_campaign\local\checks\full-suite-NEW' --timeout-seconds 600 research.nvidia_nemo_comparison.20260924_campaign.review.hardware_blocked_suite
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -m prototype.tests.run_private_desktop --receipt-dir "G:\Just_Peachy_N1\20260924_campaign\local\checks\full-suite-NEW" --timeout-seconds 600 research.nvidia_nemo_comparison.20260924_campaign.review.hardware_blocked_suite
```

Choose a new receipt directory for every run. A successful exit means software
fixtures passed, not physical microphone, Pi, touch or target-memory validation.
