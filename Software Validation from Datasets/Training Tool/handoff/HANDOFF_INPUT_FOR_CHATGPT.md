# Just-Peachy RTX 3090 handoff input

Use this compact technical record to produce the receiver's human-readable
handoff. Do not infer that training, ONNX export, or Large evaluation has run.

## A. Repository

```text
BRANCH = codex/edge-component-expansion
STARTING_COMMIT = 76c4091692b937b53f97d475cc17cff32efd5998
FINAL_COMMIT = run `git rev-parse HEAD` after pulling the completed branch
PUSH_STATUS = verify with `git status -sb` and `git rev-list --left-right --count HEAD...@{upstream}`
WORKTREE_NOTE = six operator-owned Evaluation Tool run JSON changes and Evaluation Tool/artifacts/research_queue_logs were preserved and excluded from handoff commits
```

Git commit objects cannot contain their own final hash. The final response that
accompanies this file supplies the exact pushed HEAD; the command above is the
receiver's authoritative readback.

Git content audit: this handoff stages no audio/archive/checkpoint/environment/
run artifacts and no new blob at or above 1 MB. The following files at or above
10 MB were already tracked before this handoff and remain unchanged; the four
Evaluation Tool WAVs should have repository-owner redistribution confirmation
before sharing history beyond the intended operators:

```text
22,610,146  Evaluation Tool/m9_test/audio/a1.wav
22,610,146  Evaluation Tool/m9_test/audio/a2.wav
22,610,146  Evaluation Tool/m9_test/audio/b1.wav
22,610,146  Evaluation Tool/newyork_yapping.wav
70,582,622  Evaluation Tool/runs/20260419_210030_voices_full_libri_noisy/dataset_selection_records.jsonl
64,214,622  Evaluation Tool/runs/20260419_210030_voices_full_libri_noisy/dataset_selection_source_records.jsonl
27,562,805  Evaluation Tool/runs/20260419_210030_voices_full_libri_noisy/metrics/clean/per_recording_metrics.csv
27,562,805  Evaluation Tool/runs/20260419_210030_voices_full_libri_noisy/metrics/per_recording_metrics.csv
15,226,414  Normalized Metadata/AMI/segments.parquet
15,226,414  Normalized Metadata/AMI/utterances.parquet
21,351,537  Normalized Metadata/AMI/words.parquet
64,832,447  Normalized Metadata/HiFiTTS/normalization_log.csv
50,737,488  Normalized Metadata/HiFiTTS/utterances.parquet
69,502,286  Normalized Metadata/LibriSpeech/utterances.parquet
```

## B. Portable roots and receiver layout

```text
JP_REPO_ROOT     = receiver-selected repository checkout
JP_DATA_ROOT     = receiver-selected shared external-data root
JP_TRAINING_ROOT = receiver-selected generated manifest/state root
JP_MODEL_ROOT    = receiver-selected external model/checkpoint root
JP_RUN_ROOT      = receiver-selected run/checkpoint/output root
JP_WSL_DISTRO    = explicit receiver distro or validated unique WSL default
```

Preferred raw tree:

```text
JP_DATA_ROOT/Raw Datasets (Not formatted)/
  Common Voice.gz
  Common Voice/cv-corpus-26.0-2026-06-12/prepared/en/
  AMI Meeting Corpus/
  CHiME 6/
  CMU Arctic/
  VOiCES/
  LibreSpeech/
  Hi Fi TTS/
  MIT 271 RIRs/Audio/
```

`LibreSpeech` and `Common Voice.gz` retain their historical spellings/names so
frozen provenance does not change. The resolver aliases the old Common Voice
`JP_TRAINING_ROOT:datasets/.../prepared/en` location to the preferred shared
tree; the consolidation helper preserves the old physical location as a
junction. Raw data is not tracked by Git.

Current-machine consolidation result:

```text
MOVED = selectively materialized Common Voice prepared/en tree, from JP_TRAINING_ROOT:datasets/common_voice/english/cv-corpus-26.0-2026-06-12/prepared/en to JP_DATA_ROOT:Raw Datasets (Not formatted)/Common Voice/cv-corpus-26.0-2026-06-12/prepared/en
MOVE_VERIFICATION = 101,428 files; 7,299,277,413 bytes; deterministic 256-file sample SHA256 FC54DEEC8CDA1D199026C8AEEF6A9E9387E1A13F6BDCCDD6544A65696203A57D before and after
LEGACY_PATH = retained as a junction to the preferred shared tree
REMAINED_IN_PLACE = Common Voice.gz; AMI Meeting Corpus; CHiME 6; CMU Arctic; VOiCES; LibreSpeech; Hi Fi TTS; MIT 271 RIRs
```

