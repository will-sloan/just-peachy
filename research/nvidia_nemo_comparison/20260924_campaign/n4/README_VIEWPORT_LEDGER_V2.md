# Viewport ledger V2: shared-reference and exact file-bound repair

Purpose, inputs, lifecycle and private-data policy follow README_VIEWPORT_LEDGER.md.
Use this derivative for subsequent qualification and application integration.
V1 remains immutable: seven fixture tests passed, but the first saved GUI history
exposed shared first/final/latest references being destructively expanded. V1's
large fixture also wrote 8,756,915 bytes because its summary check measured compact
JSON while its writer used indented JSON. Neither issue changes the application.

`viewport_ledger_v2.py` preserves the compact shared references while building
independent evaluator-only expanded states. It writes exactly the compact bytes
that were checked, including the newline, under the 8-MiB summary bound. Logs
remain 64-MiB maximum, individual records 8 MiB, lifetime spans 8,192, active rows
512 and memberships 16,384. Limits fail explicitly and preserve a complete
prefix; no observations are silently dropped. Captions are stored privately
once per changed row, not copied into each span's in-memory first/final/latest.

The same eight tests use all 160 saved actual-Tk observation pairs and verify
exact equality to their prior visibility histories. Fixtures cover delayed final
state, changed labels, resegmentation/retirement, corrupted records, clock
regression, thread ownership and storage/span limits. The long-caption fixture
checks actual SUMMARY.json bytes, round-trip equality and compact metadata with
8,192 spans. Synthetic timestamps are not an actual 20-minute continuity run.

No model, GUI, source audio, microphone, USB, playback, profile mutation or
training is performed. The helper pins CPU14, one math thread and GPU off, and
checks the shared payload/disk/deadline limits. Outputs are fresh private
ADMISSION.json, unittest.txt, CHECKS.json, RESULT.json and per-case log/summary
files. Deliberately invalid fixtures are retained and labelled as tests. Actual
source/consumer closure, paced GUI timing and whole-stack memory remain pending.

## PowerShell

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B 'research\nvidia_nemo_comparison\20260924_campaign\n4\probe_viewport_ledger_v2.py' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\viewport-ledger-v2'
```

## CMD / Anaconda Prompt

No new conda environment is needed. Use the pinned application Python:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n4\probe_viewport_ledger_v2.py --output G:\Just_Peachy_N1\20260924_campaign\local\n4\viewport-ledger-v2
```

Keep the output private, preserve existing attempts and use new derivative code
after a failure. Call add/close only from the original UI thread; do not expand
summaries in the measured application. File flushing and hashing costs belong
in later whole-application resource measurements. Sampling still provides point
observations, not continuous name exposure, physical scanout or target fit.
