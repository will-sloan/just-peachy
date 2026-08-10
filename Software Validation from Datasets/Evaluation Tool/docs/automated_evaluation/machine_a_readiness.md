# Machine A readiness

Verdict: **`NOT_READY_TO_LAUNCH`**. The complete assignment was inspected, not
sampled. All 20 assigned scenarios passed scenario-specific data, model, RIR,
pipeline, bounds, and executor-support checks, but assignment-wide launch
approval is blocked by the dirty candidate source tree and missing FFmpeg.

## Measured profile

| Capability | Observed value |
|---|---|
| OS | Windows 11, AMD64 |
| CPU | AMD64 Family 25 Model 33; 8 physical / 16 logical cores |
| RAM | 68,641,923,072 bytes (about 63.9 GiB) |
| GPU | NVIDIA GeForce RTX 3080, 10,240 MiB; driver 610.62 |
| Active launch environment | Python 3.12.7; PyTorch 2.11.0+cpu; `core-cpu` |
| CUDA in active interpreter | Unavailable by design; the candidate is CPU/float32 |
| FFmpeg | Missing from `PATH` — blocker |
| Campaign disk at final capture | 391.47 GiB free; required preflight minimum about 7.15 GiB |
| Required model | Whisper Base exact size/hash present |
| Assignment | `assignment_5014479496c7`; 20 scenarios; 12,368 item executions; 16.882998 audio hours |
| Complete input coverage | 20/20 scenarios; 2,750 unique source-audio files |

Machine A's point estimate is 4.08 hours, with a 3.46–6.24 hour planning
interval. This is a capacity estimate from the observed CPU Whisper Base rate,
not a completion guarantee.

## Actions required

1. Install FFmpeg from the repository root:

   ```powershell
   powershell -ExecutionPolicy Bypass -File install.ps1 -Profile dev -Device cpu -InstallFFmpeg
   where.exe ffmpeg
   ffmpeg -version
   ```

2. Commit/push the reviewed Stage 14 changes once and use a clean clone at that
   final commit. Generate runtime assignments with `--bind-current-commit`;
   do not edit tracked package identities after the commit.
3. Materialize the frozen campaign and rerun the full preflight:

   ```powershell
   Set-Location 'Software Validation from Datasets/Evaluation Tool'
   python scripts/materialize_launch_campaign.py --bind-current-commit
   powershell -ExecutionPolicy Bypass -File scripts/launch_campaign_machine_a.ps1
   ```

The final command starts inference only if every check is ready. Until the
small/standard scientific gates pass, stop after the generated preflight and do
not authorize the massive run. The evidence files are
`artifacts/launch_readiness/machine_a_profile.json` and
`machine_a_assignment_preflight.json`.
