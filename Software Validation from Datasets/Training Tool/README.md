# Training Tool: Phase-2/3 data freezes and Phase-4 training manifests

## Purpose

The Phase-2 builder freezes a local inventory of speech metadata, licence/provenance policy, and an evaluation-leakage firewall. The Phase-3 workflow selectively prepares Common Voice and freezes its speaker-disjoint roles. The Phase-4 workflow creates deterministic framework-neutral TRAIN/DEV/MONITOR manifests from those immutable inputs. This is a research/compliance aid, not legal advice. None of these workflows installs Icefall, trains a model, changes the Evaluation Tool, or creates new evaluation sets.

The existing Just-Peachy evaluation universe remains test-only. Phase-4 training manifests select from the frozen registries rather than move or regenerate evaluation data.

## Inputs

- Normalized metadata and local licence files below `JP_DATA_ROOT` (default: `Software Validation from Datasets`).
- Every benchmark parquet beneath `Evaluation Tool/benchmarks` that has source identities. This includes the v1 Small, Standard, Large, speaker-protocol, and later source-identified benchmark material.
- [license_policy.v1.json](training_data/license_policy.v1.json), the versioned policy and evidence record.

The CMU Arctic entry is CC0-1.0 based on an operator-supplied local classification. Local files independently verify the LibriSpeech, HiFiTTS, and CHiME-6 entries. AMI preserves its locally bundled historical CC BY-NC-SA 2.5 `LICENCE.txt` as provenance, but the AMI maintainers relicensed the unchanged core corpus under CC BY 4.0 on 10 April 2017. The registry therefore uses CC BY 4.0 as AMI's effective current licence: intended-commercial training is allowed with attribution. CHiME-6 is technically eligible but review-gated; this is not a legal conclusion about model weights.

## Outputs

`build` writes ignored, machine-local outputs under `JP_TRAINING_ROOT` (default: `<repository>/training`):

- `registries/training_data_registry.parquet`: one normalized training candidate per source segment/item.
- `registries/evaluation_exclusion_index.parquet`: de-duplicated frozen evaluation identities and their benchmark references.
- `registries/*summary.json` and `training_data_freeze_manifest.json`: deterministic identities, statistics, licence-policy hash, and evaluation-manifest hashes.
- `audits/training_data_audit.json` and `audits/training_data_audit.md`: human and machine audit reports.
- `license_evidence/*.json`: compact licence/provenance records, with digests for local small licence files.

Absolute `resolved_audio_path` fields are diagnostic-only. They never participate in canonical hashes. `source_available` means the normalized metadata supplied a rebasable path; the freeze intentionally does not run a slow per-audio filesystem probe or hash raw audio.

For a policy correction, preserve the existing freeze and build to a separate successor directory with `--parent-freeze`. The successor records the parent ID and hash in its own freeze manifest.

## Run from Anaconda Prompt, Command Prompt, or PowerShell

Use the repository virtual environment (or replace its Python executable with the Python from the activated Anaconda environment). Quote the directory because it contains spaces.

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Training Tool'
..\..\.venv\Scripts\python.exe -m training_data.cli build
..\..\.venv\Scripts\python.exe -m training_data.cli verify-freeze
..\..\.venv\Scripts\python.exe -m training_data.cli summary
..\..\.venv\Scripts\python.exe -m training_data.cli preview-pool robust_plus_chime
```

Create the AMI CC BY 4.0 correction successor without overwriting the historical Phase-2 output:

```powershell
$parent = '..\..\training\registries\training_data_freeze_manifest.json'
$successor = '..\..\training\successors\ami_cc_by_4_0_2017_04_10'
..\..\.venv\Scripts\python.exe -m training_data.cli build --output-root $successor --parent-freeze $parent --correction-reason ami_cc_by_4_0_relicensing_2017_04_10
..\..\.venv\Scripts\python.exe -m training_data.cli verify-freeze --path "$successor\registries\training_data_freeze_manifest.json"
```

To write data and generated registries somewhere other than the checkout, set the Phase-1 resolver inputs before running:

```powershell
$env:JP_DATA_ROOT = 'D:\just-peachy-data\Software Validation from Datasets'
$env:JP_TRAINING_ROOT = 'D:\just-peachy-training'
..\..\.venv\Scripts\python.exe -m training_data.cli build
```

On Linux or WSL:

```bash
cd '/work/just-peachy/Software Validation from Datasets/Training Tool'
../../.venv/bin/python -m training_data.cli build
../../.venv/bin/python -m training_data.cli verify-freeze
```

Inspect the Phase-1 roots first with:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
..\..\.venv\Scripts\python.exe -m app.utils.paths
```

