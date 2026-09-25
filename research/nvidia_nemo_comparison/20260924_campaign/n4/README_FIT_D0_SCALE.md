# Fit the predeclared D0/TitaNet C scale

`fit_d0_scale.py` implements the single frozen proposal in
`D0_C_SCALE_PROTOCOL_V1.json` (SHA-256
`ad9c6a9a953d9931a2f2e2bb4ce3d7d79b254952ccfcebad404ac4e0bde954e1`).
Its purpose is to propose model-specific anonymous association score units,
without Q tuning or changes to the working application. It verifies the prior
matched collection review, original protected C labels, all paired cell hashes,
unchanged source and identical nominal profiles. The private protocol-freeze
receipt must precede score inspection. No real models or GUI are loaded.

Inputs: the exact protocol, `d0-calibration-review-v1/REVIEW.json`, their bound
private collection/evidence and a fresh output directory. Outputs: private
`RESULT.json`, proposed `PROPOSED_PROFILE.json` if a mapping exists, and private
`PRIVATE_SPLIT.json`. The aggregate result contains no vectors or actor IDs and
may be copied into reports after review. The split and collection stay private.
The command refuses a used output directory. It runs on CPU14 below normal
priority with one numerical library thread; use it after the numerical worker
releases ownership. No new download, waveform, training or names are produced.

The fit uses the first/middle/last actual admitted windows per source and
short/mature role. Matching E0/E1 window pairs compare different source and PCM
IDs only. Each identity stays entirely in the protocol's deterministic C fit
or validation partition. Cross-partition pairs are excluded. Missing roles and
positive-pair support are counted, not synthesized. Cross-role pairs include
both short-left/mature-right and mature-left/short-right directions.

Center aggregation follows the frozen nested medians exactly. Validation rates
use the corresponding equal-weight hierarchy: mean error over waveform pairs
within a source-pair/role, mean over source pairs within an identity-pair/role,
mean over available roles within an identity pair, then mean over identity
pairs separately for same/different classes. Long sources and prolific speakers
therefore do not gain weight merely by producing more windows. Role-specific
scores are also retained. The fixed validation tolerances come from the protocol.

One positive affine mapping changes the declared raw-cosine thresholds and
cosine differences. Normalized joint scores, timing, vector updates and inactive
defaults remain unchanged. Invalid ranges or actual application profile
validation fail without clipping, selecting another fit or changing the split.
The proposed profile is retained even if a subsequent validation fails.

`PASS_C_SCALE_SCREEN_ONLY` is only a component screening result. A genuine
tracker regression, explicit new release/profile binding, baseline reconfirmation
and integrated evaluation still follow. A failure stays `UNQUALIFIED_C_SCALE`.
Neither status certifies processed-query naming; operational naming remains
`UNCALIBRATED_REJECT_ALL` without a separate valid domain-specific gate.

PowerShell:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local\n4'
& $jpPython -B -m unittest discover -s $jpCode -p 'test_fit_d0_scale.py' -v
& $jpPython -B "$jpCode\fit_d0_scale.py" --protocol "$jpCode\D0_C_SCALE_PROTOCOL_V1.json" --review "$jpLocal\d0-calibration-review-v1\REVIEW.json" --output "$jpLocal\d0-scale-fit-v1"
```

Command Prompt / Anaconda Prompt:

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local\n4"
"%JP_PY%" -B -m unittest discover -s "%JP_CODE%" -p "test_fit_d0_scale.py" -v
"%JP_PY%" -B "%JP_CODE%\fit_d0_scale.py" --protocol "%JP_CODE%\D0_C_SCALE_PROTOCOL_V1.json" --review "%JP_LOCAL%\d0-calibration-review-v1\REVIEW.json" --output "%JP_LOCAL%\d0-scale-fit-v1"
```

Tests cover score-independent window selection, identity partitioning, matched
pair exclusions, nested weights, separation of fit and validation, affine units,
unchanged normalized fields, strict parameter rejection and both validation
constraints. They use artificial vectors only, with no real model/audio calls.
