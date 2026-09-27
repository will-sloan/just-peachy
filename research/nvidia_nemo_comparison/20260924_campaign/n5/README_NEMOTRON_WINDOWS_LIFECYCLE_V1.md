# A2 Windows saved-file lifecycle

Purpose: check the immutable, N3-accepted A2 Nemotron English source in the real
Windows Controller/Tk application. This derivative of the baseline lifecycle
harness selects A2, supplies its exact CPU runtime bindings, checks every source
and ASR sample, and saves/reopens/deletes one isolated test transcript across two
processes. Caption-only tests ASR; anonymous-conversation additionally requires
all D1 identity samples and zero final speaker lag. These are separate checks.
No research gallery, personal store, microphone, playback or Pi is used.

Both GUIs use the existing owned private-desktop/job helper, below-normal CPU4,
one numerical thread and GPU disabled. The coordinator uses CPU14. No visible
window, desktop switch or input injection is performed. The source release,
past results and shared ledger are unchanged. Existing N3 GUI evidence remains
valid in its stated scope; this test does not promote N4 or N5 acceptance.

Inputs: `prepare_nemotron_windows_lifecycle_v1.py --name NAME --mode MODE`,
where NAME is fresh and starts `nemotron-windows-`, and MODE is `caption_only`
or `anonymous_conversation`. It verifies the accepted N3 source receipt, runtime
bindings, required models, prior baseline prepared O0 WAV, exact previous process
identities, a fresh complete resource census, free-space floors and shared budget.
It freezes a private CHECK and starts one worker through the existing supervisor.
Never repeat an existing name. An active or competing evaluation blocks admission.

Outputs: private `local/n5/NAME-precheck` census/admission/start receipts and
`local/n5/NAME` phase logs, sample counts, telemetry, saved-row fingerprints,
isolated data and exact owned-job closure receipts. Private transcripts remain
outside Git. A failed run is preserved. A PASS requires nonempty rendered and
persisted captions, matching rows on reopen, only the test session deleted,
unchanged synthetic people sentinel, complete sample/drain evidence, and normal
unforced exit of both processes. It is one 44.7-second saved file, not a full-bank
result, live-audio qualification, all-mode test or latency claim.

Each allocation is 600 seconds / 128 MiB and must end before the existing
2026-09-28 02:48:19 UTC packaging reserve. Each child has a 240-second operation
budget plus cleanup; the parent waits at most 285 seconds per child. Source and
asset hashes are rechecked. A CHECK must start within 120 seconds of admission.
Internal `--child` arguments are only for the verified private-desktop owner.

## PowerShell

```powershell
cd G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B -m unittest test_nemotron_windows_lifecycle_v1 -v
# Fresh name; starts actual saved-file work only after all admission checks:
& $py -B prepare_nemotron_windows_lifecycle_v1.py --name nemotron-windows-caption-v1 --mode caption_only
# After that worker has closed, use a new name for the identity-inclusive check:
& $py -B prepare_nemotron_windows_lifecycle_v1.py --name nemotron-windows-anonymous-v1 --mode anonymous_conversation
```

## CMD / Anaconda Prompt

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%JP_PY%" -B -m unittest test_nemotron_windows_lifecycle_v1 -v
"%JP_PY%" -B prepare_nemotron_windows_lifecycle_v1.py --name nemotron-windows-caption-v1 --mode caption_only
rem Run the following only after the first owned worker has closed:
"%JP_PY%" -B prepare_nemotron_windows_lifecycle_v1.py --name nemotron-windows-anonymous-v1 --mode anonymous_conversation
```

The explicit interpreter uses the existing environment; no package installation,
model download, environment activation or device connection is needed.