## Leakage and future selection

`relaxed_training_eligible` excludes exact evaluation items and cross-dataset source matches. `strict_training_eligible` also excludes evaluation speaker, reader, meeting, session, or VOiCES source-speaker groups, depending on the dataset. Strict is the default for future model-selection research.

VOiCES original-source identifiers are normalized to the corresponding LibriSpeech speaker/chapter/segment identity when available, so a retransmission and its direct source cannot cross the firewall. HiFiTTS and LibriSpeech share audiobook provenance, but the local metadata contains no reliable item-level crosswalk; the tool reports this limitation rather than inventing a match.

Future code can use `training_data.registry.select_records(frame, strict=True, commercial_policy='straightforward')`, or the `review_gated` policy for CHiME-6. This tool deliberately returns candidates only; it does not freeze a future split.

When Common Voice arrives, create a new additive registry/freeze version from this one plus its exact release. Do not overwrite this Phase-2 snapshot.

## Phase 3: pinned Common Voice English acquisition

Phase 3 pins **Common Voice Scripted Speech 26.0 - English**, locale `en`, corpus release `cv-corpus-26.0-2026-06-12`, released 2026-06-17. The official Mozilla Data Collective record identifies the dataset as `cmqim2hn800ssnr07gvmpcnwu`, licenses it under `CC0-1.0`, and publishes archive size `94,639,372,950` bytes and SHA-256 `6809228E6AB506D18F6A1EBC830056450F8266C8F513D6038BDB0FC88A49E6CB`.

The immutable release record is [common_voice_release.v1.json](training_data/common_voice_release.v1.json). [common_voice.py](training_data/common_voice.py) uses Mozilla's official `datacollective` Python SDK. The SDK resumes an interrupted download when its `.part` and `.checksum` state remain in the same directory. The wrapper refuses an unexpected filename, byte size, or SHA-256 and never stores or prints the API key.

Inputs:

- the existing `JP_TRAINING_ROOT` setting;
- an `MDC_API_KEY` supplied only through the current shell;
- the pinned Mozilla dataset ID and published archive identity.

Outputs, all ignored by Git, are beneath:

```text
<JP_TRAINING_ROOT>/datasets/common_voice/english/cv-corpus-26.0-2026-06-12/
  source/common-voice-scripted-speech-26-0-englis-c84784ae.tar.gz
  metadata/acquisition_manifest.json
```

This acquisition command does **not** extract the archive, select speakers, create splits, alter evaluation, or create a Phase-3 freeze. Those operations remain blocked until the exact archive verifies.

### One-time authenticated setup and continuation

