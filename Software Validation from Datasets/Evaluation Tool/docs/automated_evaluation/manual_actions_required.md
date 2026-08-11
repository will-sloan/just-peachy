# Manual actions required before either massive campaign

CPU and CUDA are first-class supported modes. The massive campaign remains blocked by clean-clone, second-machine, and scientific evidence—not by an API key.

| Owner | Required action | Exact completion evidence | Blocks massive launch |
|---|---|---|---|
| Amir | Use separate clean CPU and GPU clones at the final commit; materialize each selected campaign with `--bind-current-commit` | Clean Git status in each clone; each release binding names the checked-out commit | Yes |
| Amir | Create a new clean CPU validation clone and run the CPU real smoke plus complete assignment preflight | CPU `machine_a_assignment_preflight.json` says `READY_TO_LAUNCH` | Yes |
| Amir | Run the complete Machine A assignment preflight | `machine_a_assignment_preflight.json` says `READY_TO_LAUNCH`, 20/20 scenarios, 12,368 items | Yes |
| Machine B operator | Install the selected `core-cpu` or `core-cuda` profile; verify hardware, model, datasets, RIRs, and disk | Matching Machine B profile plus full 21-scenario preflight says `READY_TO_LAUNCH` | Yes |
| Scientific owner | Run/approve component canary | Accepted canary evidence for the exact selected Whisper Base configuration | Yes |
| Scientific owner | Run/approve small gate | Accepted small-tier report; no hidden missing/failures | Yes |
| Scientific owner | Run/approve standard gate | Accepted standard-tier prerequisite evidence supplied to analysis | Yes |
| Both operators | Confirm assignments do not overlap and release bindings match | Assignment-set validation passes on both clones | Yes |
| Both operators | Close GPU-heavy applications before timed runs | Operator log records a quiescent GPU | Recommended |

## No credential work is required

The campaign uses Whisper Base only. It does not use pyannote, Picovoice Falcon, hosted APIs, or credential-gated models. Do not create or distribute API keys for this campaign.

## Select one coherent distributed mode

Both workers may run the CPU campaign, or both may run the CUDA campaign after independent qualification. Do not combine a CPU assignment with CUDA scenarios or a CUDA assignment with CPU execution. A mixed-hardware study requires separately identified CPU and CUDA scenarios and must be analyzed as a hardware/profile comparison—not merged as one homogeneous campaign.

## Required local assets

- `models/cache/whisper/base.pt`, 145,262,807 bytes, SHA-256 `ED3A0B6B1C0EDF879AD9B11B1AF5A0E6AB5DB9205F891F668F8B0E6C6326E34E`.
- Licensed dataset folders made available locally without committing or copying raw audio into campaign results.
- Dining Room RIR `h025_Diningroom_8txts.wav`, SHA-256 `940D761A280DCD8FAAB077074E02BADE649E64E47461D80A4F927A01ABBEF5E2`.
- Restaurant RIR `h093_Restaurant_2txts.wav`, SHA-256 `C2CA8A07002943409D31A2C6D6D07BA826AA428FE6EF6CECF2C4FF33D7D4A8A8`.
- FFmpeg on `PATH`.

Bedroom remains unresolved. It is not part of either 41-scenario executable campaign and must not be replaced.

## Machine B decision rule

Machine B must run the same result-affecting mode as Machine A. For the CPU campaign that is `core-cpu`, `cpu`, `float32`; for the CUDA campaign it is `core-cuda`, `cuda:0`, `float32`. Both use the Whisper Base hash above and the frozen batch/runtime settings. A different CPU or GPU model is permitted and recorded as environment metadata, but switching CPU/CUDA mode or dtype changes scientific scenario identity and requires the corresponding separately generated scenarios and assignments. Run one GPU-heavy scenario at a time.