The archive was not renamed or moved. The other datasets were already in their
preferred shared-root subfolders. No redistribution right is inferred from
their presence there; the receiver acquisition rules remain authoritative.

## C. Additive successor data freeze

```text
PARENT_PHASE4_ID = training_manifest_freeze_phase4_cc2909f344d0
PARENT_PHASE4_SHA256 = CC2909F344D01E9007EF648BA71277188DF26741CBEA5D1D2B0933116CE6DF92
SUCCESSOR_FREEZE_ID = training_manifest_freeze_successor_d11f526adfba
SUCCESSOR_FREEZE_SHA256 = D11F526ADFBA9DA1316CFCDA18B5423F011F3CE8CB48B6BF877B0207D00516CC
SUCCESSOR_FREEZE_PATH = JP_TRAINING_ROOT:successors/phase5a_portable_training_freeze_v1/registries/training_manifest_freeze_successor.json
```

Phase 3 and Phase 4 were not edited or overwritten.

## D. Common Voice change

```text
OLD_TRAIN = 79,594 records; 124.2506913666462 h; 1,089 speakers
OLD_DEV = 10,288 records; 18.055174539930555 h; 35 speakers
OLD_HELDOUT = 11,529 records; 15.54264837673611 h; 128 speakers
NEW_TRAIN = 91,123 records; 139.79333974338232 h; 1,217 speakers
NEW_DEV = 10,288 records; 18.055174539930555 h; 35 speakers
FORMER_COMMON_VOICE_HELDOUT_RECLASSIFIED_TO_TRAIN = YES
COMMON_VOICE_FINAL_HELDOUT_REQUIRED = NO
ADDITIONAL_FINAL_HOLDOUT = NO
AGE_DEV_USED_FOR_GRADIENTS = NO
```

The frozen Large benchmark is the independent post-training benchmark.

## E. Source manifests

All paths are logical and all unaffected references remain byte-identical to
Phase 4.

| Name | ID | SHA-256 | Records | Effective hours | Speakers | Logical path |
|---|---|---|---:|---:|---:|---|
| AGE_TRAIN | `age_train_manifest_90232912fe93` | `90232912FE9347DB76EEE5B5CF4436F09B346F0D80C2BAC0B47D213663651716` | 91123 | 139.79333974338232 | 1217 | `JP_TRAINING_ROOT:successors/phase5a_portable_training_freeze_v1/source_manifests/age_train.parquet` |
| AGE_DEV | `age_dev_manifest_6fd3d4dfacb7` | `6FD3D4DFACB798A9C359C4DA48AB35800CC0A54E5737809A87438DAA50B4C4D6` | 10288 | 18.055174539930555 | 35 | `JP_TRAINING_ROOT:successors/phase4_training_manifests_v1/development/age_dev.parquet` |
| AMI_TRAIN | `ami_train_manifest_26e9c3d6cb92` | `26E9C3D6CB92673D2029E7C764AC54CC1E9965B9228ACF2AFF34FFD0F4239D4A` | 682896 | 85.57721305555556 | 181 | `JP_TRAINING_ROOT:successors/phase4_training_manifests_v1/source_manifests/ami_train.parquet` |
| AMI_DEV | `ami_dev_manifest_392e7e4d2d41` | `392E7E4D2D414CE66A97A6E2AF0B1B95A674A689087B1F37537802544E48F459` | 85311 | 10.56365694444444 | 54 | `JP_TRAINING_ROOT:successors/phase4_training_manifests_v1/development/ami_dev.parquet` |
| CHIME_TRAIN | `chime_train_manifest_69ee9b9f0932` | `69EE9B9F09324D153EC4827327E1D72FC5F737F2A1DE820625018C3E9CE93EE6` | 51761 | 29.97446111111111 | 24 | `JP_TRAINING_ROOT:successors/phase4_training_manifests_v1/source_manifests/chime_train.parquet` |
| CHIME_DEV | `chime_dev_manifest_ba6dea2a89c7` | `BA6DEA2A89C7705DC4E0E9148FD9D848334066BB2AE4E8514907CC3E8428B391` | 11028 | 5.891880555555556 | 8 | `JP_TRAINING_ROOT:successors/phase4_training_manifests_v1/development/chime_dev.parquet` |
| VOICES_TRAIN | `voices_train_manifest_5ed9bdd5fadc` | `5ED9BDD5FADC6B3399BBCB173FEA86E329C6AD59E8F3EF05F9DFE3EDDEF3B8B7` | 16704 | 2.304051336388889 | 268 | `JP_TRAINING_ROOT:successors/phase4_training_manifests_v1/source_manifests/voices_train.parquet` |
| VOICES_DEV | `voices_dev_manifest_92d336921fc1` | `92D336921FC1EC35A39AFFBEDDA0EDE1FE7A47F320A6D5BBB1F8D56BBB4AE77F` | 1856 | 0.25600421861111106 | 30 | `JP_TRAINING_ROOT:successors/phase4_training_manifests_v1/development/voices_dev.parquet` |
| CMU_TRAIN | `cmu_relaxed_exploratory_train_manifest_f768bd2ba84d` | `F768BD2BA84DB91DA16788226DCD057CAEEAA6AD2D17777ED3C9B72D7B52AF9E` | 6379 | 5.66484971 | 14 | `JP_TRAINING_ROOT:successors/phase4_training_manifests_v1/source_manifests/cmu_relaxed_exploratory_train.parquet` |
| CMU_DEV | `cmu_relaxed_exploratory_dev_manifest_9787136d1023` | `9787136D10236E5E8BDF490C170B1F80490D90B421279FD24F5C296E6588361D` | 1802 | 1.4188877513888891 | 4 | `JP_TRAINING_ROOT:successors/phase4_training_manifests_v1/development/cmu_relaxed_exploratory_dev.parquet` |
| CLEAN_MONITOR | `clean_regression_monitor_manifest_d5a22fe5e6bd` | `D5A22FE5E6BD93E939A4B313B2504B6EAD2CE4983742DF0232D2FEF4DBB33D52` | 1487 | 5.000872291944445 | 1487 | `JP_TRAINING_ROOT:successors/phase4_training_manifests_v1/monitoring/clean_regression_monitor.parquet` |