1. Open the [official Mozilla dataset record](https://mozilladatacollective.com/datasets/cmqim2hn800ssnr07gvmpcnwu), sign in or create an account, read and accept the dataset conditions, and confirm the Common Voice prohibitions on speaker identification and redistribution.
2. In Mozilla Data Collective, open **Account -> Credentials** and create or retrieve an API key.
3. In Anaconda Prompt or PowerShell, run the following. Do not put the key in a `.env` file inside this repository and do not commit it.

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Training Tool'
..\..\.venv\Scripts\python.exe -m pip install datacollective
$env:MDC_API_KEY = Read-Host 'Mozilla Data Collective API key'
..\..\.venv\Scripts\python.exe -m training_data.common_voice status
..\..\.venv\Scripts\python.exe -m training_data.common_voice acquire
```

In classic Anaconda Prompt (`cmd.exe`), use `set /p MDC_API_KEY=Mozilla Data Collective API key:` instead of the PowerShell `Read-Host` line. Rerun the same `acquire` command after any interruption; the official SDK resumes automatically. After it reports `download_complete: true`, continue Phase 3 with archive extraction, real metadata/age-schema inspection, older-speaker selection, leakage checks, speaker-disjoint splits, and a successor freeze derived from `training_freeze_7a88aec7492f`.

Before authentication, the safe diagnostic command is:

```powershell
..\..\.venv\Scripts\python.exe -m training_data.common_voice status
```

### Selectively prepare an operator-downloaded archive

When the authenticated archive already exists under `JP_DATA_ROOT/Raw Datasets (Not formatted)`, it may have an operator-friendly local name such as `Common Voice.gz`. The local filename is not scientific identity: the Phase-3 workflow discovers the single size-matching file, detects gzip from its content, and accepts it only after the compressed SHA-256 exactly matches the pinned Mozilla archive.

The workflow performs two sequential archive traversals:

1. verify the complete compressed SHA-256 while indexing members and preserving the original metadata files;
2. extract every missing validated age>=60 MP3 in one streaming traversal.

It does not full-extract Common Voice and does not reopen the archive once per clip. The selected MP3s and resume state are stored beneath `JP_TRAINING_ROOT`:

```text
<JP_TRAINING_ROOT>/datasets/common_voice/english/cv-corpus-26.0-2026-06-12/prepared/en/
  metadata/original/
  metadata/derived/
  clips/
  state/
```

The additive Phase-3 registry, audits, membership manifest, license evidence, and freeze are written beneath:

```text
<JP_TRAINING_ROOT>/successors/common_voice_26_english_phase3/
```

Run from Anaconda Prompt or PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Training Tool'
..\..\.venv\Scripts\python.exe -m training_data.common_voice phase3-status
..\..\.venv\Scripts\python.exe -m training_data.common_voice phase3-run
..\..\.venv\Scripts\python.exe -m training_data.common_voice phase3-verify
```

`phase3-run` is resumable. A completed source audit is reused when its pinned identity and metadata are present. During selective materialization, completed MP3s and their validation rows are reused; a rerun makes one archive pass only for missing selected members. The workflow also hashes every source-audio file referenced by the frozen evaluation exclusion index, stores a portable content-hash-index identity in the successor freeze, and caches file hashes by size and modification time for later reruns. Inputs are the verified source archive, corrected Phase-2 freeze, Phase-2 registry, evaluation exclusion index, and the evaluation audio it references. Outputs are selected original MP3s, exact original TSVs, derived Parquet registries, deterministic train/dev/heldout membership, audits, pool previews, and an immutable successor freeze. No Icefall installation, training manifest, model training, inference, or ONNX export occurs.

## Test

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Training Tool'
..\..\.venv\Scripts\python.exe -m pytest -q tests
```

## Phase 4: deterministic training manifests and sampling bundles

Phase 4 turns the immutable Phase-3 data universe into framework-neutral TRAIN,
DEV, and MONITOR manifests. It does not install Icefall or k2, extract features,
train or fine-tune a model, export ONNX, or run an Evaluation Tool campaign.

Inputs:

- the verified Phase-3 freeze `training_freeze_phase3_086685615728` and its
  frozen Common Voice registry/split;
- the corrected Phase-2 registry and evaluation-exclusion index;
- the existing deployed Original Sherpa and LibriSpeech+GigaSpeech Sherpa ONNX
  assets, read only to record exact deployment hashes and lineage references;
- the existing frozen evaluation manifests and scenario catalogs, read only for
  an immutability audit.

Outputs are ignored local metadata below
`<JP_TRAINING_ROOT>/successors/phase4_training_manifests_v1/`:

- `source_manifests/`: deterministic AGE, AMI, CHiME, VOiCES, and exploratory
  CMU TRAIN Parquets plus the explicit empty strict-CMU descriptor;
- `development/`: deterministic per-source DEV Parquets;
- `monitoring/`: an approximately five-hour, broad-speaker LibriSpeech clean
  regression monitor that is never gradient eligible;
- `policies/`: source grouping, rotating acoustic-view, speaker balancing,
  square-root dataset weighting, DEV/checkpoint, CMU interpretation, Large-use,
  and licence propagation policies;
- `bundles/`: eight immutable source-reference bundles, including the three
  combined bundles and their full-precision weights;
- `registries/`: the 12-row model plan, initialization references, summary, and
  immutable Phase-4 successor freeze;
- `audits/`: split overlap, sampling, dataset contribution, heldout, monitor,
  structure, and before/after immutability evidence.

Canonical IDs use logical roots plus relative paths. Physical absolute paths are
excluded from source manifests, policy and bundle hashes, and the Phase-4 freeze.
AMI and VOiCES source speech is counted once regardless of microphone or
retransmission view count. CHiME rows are treated according to the observed
registry structure: one canonical utterance row, not 48 fabricated views.

Run from Anaconda Prompt, Command Prompt, or PowerShell with the repository
environment (or replace the executable with the Python from an activated
Anaconda environment):

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Training Tool'
..\..\.venv\Scripts\python.exe -m training_data.phase4 status
..\..\.venv\Scripts\python.exe -m training_data.phase4 run
..\..\.venv\Scripts\python.exe -m training_data.phase4 verify
```

In classic Anaconda Prompt (`cmd.exe`), the same commands work after:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Training Tool"
..\..\.venv\Scripts\python.exe -m training_data.phase4 status
..\..\.venv\Scripts\python.exe -m training_data.phase4 run
..\..\.venv\Scripts\python.exe -m training_data.phase4 verify
```

Portable overrides use the existing Phase-1 resolver; no second path system is
introduced:

```powershell
$env:JP_REPO_ROOT = 'D:\checkouts\just-peachy'
$env:JP_DATA_ROOT = 'D:\just-peachy-data\Software Validation from Datasets'
$env:JP_TRAINING_ROOT = 'D:\just-peachy-training'
$env:JP_MODEL_ROOT = 'D:\just-peachy-models'
..\..\.venv\Scripts\python.exe -m training_data.phase4 status
```

`run` refuses to replace a valid existing Phase-4 freeze. A future scientific
change must use a new additive successor/version rather than mutating this one.

## Phase 5: Original Zipformer2 adapter training

### Purpose and scope

Phase 5 qualifies and trains only the Original LibriSpeech-lineage Zipformer2
checkpoint with Icefall's official residual adapter implementation. It creates
no Giga job, custom legacy adapter, full-model fine-tune, ONNX export, Large
campaign, Common Voice heldout evaluation, or general rehearsal. The Giga
baseline remains evaluation-only; the future decision gate is recorded in
[future_giga_decision.md](docs/future_giga_decision.md).

The deployed Original ONNX files are not byte-identical to the presently
published upstream ONNX files. Official source documentation, architecture and
tokenizer identity, a complete structural checkpoint load, and a fixed five-item
continuity smoke support
`strong_lineage_requires_reconstructed_baseline`. Phase 6 must therefore export
the unadapted trainable checkpoint through the same export pipeline as the
adapters, and Phase 7 must use that reconstruction as the primary adaptation
baseline.

### Inputs

- Phase-4 freeze `training_manifest_freeze_phase4_cc2909f344d0`, SHA-256
  `CC2909F344D01E9007EF648BA71277188DF26741CBEA5D1D2B0933116CE6DF92`.
- The eight immutable Phase-4 bundle descriptors and their exact sampler,
  speaker-balancing, acoustic-view, DEV, monitor, CMU, and licence policies.
- Original checkpoint
  `JP_TRAINING_ROOT:checkpoints/upstream/original/pretrained.pt`, SHA-256
  `E44BB7C8D3985A7CF0089020D227AECD71E323DCAAABCAED90E4A792E1385342`.
- SentencePiece BPE-500 model, SHA-256
  `C53433DE083C4A6AD12D034550EF22DE68CEC62C4F58932A7B6B8B2F1E743FA5`.
- Icefall commit `3f848bb6d0acc970c9b294a30ca0a04a7c9c78d1`, specifically
  `egs/librispeech/ASR/zipformer_adapter`.
- WSL2 Ubuntu, an NVIDIA CUDA-capable GPU, and local Phase-4 audio.

The tracked, self-hashed configuration files are:

- [original_adapter_recipe.v1.json](configs/original_adapter_recipe.v1.json)
- [original_adapter_budget_policy.v1.json](configs/original_adapter_budget_policy.v1.json)
- [original_adapter_environment_lock.v1.json](configs/original_adapter_environment_lock.v1.json)
- [original_adapter_provenance.v1.json](configs/original_adapter_provenance.v1.json)

After the implementation commit is created, the small
`configs/original_adapter_system_commit.v1.json` lock records that exact source
commit for the later Phase-6 handoff. It is intentionally added in a metadata-
only follow-up commit so it can name the immutable implementation commit without
a self-reference.

### Outputs

All model/data-sized outputs remain ignored beneath `JP_TRAINING_ROOT`:

```text
successors/phase5_original_adapter_training_v1/
  audits/framework_manifest_audit.json
  framework_manifests/{train,dev,monitor}/
  qualification/canaries/{O-AGE,O-AGE-ROBUST}/
  qualification/canary_summary.json
  registries/original_adapter_queue.json
  queue_status.json
  phase5_original_adapter_training_completion.{json,md}
runs/adapters/<training-run-id>/
  checkpoint-step-*.pt
  result.json
```

Derived Parquets retain every Phase-4 row and bind their source manifest, bundle,
parent freeze, sampler, and text-normalization identities. AMI and CHiME temporal
segments are joined from the normalized metadata. Blank/punctuation-only AMI
transcripts remain explicit blank transducer targets and are counted; they are
not dropped or assigned invented text. One reversed CHiME DEV endpoint is swapped
in the derived copy with the correction recorded. Two Common Voice raw transcript
fields contain embedded TSV metadata tails; the raw evidence and rows remain
unchanged, while only the derived recipe targets use the non-empty first TSV
field and record that correction. Tokenization audit must report zero failures
and zero `<unk>` tokens before training. Microbatch accounting uses the larger
of source duration, one second, or 0.05 seconds per BPE token, so mandatory
transducer padding cannot silently exceed the frozen duration budget.

Checkpoints contain adapter weights, optimizer, scheduler, FP16 scaler, global
step, exact sampler event, cumulative elapsed time, Python/Torch/CUDA RNG state,
budget state, best-DEV state, and the frozen-backbone digest. Full checkpoints
are reconstructed from
the immutable initialization plus the adapter state; the 66.1M-parameter
backbone is not duplicated in every file.

The Eden batch schedule advances every optimizer step. Its epoch schedule
advances only after a completed deterministic effective-source pass, where one
pass is the frozen weighted unique-source audio mass divided by the 90-second
effective batch target. This preserves the upstream epoch semantics for the
infinite deterministic sampler without inventing filesystem-sized epochs.

### One-time WSL/CUDA environment setup

The qualified machine uses a dedicated Python 3.11 environment at
`/home/amiri/.local/share/just-peachy/envs/original_adapter_training` and a
Linux-native Icefall checkout at
`/home/amiri/.local/share/just-peachy/toolchains/icefall`. Do not install these
packages into an Evaluation Tool environment.

From PowerShell, after installing Miniforge for the WSL user, run:

```powershell
wsl -d Ubuntu -- /home/amiri/.local/share/just-peachy/miniforge3/bin/conda create -y -p /home/amiri/.local/share/just-peachy/envs/original_adapter_training python=3.11 pip ffmpeg sox libsndfile git

$WslPython = '/home/amiri/.local/share/just-peachy/envs/original_adapter_training/bin/python'
wsl -d Ubuntu -- $WslPython -m pip install torch==2.11.0+cu126 torchaudio==2.11.0+cu126 --index-url https://download.pytorch.org/whl/cu126
wsl -d Ubuntu -- $WslPython -m pip install 'k2==1.24.4.dev20260625+cuda12.6.torch2.11.0' -f https://k2-fsa.github.io/k2/cuda.html
wsl -d Ubuntu -- $WslPython -m pip install -r '/mnt/c/Users/amiri/Documents/GitHub/just-peachy/Software Validation from Datasets/Training Tool/requirements.original_adapter_training.txt'

wsl -d Ubuntu -- git clone --filter=blob:none https://github.com/k2-fsa/icefall.git /home/amiri/.local/share/just-peachy/toolchains/icefall
wsl -d Ubuntu -- git -C /home/amiri/.local/share/just-peachy/toolchains/icefall checkout --detach 3f848bb6d0acc970c9b294a30ca0a04a7c9c78d1
```

From Anaconda Prompt or Command Prompt, use the equivalent commands without a
PowerShell variable:

```bat
wsl -d Ubuntu -- /home/amiri/.local/share/just-peachy/miniforge3/bin/conda create -y -p /home/amiri/.local/share/just-peachy/envs/original_adapter_training python=3.11 pip ffmpeg sox libsndfile git
wsl -d Ubuntu -- /home/amiri/.local/share/just-peachy/envs/original_adapter_training/bin/python -m pip install torch==2.11.0+cu126 torchaudio==2.11.0+cu126 --index-url https://download.pytorch.org/whl/cu126
wsl -d Ubuntu -- /home/amiri/.local/share/just-peachy/envs/original_adapter_training/bin/python -m pip install k2==1.24.4.dev20260625+cuda12.6.torch2.11.0 -f https://k2-fsa.github.io/k2/cuda.html
wsl -d Ubuntu -- /home/amiri/.local/share/just-peachy/envs/original_adapter_training/bin/python -m pip install -r "/mnt/c/Users/amiri/Documents/GitHub/just-peachy/Software Validation from Datasets/Training Tool/requirements.original_adapter_training.txt"
wsl -d Ubuntu -- git clone --filter=blob:none https://github.com/k2-fsa/icefall.git /home/amiri/.local/share/just-peachy/toolchains/icefall
wsl -d Ubuntu -- git -C /home/amiri/.local/share/just-peachy/toolchains/icefall checkout --detach 3f848bb6d0acc970c9b294a30ca0a04a7c9c78d1
```

Verify the exact GPU runtime:

```powershell
wsl -d Ubuntu -- $WslPython -c "import torch,k2,lhotse,sentencepiece; print(torch.__version__, torch.version.cuda, torch.cuda.is_available(), torch.cuda.get_device_name(0)); print(getattr(k2, '__dev_version__', 'unknown'), lhotse.__version__, sentencepiece.__version__)"
```

In Anaconda Prompt or Command Prompt, replace `$WslPython` in that verification
command with
`/home/amiri/.local/share/just-peachy/envs/original_adapter_training/bin/python`.

The frozen qualification is Python 3.11.15, PyTorch 2.11.0+cu126, CUDA 12.6,
cuDNN 9.10.2.21, k2
1.24.4.dev20260625+cuda12.6.torch2.11.0, Lhotse 1.33.0, and
SentencePiece 0.2.1 on an NVIDIA GeForce RTX 3080. A different environment is a
result-affecting change and requires a new lock/recipe identity.

### Run from repository root

The PowerShell front door performs routine WSL invocation. The operator does not
activate WSL or enter Linux commands:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy'
$Runner = 'Software Validation from Datasets\Training Tool\scripts\run_adapter_research.ps1'

powershell -ExecutionPolicy Bypass -File $Runner -Action Plan
powershell -ExecutionPolicy Bypass -File $Runner -Action Estimate
powershell -ExecutionPolicy Bypass -File $Runner -Action Run
powershell -ExecutionPolicy Bypass -File $Runner -Action RunOne -ExperimentId O-AGE
powershell -ExecutionPolicy Bypass -File $Runner -Action Status
powershell -ExecutionPolicy Bypass -File $Runner -Action Watch -RefreshSeconds 30
powershell -ExecutionPolicy Bypass -File $Runner -Action Stop -Reason 'operator request'
powershell -ExecutionPolicy Bypass -File $Runner -Action Resume
powershell -ExecutionPolicy Bypass -File $Runner -Action Validate
powershell -ExecutionPolicy Bypass -File $Runner -Action Results
```

`Plan` verifies the parent and initialization, builds derived manifests, audits
all audio/segments/text/tokenization, derives one deterministic budget for each
bundle, and writes exactly eight Original jobs in strict-before-exploratory
order. `Estimate` refuses to invent an ETA before both canaries provide measured
throughput. It reports the mean measured point estimate with fixed 0.80x low and
1.35x high duration bounds. `Run` skips already successful jobs and starts every
remaining job in a fresh WSL process. `Stop` writes a controlled request; the
runtime checkpoints
at the next optimizer boundary. `Resume` removes that request and restores the
latest complete checkpoint. `Validate` checks every readiness gate. `Results`
creates the JSON/Markdown completion artifacts and the exact Phase-6 input block.

The two 250-step canaries are qualification artifacts, not final research runs.
They use fixed, bounded DEV and monitor panels only. Full jobs use their complete
Phase-4 DEV objective and complete clean monitor at the frozen intervals. The
monitor never supplies gradients or chooses a checkpoint.

### Phase-5 tests

From Anaconda Prompt, Command Prompt, or PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Training Tool'
..\..\.venv\Scripts\python.exe -m pytest -q tests\test_adapter_research.py
..\..\.venv\Scripts\python.exe -m pytest -q tests
..\..\.venv\Scripts\python.exe -m ruff check training_data tests
..\..\.venv\Scripts\python.exe -m compileall -q training_data tests
```

The live canaries additionally exercise the CUDA-only checkpoint load, official
adapter construction, FP16 forward/backward, adapter-only optimizer, full
backbone hash, adapter change, save/reload, resume state, DEV/monitor decode,
sampler behavior, GPU use, and peak VRAM gates.
