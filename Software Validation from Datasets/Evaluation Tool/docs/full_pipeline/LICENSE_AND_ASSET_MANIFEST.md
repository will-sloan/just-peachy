# Full Speech-Pipeline License and Asset Manifest

- Program: `just_peachy_full_pipeline_program_v1`
- Protocol: `full_pipeline_protocol.v1`
- Matrix: `configs/automated_evaluation/full_pipeline_matrix.v1.yaml`
- Matrix cardinality: 18 logical pipelines (`2 ASR x 3 anonymous diarization x 3 identity`)
- Scope: local repository records and locally installed package metadata only; no external legal or commercial clearance is asserted.

## Eligibility rule

Technical eligibility and deployment eligibility are independent axes.

- **Technical eligibility** answers whether the exact local component has resolved assets, a qualified runtime path, and a usable scientific contract.
- **Licensing/provenance deployment eligibility** answers whether the repository records support shipping the code and checkpoint for the intended use.
- A technically qualified component may still require attribution, gated acquisition, redistribution review, or commercial review.
- A technically strong pipeline is not a production candidate unless every component in that pipeline independently passes deployment review.
- Running the internal 18-pipeline research matrix does not authorize redistribution of repository code, packages, checkpoints, source archives, or training data.

The repository root has no `LICENSE`, `COPYING`, or `NOTICE` file. Therefore the Just-Peachy repository code as a whole has **no locally established redistribution grant**. Licenses found inside third-party model caches apply to those third-party assets, not to the repository as a whole.

## Status summary

| Component | Exact technical identity | Technical eligibility | Recorded license/provenance status | Deployment eligibility |
|---|---|---|---|---|
| Just-Peachy repository code | Current working tree implementing `full_pipeline_protocol.v1` | Eligible for local research execution | No repository-level license file | **Unresolved; do not redistribute as a licensed package** |
| Sherpa-ONNX runtime | `sherpa-onnx==1.13.4`, `onnx` profile | Qualified | Apache-licensed runtime in installed metadata and registries | Eligible only with applicable Apache license/notice review |
| AO Original Sherpa checkpoint | `sherpa-onnx-streaming-zipformer-en-2023-06-26` | Qualified | Archive/source release recorded; exact training provenance and archive redistribution terms unresolved | **Redistribution/commercial review required** |
| AG Sherpa Giga checkpoint | `sherpa_onnx_libri_giga_zipformer_2023_06_21` | Qualified under current segment contract | Apache-2.0 weights/runtime; LibriSpeech + GigaSpeech provenance | **Commercial deployment review required because of GigaSpeech** |
| `pyannote.audio` runtime | `pyannote.audio==4.0.7`, `credential-diarization` profile | Qualified for the bounded modular path | Package license is not separately stated by the selected repository registries; installed package metadata has no license field | **Code redistribution review required** |
| Pyannote Segmentation 3.0 | revision `e66f3d3b9eb0873085418a7b813d3b369bf160bb` | Qualified shared segmentation asset | MIT checkpoint; gated Hugging Face acquisition | Conditional on accepted gated terms and redistribution review |
| Agglomerative clustering | `scikit-learn==1.7.2`, cosine agglomerative policy | Technically resolved | Installed package metadata records `BSD-3-Clause`; no model/checkpoint | Eligible with BSD notice/license preservation review |
| WeSpeaker code | commit `1d4164bdb1dcfee4624093190fd5ecbb19447686` | Qualified with warnings | Apache-2.0 code | Eligible with Apache notice/license review |
| WeSpeaker checkpoint | `voxceleb_resnet221_LM` | Qualified with warnings | CC BY 4.0 pretrained weight; VoxCeleb2-dev provenance | **Attribution required** |
| ReDimNet2 code | commit `cdc875670034dd7068013ca2ab21ec083a040ff8` | Qualified | MIT | Eligible with MIT license text preserved |
| ReDimNet2-B2 checkpoint | official `b2-vox2-lm.pt`, release `v1.0.0` | Qualified | MIT; VoxCeleb2-dev; native checkpoint, no conversion | Eligible under the recorded MIT disposition |
| SpeechBrain code | `speechbrain==1.1.0` | Qualified on CPU | Apache-2.0 code | Eligible with Apache notice/license review |
| SpeechBrain ECAPA checkpoint | `speechbrain/spkrec-ecapa-voxceleb`, revision `0f99f2d0ebe89ac095bcc5903c4dd8f72b367286` | Qualified on CPU | No license copied into the local checkpoint cache; exact checkpoint/data redistribution terms unresolved | **Checkpoint redistribution/commercial review required** |