## F. Bundles and exact weights

| Bundle | ID | SHA-256 | Exact weights |
|---|---|---|---|
| AGE | `age_bundle_6c15a716a5e6` | `6C15A716A5E6AB86383172194DF83E7A27206F014EBF7719E1ACDA65712CB04D` | `common_voice=1` |
| AMI | `ami_bundle_0dddb3c25dcf` | `0DDDB3C25DCF1F9053E32A8D3960B33BAD0EC2924305ED665FFE057B5B0113EC` | `ami=1` |
| CHIME | `chime_bundle_55552bf73da1` | `55552BF73DA169BDAC0AB62D1345CED56035B849B81D58B1FEB551AF944A71AB` | `chime6=1` |
| VOICES | `voices_bundle_82819d502e7a` | `82819D502E7A692A4EC6E6628AE37660EFF271E1A9786234EA18D27CB9216A72` | `voices=1` |
| ROBUST | `robust_bundle_204aa1c051dd` | `204AA1C051DD159AABB6B870000F2B48A4A0DDC2273B192A4CDE48FD524FB239` | `ami=0.56538717843912649506944032421900867864120416578872; chime6=0.33461282156087350493055967578099132135879583421128; voices=0.10` |
| AGE_ROBUST | `age_robust_bundle_90dde6962bda` | `90DDE6962BDA6314965505184EF9C21937C566F3E0E1D46DB39793A3BFA087FC` | `common_voice=0.40080741253527681038165049723636596635644147235827; ami=0.31359676502711856669722938656537408662846714478052; chime6=0.18559582243760462292112011619825994701509138286125; voices=0.10` |
| CMU_EXPLORATORY | `cmu_exploratory_bundle_46d30d7c0d82` | `46D30D7C0D824A03E11008BE2CA9BA7F8BC7F582DAF1A9B5A67F34CECD0721C7` | `cmu_arctic=1` |
| AGE_ROBUST_CMU_EXPLORATORY | `age_robust_cmu_exploratory_bundle_f7c98d9e6362` | `F7C98D9E63623556A5EE912F104200DFD3EFEC5AC326F723CD92190EF76203F9` | `common_voice=0.36783175873630330249825647867633407686969218123759; ami=0.28779619838938917300032950106916063138427093087775; chime6=0.17032628550832053953543863860923971215076256086440; voices=0.10; cmu_arctic=0.074045757365986984965975381645265579595274327020282` |

