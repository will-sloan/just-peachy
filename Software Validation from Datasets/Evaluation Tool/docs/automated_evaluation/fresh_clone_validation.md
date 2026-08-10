# Fresh-clone validation

Verdict: **`fresh_clone_ready_with_manual_prerequisites`** for the remote
`handoff` commit `4e1c1e7cea17bfdea87f4af6c4ae1d23d5052f44`. This proves the committed
Evaluation Tool can reach a real Whisper Base result; it does not prove that
the uncommitted Stage 14 launch package is reproducible from GitHub.

## Executed evidence

| Check | Observed result |
|---|---|
| Genuine clone | `git clone https://github.com/will-sloan/just-peachy.git`; branch `handoff`; exact remote commit above |
| Disposable clone | `<disposable-workspace>/prompt14-clean-clone` (portable privacy-safe location recorded in shared evidence) |
| Environment | New clone-local `.venv`; no reuse of the development `.venv` |
| Install | `powershell -ExecutionPolicy Bypass -File install.ps1 -Profile dev -Device cpu` succeeded |
| Activation | `powershell -ExecutionPolicy Bypass` activation succeeded; `activate.bat` succeeded in cmd; plain PowerShell activation is blocked by this machine's execution policy unless process bypass is used |
| Dependency consistency | `pip check` reported no broken requirements |
| Verifier | 25/26 checks after core asset bootstrap; only FFmpeg remained absent; CUDA correctly reported optional/unavailable in the CPU environment |
| Model acquisition | Repository bootstrap downloaded Whisper Tiny, Base, and Small and prepared SpeechBrain ECAPA; no inference-time download was enabled |
| Dataset access | Operator-supplied raw data was linked into the clone; the metadata alias-resolution defect found during this test is corrected in the current Stage 14 worktree |
| Real run | One CMU Arctic utterance through configured Whisper Base, standardized prediction, diagnostics, scoring, 11 plots, and report |
| Real result | 1 selected, 1 prediction, 0 failures, 0 missing; aggregate WER 0.25 for this smoke only |

Real run artifacts are under
`runs/prompt14_clean_clone/20260810_150810_cmu_arctic_full_prompt14_clean_clone_real`
inside the disposable clone. The hypothesis was “author of the danger trail,
fill up steels, etc.” for `CMU_ARCTIC_aew_arctic_a0001`; IDs and the
0.0–3.880063 second bounds were retained.

Clean-clone Whisper identities were Tiny 75,572,083 bytes / SHA-256
`65147644A518D12F04E32D6F3B26FACC3F8DD46E5390956A9424A650C0CE22B9`,
Base 145,262,807 /
`ED3A0B6B1C0EDF879AD9B11B1AF5A0E6AB5DB9205F891F668F8B0E6C6326E34E`,
and Small 483,617,219 /
`9ECF779972D90BA49C06D968637D720DD632C55BBF19D441FB42BF17A411E794`.

## Manual prerequisites

1. Install FFmpeg and reopen the terminal so `where.exe ffmpeg` succeeds.
2. Supply licensed datasets locally; they are not cloned from GitHub.
3. Bootstrap the exact required models with repository tooling before running;
   Tiny, Base, Small, and ECAPA were all verified in the clean clone, and
   implicit runtime downloads remain prohibited.
4. Commit and push Stage 14 once, repeat this clean-clone test at that new
   commit, and run `python scripts/materialize_launch_campaign.py
   --bind-current-commit` in both clones. Their generated
   `release_binding.json` files must be byte-identical.

The portable machine-readable evidence is
`artifacts/launch_readiness/fresh_clone_validation.json` in the development
workspace.