## 1. Just-Peachy repository code

- **Code identity:** the repository code that defines `just_peachy_full_pipeline_program_v1` and the 18-pipeline matrix.
- **Code license:** unresolved. There is no repository-root `LICENSE`, `COPYING`, or `NOTICE` file.
- **Checkpoint/data provenance:** not applicable to repository-authored code; third-party assets are listed separately below.
- **Attribution requirement:** no repository-authored attribution terms are locally declared because no repository license is present.
- **Redistribution review:** required before publishing, packaging, sublicensing, or shipping the repository code.
- **Gated acquisition:** no.
- **Unresolved commercial issue:** the absence of a repository license prevents a local conclusion about commercial redistribution rights.
- **Acquisition path:** the existing Git working tree at `C:\Users\amiri\Documents\GitHub\just-peachy`.
- **Deployability:** local technical research is permitted by project practice; redistribution or product packaging is not cleared by this manifest.

## 2. Sherpa-ONNX runtime

- **Package:** `sherpa-onnx==1.13.4`.
- **Environment:** `.stage8-envs/onnx`; current Python `3.12.7`, 68-package freeze SHA-256 `d88638b4955ab0dada065ef0821ece33a8f02764c1c40946f99b753ce9219b16`.
- **Requirement:** `requirements/stage8/onnx.txt`, SHA-256 `2da35d518b59776b6bdbedf3172d39a218aadb81434ff49ca5cf55d89b1972e7`.
- **Code license:** the installed package metadata and repository registries record an Apache-licensed runtime.
- **Checkpoint/data provenance:** none; AO and AG are separate assets below.
- **Attribution requirement:** preserve and review the applicable Apache license and notices when redistributing the runtime. No additional project-specific attribution text is recorded locally.
- **Redistribution review:** routine third-party package review remains required for a shipped product.
- **Gated acquisition:** no.
- **Acquisition path:** `powershell -ExecutionPolicy Bypass -File scripts\install_stage8_profile.ps1 -Profile onnx -DownloadModels`.
- **Deployability:** runtime is technically qualified; checkpoint-specific restrictions still control each ASR configuration.

## 3. AO — Original Sherpa ASR asset

- **Component:** `sherpa_onnx`; registry ID `asr.sherpa_onnx`.
- **Config:** `configs/inference/components/asr/sherpa_onnx.yaml`, SHA-256 `8c1f86cffea8a497aed699445e00329089ff0baebf08595f606fba263fbb2748`.
- **Model:** `sherpa-onnx-streaming-zipformer-en-2023-06-26`; mono 16 kHz, mixed INT8/FP32.
- **Source:** the Sherpa-ONNX ASR model release recorded by `model_asset_registry.v1.yaml`.
- **Source archive:** `models/cache/downloads/sherpa-onnx-streaming-zipformer-en-2023-06-26.tar.bz2`, 310,414,022 bytes, SHA-256 `639e25b578e9e997131402199419c13a941f8e4e198e2da1ce57dbf5cf401282`.
- **Installed tree:** `models/cache/sherpa_onnx/asr/sherpa-onnx-streaming-zipformer-en-2023-06-26`, 335,746,916 bytes, observed tree SHA-256 `5950412343bc8b76fe8c8de484f202514f579e69a5d837f21b5361472a1ab448`.
- **Result-affecting files:**
  - `tokens.txt`: 5,048 bytes, SHA-256 `49e3c2646595fd907228b3c6787069658f67b17377c60aeb8619c4551b2316fb`.
  - `encoder-epoch-99-avg-1-chunk-16-left-128.int8.onnx`: 70,108,816 bytes, SHA-256 `5022b2eca5b19d1bc104fcf33e26bc32604b7df553cd2e1f62e31dc7b05e9c87`.
  - `decoder-epoch-99-avg-1-chunk-16-left-128.onnx`: 2,093,080 bytes, SHA-256 `85914f840b71110487ece7a30ebd0bd4b8fb5c2623215bba3aa5ab4c138fc591`.
  - `joiner-epoch-99-avg-1-chunk-16-left-128.int8.onnx`: 259,416 bytes, SHA-256 `abd5e30f3f16fc510605c6029dba33f10e4386bd75c5bdc30cf94076864db10d`.
