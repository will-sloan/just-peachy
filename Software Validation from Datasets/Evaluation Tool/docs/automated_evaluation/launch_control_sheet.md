# Launch control sheet — campaign_05_massive_release

> **Launch verdict: `NOT_READY_TO_LAUNCH`. Do not run either launch command until both assignment preflights return `READY_TO_LAUNCH` and the small/standard gates have passed.**

| Final operational fact | Value |
|---|---|
| Repository remote | `https://github.com/will-sloan/just-peachy.git` |
| Candidate branch / evidence commit | `handoff` / `4e1c1e7cea17bfdea87f4af6c4ae1d23d5052f44` |
| Repository freeze | Not frozen: Stage 14 changes are uncommitted. After one reviewed commit/push, each clean clone must run `python scripts/materialize_launch_campaign.py --bind-current-commit` and compare its generated `worker_assignments/release_binding.json`. |
| Campaign ID | `campaign_05_massive_release` |
| Campaign SHA-256 | `FF833023B2CBFCC58C4CB65038BBF97A4A791296BE8AC7C09B6AA948C66046D4` |
| Benchmark hashes | large `BC207E61B82052F06CCB9FFFE038B6DFE7B1C65C21843D08905946114238DE88`; speaker `A9B0B28F5C7FDEF51215069521215BB78598DB9497E40BDA6C893181F71288D4` |
| Expected completion | 41 global scenarios; 25,798 item executions; 33.720121 repeated audio hours |
| Scientific scope | Whisper Base, CPU/float32, full-record ASR reference/robustness candidate; not a finalized multi-backend release campaign |

| Machine | Readiness | Assignment / batch | Work | Runtime estimate | Output estimate |
|---|---|---|---:|---:|---:|
| A | `NOT_READY_TO_LAUNCH`: all 20 assigned scenarios have resolvable local inputs, model/RIR identities and compatible `core-cpu`; blocked by dirty source tree and missing FFmpeg | A1 candidate: `assignment_5014479496c7`, SHA `5014479496C7A64708449EF0AD02BA591DA0E21CFBA8832F9156618FDD36589F`; final launch identity comes from `release_binding.json` | 20 scenarios; 12,368 items; 16.882998 h | 4.08 h point; 3.46–6.24 h | 2.15 GiB artifacts; 7.15 GiB minimum free including reserve |
| B | `NOT_YET_TESTED`; all 21 scenarios passed a static source/model/RIR/pipeline cross-check on A, but B's actual environment/data/output/disk/hardware remain unverified | B1 candidate: `assignment_53642fa92b2a`, SHA `53642FA92B2AE31526C7948432E620B32BFC871954C69C2FDB0688A16AFF2020`; final launch identity comes from `release_binding.json` | 21 scenarios; 13,430 items; 16.837123 h | 4.07 h point; 3.45–6.24 h, **provisional from A CPU rate** | 2.30 GiB artifacts; 7.30 GiB minimum free including reserve |

Manual blockers remaining: review/commit/push the Stage 14 launch package once; check out that exact commit on both clean clones; run the post-commit binding command on both machines and confirm byte-identical `release_binding.json` files; install FFmpeg on A; set up B and return its profile/full preflight; execute the component canary; run and pass the small then standard scientific gates; freeze a screening-based finalist campaign. Bedroom is unresolved and excluded without substitution. ParkingLot is not Bedroom or Kitchen.

Required environment: root `.venv`, Python 3.12, `core-cpu`, PyTorch CPU, FFmpeg. Required model: `models/cache/whisper/base.pt`, 145,262,807 bytes, SHA-256 `ED3A0B6B1C0EDF879AD9B11B1AF5A0E6AB5DB9205F891F668F8B0E6C6326E34E`. Required credentials for this candidate: **none**. Pyannote/Falcon credentials are optional and those backends are excluded.

From `Software Validation from Datasets/Evaluation Tool`, after every blocker is cleared:

```powershell
# Both clean clones, before preflight or launch
python scripts/materialize_launch_campaign.py --bind-current-commit
Get-FileHash automated_runs/campaign_05_massive_release/worker_assignments/release_binding.json -Algorithm SHA256

# Machine A — batch A1
powershell -ExecutionPolicy Bypass -File scripts/launch_campaign_machine_a.ps1

# Machine B — batch B1
powershell -ExecutionPolicy Bypass -File scripts/launch_campaign_machine_b.ps1
```

```powershell
# On either worker clone
python run_evaluation.py campaign status --campaign-root automated_runs/campaign_05_massive_release
python run_evaluation.py campaign stop --campaign-root automated_runs/campaign_05_massive_release --reason "operator request"
powershell -ExecutionPolicy Bypass -File scripts/launch_campaign_machine_a.ps1 -ResumeStopped  # A only
powershell -ExecutionPolicy Bypass -File scripts/launch_campaign_machine_b.ps1 -ResumeStopped  # B only
```

```powershell
# Export only after that worker reports complete
powershell -ExecutionPolicy Bypass -File scripts/export_machine_a_results.ps1
powershell -ExecutionPolicy Bypass -File scripts/export_machine_b_results.ps1
```

Transfer exactly `transfer_packages/campaign_05_massive_release/machine_a` and `transfer_packages/campaign_05_massive_release/machine_b`. Allow about 2.15 GiB and 2.30 GiB respectively; keep at least 15 GiB free on the coordinator for both transfers, merged copies, analysis, and reserve.

```powershell
# Coordinator
powershell -ExecutionPolicy Bypass -File scripts/merge_massive_campaign.ps1 `
  -MachineATransfer C:/campaign_transfers/campaign_05_massive_release/machine_a `
  -MachineBTransfer C:/campaign_transfers/campaign_05_massive_release/machine_b

powershell -ExecutionPolicy Bypass -File scripts/analyze_massive_campaign.ps1 `
  -PrerequisiteEvidence automated_runs/campaign_04_standard_release/analysis/report/release_qualification.json
```

Expected final report: `automated_runs/campaign_05_massive_release/analysis/report/campaign_report.md`. Final completion requires 41/41 checksum-valid merged scenarios and a passed standard-gate prerequisite; validation alone is not scientific release approval.