Affected bundle paths are below
`JP_TRAINING_ROOT:successors/phase5a_portable_training_freeze_v1/bundles/`.
Unchanged bundle paths remain below
`JP_TRAINING_ROOT:successors/phase4_training_manifests_v1/bundles/`.

## G. Eight Original experiments

The generated queue at
`JP_TRAINING_ROOT:successors/phase5a_original_adapter_training_v1/registries/original_adapter_queue.json`
is authoritative for exact derived budgets and run IDs.

```text
QUEUE_ID = adapter_queue_22d65f9ff187
QUEUE_SHA256 = 22D65F9FF187EDCEE288E2ACDE913089AC32E4062A0BD6FD80D666E3D017F3FA
```

| Experiment | Bundle | Class | Release review | Derived optimizer-step budget | Weighted unique hours |
|---|---|---|---|---:|---:|
| O-AGE | AGE | strict | no | 20000 | 139.79333974338232 |
| O-AMI | AMI | strict | no | 13693 | 85.57721305555556 |
| O-CHIME | CHIME | strict | yes | 4796 | 29.97446111111111 |
| O-VOICES | VOICES | strict | no | 1500 | 2.304051336388889 |
| O-ROBUST | ROBUST | strict | yes | 9384 | 58.64450316895899 |
| O-AGE-ROBUST | AGE_ROBUST | strict | yes | 14186 | 88.66048386214823 |
| O-CMU | CMU_EXPLORATORY | exploratory | no | 1500 | 5.66484971 |
| O-AGE-ROBUST-CMU | AGE_ROBUST_CMU_EXPLORATORY | exploratory | yes | 13089 | 81.80452844552707 |

```text
TOTAL_ORIGINAL_ADAPTER_JOBS = 8
GIGA_ADAPTER_JOBS = 0
```

## H. Frozen training system

```text
CHECKPOINT_ID = zengwei_librispeech_streaming_zipformer_2023_05_17_37cb5606808f
CHECKPOINT_SHA256 = E44BB7C8D3985A7CF0089020D227AECD71E323DCAAABCAED90E4A792E1385342
TOKENIZER_ID = sentencepiece_bpe500_c53433de083c
TOKENIZER_SHA256 = C53433DE083C4A6AD12D034550EF22DE68CEC62C4F58932A7B6B8B2F1E743FA5
TOKENS_SHA256 = 49E3C2646595FD907228B3C6787069658F67B17377C60AEB8619C4551B2316FB
ICEFALL_COMMIT = 3f848bb6d0acc970c9b294a30ca0a04a7c9c78d1
ADAPTER_IMPLEMENTATION = official Zipformer2 residual adapter, dimension 16
TOTAL_PARAMETERS = 66872275
TRAINABLE_ADAPTER_PARAMETERS = 761344
RECIPE_ID = original_adapter_recipe_94be54407fb2
RECIPE_SHA256 = 94BE54407FB240CD6EC9650E1B34A6539BE55AC1CF917BBB2F5E45D7C9AF8A36
BUDGET_POLICY_ID = original_adapter_budget_policy_250c2dc05ffb
BUDGET_POLICY_SHA256 = 250C2DC05FFB7FF372C76DDC9CFA23A48F1C7DB590877A22E77404A68D48E3C7
PRECISION = FP16; MICROBATCH = 45 seconds; GRADIENT_ACCUMULATION = 2; EFFECTIVE_TARGET = 90 seconds
```

## I. Portability fixes

Problems found: Windows backslashes were consumed by `wsl.exe`; `Ubuntu`,
`/home/amiri`, the checkpoint root, and run root were hardcoded; runtime bundle
lookup bypassed queue logical paths; Common Voice prepared audio lived below the
machine-local training root.

Fixes: forward-slash conversion is passed as one subprocess argument; distro is
explicit/discovered and validated; WSL HOME is discovered; all five roots are
propagated into WSL; checkpoint/run/audio/bundle paths use logical resolvers;
Common Voice has a verified external-root alias and consolidation helper.

Bootstrap: `scripts/bootstrap_training_machine.ps1`.

## J. Data inventory

Exact current/receiver paths, sizes, record/file counts, licences,
redistribution classifications, official sources, and verification commands are
in `handoff/training_handoff_data_inventory.json`. Common Voice, AMI, CHiME-6,
CMU Arctic, VOiCES, LibriSpeech, HiFiTTS, and approved Large RIRs are external
and not Git-tracked.