- **Code license:** Sherpa-ONNX runtime is recorded as Apache-2.0/Apache licensed.
- **Checkpoint/data provenance:** the release and archive are pinned, but the exact upstream model revision and training corpora are not recorded locally.
- **Attribution requirement:** runtime Apache notices apply; model-specific attribution is not conclusively recorded.
- **Redistribution review:** required. The model registry explicitly says to verify the model archive terms before redistribution.
- **Gated acquisition:** no.
- **Unresolved commercial issue:** exact training provenance and model-archive commercial redistribution clearance are unresolved.
- **Acquisition path:** `scripts/bootstrap_models.py --sherpa-asr`.
- **Deployability:** `TECHNICAL_USE_ALLOWED_REDISTRIBUTION_REVIEW_REQUIRED`.

The source-archive SHA and installed-tree SHA have different scopes and are both authoritative for their stated object. They are not a hash mismatch.

## 4. AG — Sherpa LibriSpeech + GigaSpeech ASR asset

- **Component:** `sherpa_onnx_libri_giga_zipformer_2023_06_21`; registry ID `asr.sherpa_onnx_libri_giga_zipformer_2023_06_21`.
- **Config:** `configs/inference/components/asr/sherpa_onnx_libri_giga_zipformer_2023_06_21.yaml`, SHA-256 `a9d5b6788f2a3fd3855520bb7e26aa9bc1ba95c75e563df68a78e21c494cfae8`.
- **Model:** `csukuangfj/sherpa-onnx-streaming-zipformer-en-2023-06-21`.
- **Upstream revision:** `9a65b6ea94c311ca770c2bf895b30f456a22d703`.
- **Source checkpoint:** `marcoyang/icefall-libri-giga-pruned-transducer-stateless7-streaming-2023-04-04`, revision `df8a1ee67abb67244b87d8011ec64ba46c6e97c0`.
- **Training corpora recorded locally:** LibriSpeech and GigaSpeech.
- **Source archive:** `models/cache/downloads/sherpa-onnx-streaming-zipformer-en-2023-06-21.tar.bz2`, 506,956,414 bytes, SHA-256 `455f40e556aa2b20ac9d3bffd603b58002075c1193b4070938540c11efe0a4da`.
- **Installed tree:** `models/cache/sherpa_onnx/asr/sherpa-onnx-streaming-zipformer-en-2023-06-21`, 546,279,902 bytes, SHA-256 `8ad24aa63b28ffb15a5b91461e4d05b19e3237c3f5ca7a6d3557d0fac0a9dfdf`.
- **Result-affecting files:**
  - `tokens.txt`: SHA-256 `49e3c2646595fd907228b3c6787069658f67b17377c60aeb8619c4551b2316fb`.
  - `encoder-epoch-99-avg-1.int8.onnx`: SHA-256 `32c98281c7bd8b63e3e142d007251b37f120572e8fdea9a4f5a79ce22b10ec4f`.
  - `decoder-epoch-99-avg-1.onnx`: SHA-256 `9da02b77cb08826756ec6a88635f35a40374e4164e7c6359121a9145958a6ceb`.
  - `joiner-epoch-99-avg-1.int8.onnx`: SHA-256 `831477d390e59a61f1b6a6f763b9903e6c6366ff6034f1ddba613be82637122f`.
- **Code/checkpoint license:** Apache-2.0 runtime and weights are recorded locally.
- **Checkpoint/data provenance:** official Sherpa-ONNX conversion from the cited Icefall LibriSpeech + GigaSpeech checkpoint.
- **Attribution requirement:** preserve applicable Apache license/notices; no additional repository-authored attribution text is recorded.
- **Redistribution review:** required for the complete archive and its provenance chain.
- **Gated acquisition:** no.
- **Unresolved commercial issue:** GigaSpeech training provenance requires a separate commercial deployment review.
- **Acquisition path:** `scripts/bootstrap_models.py --sherpa-libri-giga`.
- **Deployability:** `COMMERCIAL_DEPLOYMENT_REVIEW_REQUIRED_GIGASPEECH_PROVENANCE`. AG must not be described as commercially cleared.

## 5. Pyannote runtime and shared Segmentation 3.0 asset

### `pyannote.audio` code

- **Package:** `pyannote.audio==4.0.7`.
- **Environment:** `.stage8-envs/credential-diarization`; current Python `3.12.7`, 118-package freeze SHA-256 `341562b3f910676d5b02b3c55ea09dab54ed05d67c71dfc898d562da3ddff960`.
- **Requirement:** `requirements/stage8/credential-diarization.txt`, SHA-256 `cf232966ccbb4eaa1c9e972c1513635f12a0d6e18e2cf4421737cf3fb30d6149`.
- **Code license:** not separately established by the selected repository registries; the currently installed distribution metadata has no `License` or `License-Expression` field. The checkpoint's MIT license must not be used as a substitute for the runtime code license.
- **Attribution/redistribution:** code-license and notice review required before bundling the runtime.
- **Gated acquisition:** package installation is not the scientific asset gate; the checkpoint acquisition below is gated.
- **Acquisition path:** `scripts/install_stage8_profile.ps1 -Profile credential-diarization -DownloadModels` after the required personal terms/credential setup.
- **Deployability:** technically qualified for the modular path; runtime redistribution remains under review.

### `pyannote/segmentation-3.0` checkpoint

- **Asset ID:** `pyannote_segmentation_3_0`.
- **Revision:** `e66f3d3b9eb0873085418a7b813d3b369bf160bb`.
- **Storage:** `models/cache/pyannote/segmentation-3.0`.
- **Installed tree:** 5,982,542 bytes, SHA-256 `0bd17acc0afbd3ae9b78f0ac2912d660297d59d9c107cf75bb75b39dcb8c7e14`.
- **Files:**
  - `config.yaml`: 399 bytes, SHA-256 `fa65a47a751602f04cc570135007d76859b69e8f9f1bfdf5878a5145980d4263`.
  - `pytorch_model.bin`: 5,905,440 bytes, SHA-256 `da85c29829d4002daedd676e012936488234d9255e65e86dfab9bec6b1729298`.
- **Checkpoint license:** MIT, supported by the cached checkpoint `LICENSE` and model asset registry.
- **Data provenance:** no separate training-corpus declaration is recorded in the selected local asset registry.
- **Attribution requirement:** preserve the MIT license/copyright notice; no additional local attribution text is declared.
- **Redistribution review:** required despite the MIT record because acquisition is gated and accepted access terms must be honored.
- **Gated acquisition:** yes; `huggingface_cli_login_for_acquisition` and personal acceptance are required.
- **Acquisition path:** `hf auth login`, then `scripts/bootstrap_models.py --pyannote`.
- **Deployability:** `MIT_GATED_ACQUISITION_DO_NOT_REDISTRIBUTE_WITHOUT_REVIEW`.

DW, DR, and DE all reuse this exact segmentation asset. Their per-record `segmentation_cache_sha256` values are cache-result identities, not checkpoint hashes, and must not replace the installed-tree identity above.

## 6. Agglomerative cosine clustering

- **Implementation identity:** `agglomerative_cosine`, estimated speaker count, development-calibrated threshold `0.35` in DW, DR, and DE.
- **Package:** `scikit-learn==1.7.2`, pinned by `requirements/core.txt`, SHA-256 `c4e2c3730df95ac92ef13c74835865af28ac7343975b36ed8a1bc1ab3f7f0c51`.
- **Code license:** the installed distribution metadata records `BSD-3-Clause`.
- **Checkpoint/data provenance:** none; this is deterministic clustering code over extracted embeddings.
- **Attribution requirement:** preserve/review the BSD license and copyright notice when distributing the package. No Just-Peachy-specific attribution text is recorded.
- **Redistribution review:** routine third-party package review.
- **Gated acquisition:** no.
- **Unresolved commercial issue:** none recorded for this package; this does not resolve the licenses of its input embeddings or upstream checkpoints.
- **Acquisition path:** installed through the pinned core requirements used by the environment profiles.
- **Deployability:** technically and provisionally licensing-eligible with BSD notice preservation.