## K. Common Voice acquisition/materialization

```text
RELEASE = cv-corpus-26.0-2026-06-12 English 26.0
SOURCE_ARCHIVE_ID = common_voice_source_6809228e6ab5
ARCHIVE_BYTES = 94639372950
ARCHIVE_SHA256 = 6809228E6AB506D18F6A1EBC830056450F8266C8F513D6038BDB0FC88A49E6CB
RAW_COMMON_VOICE_AUDIO_TRACKED_IN_GIT = NO
```

Receiver acquisition is through its own Mozilla Data Collective access. After
all external sources are present, the single deterministic command is:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\bootstrap_training_machine.ps1 -Action MaterializeData -Apply
```

It rebuilds the frozen Phase-2 parent, verifies the full archive, reads metadata,
selectively materializes only eligible clips in a streaming traversal,
consolidates them below the preferred shared root, reconstructs and verifies
Phase 3/Phase 4/the additive successor, and stops on any mismatch.

## L. Model bootstrap

```powershell
..\..\.venv\Scripts\python.exe -m training_data.handoff acquire-models
..\..\.venv\Scripts\python.exe -m training_data.handoff verify-models
```

The source is the authoritative Hugging Face repository pinned to revision
`37cb5606808f3d5e55a3fc73554bdf757d82465a`; each file must match its frozen
SHA-256 or bootstrap stops.

## M. RTX 3090 qualification and parallelism

```powershell
powershell -ExecutionPolicy Bypass -File scripts\bootstrap_training_machine.ps1 -Action Qualify -Apply
powershell -ExecutionPolicy Bypass -File scripts\run_parallel_adapter_research.ps1 -Action BenchmarkProtocol
```

Default maximum is 1. Parallel=2 is blocked until the bounded one-vs-two process
benchmark shows at least 25% higher aggregate optimizer throughput and passes
VRAM, loss, freeze, integrity, OOM, collision, CPU/GPU, and I/O gates. Processes,
status paths, run directories, and checkpoints remain independent. Three or
four jobs are unsupported. Do not run GPU Large evaluation with training on the
same RTX 3090.

## N. Current training status

```text
FULL_ADAPTERS_COMPLETED = NONE ASSUMED
TRAINING_STARTED_BY_THIS_HANDOFF = NO
ONNX_EXPORT_STARTED = NO
LARGE_EVALUATION_STARTED = NO
```

## O. Future phase plan

1. Portable handoff and successor freeze.
2. Train eight Original adapters.
3. Export successful adapters and the reconstructed unadapted Original baseline.
4. Run frozen Large; do not create another Common Voice heldout benchmark.
5. Analyze historical Original, reconstructed Original, Giga baseline, and eight adapters.
6. Select approximately 2-3 data recipes and full-fine-tune only those.
7. Export and run frozen Large for full-fine-tuned candidates.
8. Select the best full-fine-tuned production candidate.

There is no mandatory TRAIN+DEV refit. A future Giga-native full-finetune
feasibility canary remains deferred and must use the legacy
`pruned_transducer_stateless7_streaming_multi` lineage; do not create a custom
legacy Giga adapter.

## P. Exact receiver input block

```text
Repository branch: codex/edge-component-expansion
Read: Software Validation from Datasets/Training Tool/handoff/training_handoff_state.json
Read: Software Validation from Datasets/Training Tool/handoff/training_handoff_data_inventory.json
Read: Software Validation from Datasets/Training Tool/handoff/training_handoff_machine_requirements.json
Read: Software Validation from Datasets/Training Tool/handoff/training_handoff_external_assets.json
Follow: Software Validation from Datasets/Training Tool/handoff/training_handoff_commands.md
Target: Windows + WSL2, NVIDIA RTX 3090 24 GB
Configure: JP_REPO_ROOT, JP_DATA_ROOT, JP_TRAINING_ROOT, JP_MODEL_ROOT, JP_RUN_ROOT, and JP_WSL_DISTRO
First actions: Diagnose; Configure -Apply; BootstrapEnvironment -Apply; acquire external data; MaterializeData -Apply; VerifyData; acquire-models; VerifyModels; Plan; Qualify -Apply; Validate; Estimate
Default MAX_PARALLEL_ADAPTER_JOBS: 1
Do not train until receiver qualification passes.
Do not run Large or export during bootstrap/qualification.
Do not add raw data, checkpoints, environments, Icefall, runs, or logs to Git.
```