## 7. WeSpeaker code and `voxceleb_resnet221_LM`

### Code

- **Source revision:** `1d4164bdb1dcfee4624093190fd5ecbb19447686`.
- **Package identity:** installed metadata reports `wespeaker==0.0.0`; the immutable source commit is the meaningful identity.
- **Package requirement:** `requirements/stage8/wespeaker-package.txt`, SHA-256 `608b599990755f6b79cc397bb77f7fc1b8fd68f317f224a16e61a7fed35c56e8`.
- **Code license:** Apache-2.0, recorded by the component registry and installed package metadata.
- **Attribution/redistribution:** preserve/review applicable Apache license and notices.
- **Acquisition path:** the pinned Git requirement installed by `scripts/install_stage8_profile.ps1 -Profile wespeaker`.

### Checkpoint

- **Asset:** `wespeaker_voxceleb_resnet221_lm`; model `voxceleb_resnet221_LM`.
- **Training provenance:** VoxCeleb2-dev.
- **Storage:** `models/cache/wespeaker/english`.
- **Source archive:** `models/cache/downloads/voxceleb_resnet221_LM.tar.gz`, 105,902,456 bytes, SHA-256 `9462705bfafeed7b4a6585638a4d0140ddaf9338471198d014eb2579712f89f6`.
- **Installed tree:** 114,411,934 bytes, SHA-256 `bd70550dbfcdaecf387cefcc34d57d1b815fbdd6ee2d62477dd0e1eb176ff962`.
- **Files:**
  - `avg_model.pt`: 114,410,390 bytes, SHA-256 `47d76239f1e865b273e31e30f691959061ff6565ed6c4e7be9639a65d9662eb5`.
  - `config.yaml`: 1,544 bytes, SHA-256 `31511c8e6c60d96d40962e9a261dd8f752b01831b955192b5cbed8367276bbb5`.
- **Frozen backend identity:** model ID `wespeaker:d0a7906fde51`; model identity SHA-256 `e1bbaa057971bb48cce094b8f53ff9843818a1530c7f39d9b31aea002fb07f2a`; backend identity SHA-256 `290b28a5a517a4887692caef974abdab86fbbf12a8c76d486486dd18d0ce02f7`.
- **Checkpoint license:** CC BY 4.0 according to the current model asset registry and official-documentation evidence recorded there.
- **Attribution requirement:** mandatory CC BY 4.0 attribution for the pretrained weight. Record the model name, WeSpeaker source, checkpoint origin, and license in product notices.
- **Redistribution review:** confirm the notice/attribution package before shipping the weight. The shared VoxCeleb training-data name does not grant permission to redistribute source dataset audio, which is not part of this asset.
- **Gated acquisition:** no credential gate is recorded.
- **Unresolved commercial issue:** none beyond satisfying CC BY 4.0 attribution in the current registry disposition.
- **Acquisition path:** `scripts/bootstrap_models.py --wespeaker`.
- **Deployability:** `COMMERCIAL_PERMISSIVE_WITH_CC_BY_4_0_ATTRIBUTION`.

## 8. ReDimNet2 code and B2 VoxCeleb2 large-margin checkpoint

### Code

- **Source revision:** `cdc875670034dd7068013ca2ab21ec083a040ff8`.
- **Source archive:** `models/cache/downloads/redimnet2-cdc875670034dd7068013ca2ab21ec083a040ff8.tar.gz`, 1,118,945 bytes, SHA-256 `48ccf0de4d9a7a2f5c0aeccab7d286d1120ee2564074c7c2f7f38311ac8ff028`.
- **Installed source:** `models/cache/redimnet2/source-cdc875670034dd7068013ca2ab21ec083a040ff8`, tree SHA-256 `9ad9348bcb79c38e17e63ecd904bf79fac6dde05a3bf55afef9bad53a5ab3210`.
- **Code license:** MIT; the exact source cache includes `LICENSE`.
- **Attribution/redistribution:** preserve the MIT license/copyright notice.
- **Acquisition path:** `scripts/bootstrap_models.py --redimnet2-b2`.

### Checkpoint

- **Asset:** `redimnet2_b2_vox2_lm`; official native PalabraAI ReDimNet2-B2 VoxCeleb2 large-margin release `v1.0.0`.
- **Storage:** `models/cache/redimnet2/b2-vox2-lm.pt`.
- **File:** 15,897,450 bytes, SHA-256 `0545a29679a87fe1c662d2bbd05e3b3fe0d1b392832729abaa135e4079a2f77a`.
- **Conversion provenance:** official native PyTorch checkpoint; no conversion.
- **Training provenance:** VoxCeleb2-dev.
- **Frozen backend identity:** model ID `redimnet2_b2_speaker_embedding:11f2cbf70100`; model identity SHA-256 `c84ce9857dbc788cf5a65b22b044ddb1a37874158ce2168e80613e5036d1c678`; backend identity SHA-256 `3fa146871adb3336950a59f7e7cb5905fd209aa9b5126d6295a0109ee0a2e1d9`.
- **Checkpoint license:** MIT under the local model asset registry's recorded official repository/release disposition.
- **Attribution requirement:** preserve the MIT notice; no additional checkpoint attribution is locally declared.
- **Redistribution review:** verify the packaged source/checkpoint notices. Source VoxCeleb audio is not included or authorized for redistribution by this checkpoint record.
- **Gated acquisition:** no.
- **Unresolved commercial issue:** none recorded for the code/checkpoint license.
- **Deployability:** `COMMERCIAL_PERMISSIVE_MIT`.

## 9. SpeechBrain code and ECAPA checkpoint

### Code

- **Package:** `speechbrain==1.1.0`; Torch `2.11.0` in the `core-cpu` path.
- **Requirement:** `requirements/inference.txt`, SHA-256 `4116592807b9585cf1272904b26f4ba401bbfa125d3d11ed1bab28eec82c4c92`; the matrix binds `requirements/dev.txt`, SHA-256 `e5c49913957baf8bf807eab9367ff1b0ade1ade10f06a6c441ec8b9395a2e5e2`.
- **Code license:** installed package metadata and repository readiness records identify Apache-2.0.
- **Attribution/redistribution:** preserve/review applicable Apache license and notices.
- **Acquisition path:** installed through the core/dev inference requirements.

### Checkpoint

- **Source:** `speechbrain/spkrec-ecapa-voxceleb`.
- **Recorded source revision:** `0f99f2d0ebe89ac095bcc5903c4dd8f72b367286`.
- **Storage:** `models/cache/speechbrain/spkrec-ecapa-voxceleb`.
- **Files:**
  - `embedding_model.ckpt`: 83,316,686 bytes, SHA-256 `0575cb64845e6b9a10db9bcb74d5ac32b326b8dc90352671d345e2ee3d0126a2`.
  - `classifier.ckpt`: 5,534,328 bytes, SHA-256 `fd9e3634fe68bd0a427c95e354c0c677374f62b3f434e45b78599950d860d535`.
  - `hyperparams.yaml`: 1,919 bytes, SHA-256 `6f78854fa04ba59e761437b76a2575d3aba5e5016de3e9b69f0c9a5077fb1a41`.
  - `label_encoder.ckpt`: 128,619 bytes, SHA-256 `e13c3a167bb4112685670ee896d20e2b565af16b3a4ceeaa8689fa4d22adb8b9`.
  - `mean_var_norm_emb.ckpt`: 1,921 bytes, SHA-256 `cd70225b05b37be64fc5a95e24395d804231d43f74b2e1e5a513db7b69b34c33`.
- **Frozen backend identity:** model ID `speechbrain_ecapa:f47951032c81`; model identity SHA-256 `2744a8a1a4c9a4c810c436f5121315cc244436c46e25a717275b763ae0e42a3c`; backend identity SHA-256 `d64f6695332208cacdc6f22146d114f0b5cc2d27f445d344431f7ba1d161474f`.
- **Checkpoint/data provenance:** the source model name is recorded, but the selected local registries do not prove an exact training-corpus declaration or checkpoint redistribution license.
- **Checkpoint license:** unresolved. No license file is copied beside the five local files.
- **Attribution requirement:** unresolved for the checkpoint; SpeechBrain code's Apache notices do not establish checkpoint terms.
- **Redistribution review:** mandatory before shipping any of the five cache files.
- **Gated acquisition:** no credential gate is recorded; downloads remain disabled during scientific execution.
- **Unresolved commercial issue:** checkpoint and training-data commercial disposition is not established locally.
- **Acquisition path:** `scripts/bootstrap_models.py --speechbrain-ecapa`.
- **Deployability:** `TECHNICAL_USE_ALLOWED_CHECKPOINT_REDISTRIBUTION_REVIEW_REQUIRED`.

### SpeechBrain cache discrepancy

The frozen backend model identity covers `embedding_model.ckpt` and `hyperparams.yaml`, while the audited runtime cache contains the five files listed above. In addition, the cached `hyperparams.yaml` references `label_encoder.txt`, but the audited cache and environment registry record `label_encoder.ckpt`. Completed scientific extraction succeeded, so this is not evidence of a failed evaluation. It is an identity-coverage and filename discrepancy that must be resolved before a production asset freeze or redistribution package is declared complete.

The stale hash `0575CB012...` in `runs/research_readiness/speaker_research_readiness.md` must not be used. The observed file and authoritative component-registry hash is `0575cb64845e6b9a10db9bcb74d5ac32b326b8dc90352671d345e2ee3d0126a2`.

## Pipeline-level deployment implications

- All 18 pipelines depend on repository-authored code with no repository-level license, so none is currently cleared for external redistribution as a complete Just-Peachy product package.
- Every pipeline uses Pyannote Segmentation 3.0 and `pyannote.audio`; checkpoint acquisition is gated, and runtime code redistribution needs explicit review.
- Pipelines using IW or DW inherit the WeSpeaker CC BY 4.0 checkpoint-attribution requirement.
- Pipelines using IE or DE inherit the unresolved SpeechBrain checkpoint/cache review.
- Pipelines using IR or DR inherit the locally recorded MIT ReDimNet2 disposition.
- Every AG pipeline inherits the unresolved GigaSpeech commercial deployment review, independent of technical performance.
- Every AO pipeline inherits the unresolved model-archive/training-provenance redistribution review.
- Technical ranking and licensing/provenance ranking must remain separate. A technically superior pipeline with unresolved deployment rights cannot displace a cleared alternative on the production shortlist without an explicit legal/provenance decision.

## Reproducible acquisition and redistribution boundaries

- Scientific execution must use the pinned local paths and hashes above with implicit downloads disabled.
- Gated assets must be reacquired by an authorized user through the recorded acquisition route; access on one machine does not grant another person permission or authorize redistribution.
- No raw VoxCeleb, LibriSpeech, GigaSpeech, or other training audio is included in this manifest. A checkpoint's recorded license does not authorize redistribution of its source training corpus.
- Archive hashes, installed-tree hashes, and frozen backend identity hashes cover different objects. They must be stored with their scope and must not be substituted for one another.
- Any changed checkpoint, source revision, config, package environment, or license disposition requires a new asset review and a new result-affecting identity where applicable.

## Evidence anchors

- `configs/automated_evaluation/full_pipeline_matrix.v1.yaml`
- `configs/automated_evaluation/component_registry.v1.yaml`
- `configs/automated_evaluation/model_asset_registry.v1.yaml`
- `configs/automated_evaluation/environment_profiles.stage8.v1.yaml`
- `configs/automated_evaluation/environment_profiles.v1.yaml`
- `runs/extended_backend_qualification/model_asset_inventory.json`
- `runs/extended_backend_qualification/onnx.json`
- `runs/edge_backend_qualification/onnx-libri-giga.json`
- `runs/extended_backend_qualification/wespeaker.json`
- `runs/extended_backend_qualification/redimnet2.json`
- `runs/speaker_diarization_stack_qualification/credential_diarization_bounded.json`
- `JustPeachyResults/diarization_product_v2_development/frozen_diarization_development_selection.yaml`
- `JustPeachyResults/hybrid_speaker_attribution_product_v2_development/frozen_hybrid_product_v2_selection.yaml`
- `JustPeachyResults/hybrid_speaker_attribution_product_v2_final_evaluation/final_hybrid_product_v2_selection.yaml`

This manifest records repository evidence; it is not legal advice and does not replace review by the appropriate rights holder or counsel.
