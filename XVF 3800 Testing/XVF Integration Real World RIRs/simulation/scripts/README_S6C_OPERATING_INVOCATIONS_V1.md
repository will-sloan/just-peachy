# Four exact operating-condition invocation commands

Purpose: validate and explicitly invoke the four separately studied O0 conditions without substituting an application generation, profile, or gallery. This entry point does not select an operating preset or alter the application. `validate` only reads bounded source/metadata and applies the original profile parser; it does not open audio, gallery vectors or model weights, instantiate models, or start a session. `file` delegates the original application CLI and therefore starts inference when a user explicitly invokes it. No file command was run for this validation.

| Candidate | Exact application/profile | Naming |
|---|---|---|
| B36 | Preserved S6B epoch2 application, original full B36 v2 profile, original_common tracker | No research enrollment; fresh empty private profile directory |
| C067 | Preserved S6C epoch4 application, C067_O0_O0 v3 profile, N03 mature evidence | None |
| C088 | Same S6C application, C088_O0_O0 N01 profile | Original fixed A15 gallery 84f59413a02827ef445c66be |
| C091 | Same S6C application, C091_O0_O0 N01 profile | Original fixed B15 gallery e21c165f33bb4fd0b3cf0051 |

The helper pins the already prepared original continuous manifests only as exact configuration/source authorities. It does not invoke their coordinators or rerun those sessions. All original frozen application `.py` files, whole profile JSON and gallery manifest bytes are checked before imports. The validation receipt reports current-working-APP versus frozen source parity separately. B36 is never run through the C application. The two 15-profile manifests are not the later common-duration 14-person galleries.

Frozen application copies derive incorrect asset defaults from their relocated paths. This helper supplies the eight original epoch-declared `AssetSpec` paths and digests to a private copy of the unchanged CLI `main` code's globals. It does not change any original module, function code, profile, asset, or saved receipt. It does not copy weights. Metadata validation checks the declarations, not current weight bytes. Original application model admission applies on a future file run.

## Inputs and outputs

Required: `validate` or `file`, and `--candidate B36|C067|C088|C091`. The profile, original application, eight asset declarations and original gallery are fixed by the source-pinned condition. There is no telemetry override, tap search, accelerated option or gallery substitution. Environment thread settings are one and the effective profile must set all three native thread counts to one.

Optional `--wav` specifies the prepared mono 16-kHz O0 WAV for a future file command. The default example is the existing full `S45_01_06/O0.wav`. C conditions pass that same full file to both original paired lanes. B36's original CLI has one mono source and does not support `--identity-wav`. Input must already have the historical prescribed gain applied once; runtime gain stays one. A filename is not proof of correct gain or tap. Validation parses the original file command but does not inspect the WAV header or contents. Future file execution performs the original application input checks. This example is saved-file processing, with no speaker playback or attached XVF hardware.

`validate --receipt <fresh.json>` writes exact source/profile/gallery/asset declarations, the original effective profile, original CLI argv, current source parity, and explicit zero-inference scope. Omit `--receipt` to print this JSON. Validation does not create a session or the configured output root. Use a fresh receipt filename for repetition.

`file --output-root <fresh-directory>` requires a nonexistent explicit output root and no active campaign quiet lease. The original CLI runs at source speed. Actual output goes to `<output-root>/sessions`; the independent empty private store is `<output-root>/empty_private_profiles`. The original CLI returns its completion/export status and writes its generation's session artifacts. These direct invocations have no campaign storage observer, finite batch admission, or external owner supervisor. They are not substitutes for the admitted measured runs or the final census. Preserve actual failures and check original finalization and exit status; do not infer source completion from a transcript alone.

## PowerShell: model-free validation

Use a fresh terminal and the existing interpreter; no package installation or environment activation is needed. Each command starts a fresh interpreter so historical and C imports cannot mix.

```powershell
$s6cRepo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$s6cSim = Join-Path $s6cRepo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s6cPython = Join-Path $s6cRepo '.edge-speech-env\python.exe'
$s6cInvocation = Join-Path $s6cSim 'scripts\s6c_operating_invocations_v1.py'
$s6cValidation = Join-Path $s6cSim 'reports\S6C\20260910T123540Z\command_examples\four_operating_conditions_v2'
& $s6cPython -B $s6cInvocation validate --candidate B36 --receipt "$s6cValidation\B36.json"
& $s6cPython -B $s6cInvocation validate --candidate C067 --receipt "$s6cValidation\C067.json"
& $s6cPython -B $s6cInvocation validate --candidate C088 --receipt "$s6cValidation\C088.json"
& $s6cPython -B $s6cInvocation validate --candidate C091 --receipt "$s6cValidation\C091.json"
```

## Anaconda Prompt / Windows CMD: model-free validation

```bat
set "S6C_REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "S6C_SIM=%S6C_REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6C_PYTHON=%S6C_REPO%\.edge-speech-env\python.exe"
set "S6C_INVOCATION=%S6C_SIM%\scripts\s6c_operating_invocations_v1.py"
set "S6C_VALIDATION=%S6C_SIM%\reports\S6C\20260910T123540Z\command_examples\four_operating_conditions_v2"
"%S6C_PYTHON%" -B "%S6C_INVOCATION%" validate --candidate B36 --receipt "%S6C_VALIDATION%\B36.json"
"%S6C_PYTHON%" -B "%S6C_INVOCATION%" validate --candidate C067 --receipt "%S6C_VALIDATION%\C067.json"
"%S6C_PYTHON%" -B "%S6C_INVOCATION%" validate --candidate C088 --receipt "%S6C_VALIDATION%\C088.json"
"%S6C_PYTHON%" -B "%S6C_INVOCATION%" validate --candidate C091 --receipt "%S6C_VALIDATION%\C091.json"
```

## Optional file inference commands: not executed by this validation

Run only the desired condition, with a fresh output directory and the prepared once-gained O0 source. This action performs inference. It does not enroll or modify a gallery. The commands below intentionally remain separate conditions, not a combined recipe or automatic selection.

PowerShell, after the variable definitions above:

```powershell
$s6cWav = 'G:\Just_Peachy_S6B\20260909T230840Z\inputs\S45_01_06\O0.wav'
& $s6cPython -B $s6cInvocation file --candidate B36 --wav $s6cWav --output-root 'G:\Just_Peachy_S6C\20260910T123540Z\user_invocations\b36_o0_example_v1'
& $s6cPython -B $s6cInvocation file --candidate C067 --wav $s6cWav --output-root 'G:\Just_Peachy_S6C\20260910T123540Z\user_invocations\c067_o0_example_v1'
& $s6cPython -B $s6cInvocation file --candidate C088 --wav $s6cWav --output-root 'G:\Just_Peachy_S6C\20260910T123540Z\user_invocations\c088_a15_o0_example_v1'
& $s6cPython -B $s6cInvocation file --candidate C091 --wav $s6cWav --output-root 'G:\Just_Peachy_S6C\20260910T123540Z\user_invocations\c091_b15_o0_example_v1'
```

Anaconda Prompt / CMD, after its variable definitions above:

```bat
set "S6C_WAV=G:\Just_Peachy_S6B\20260909T230840Z\inputs\S45_01_06\O0.wav"
"%S6C_PYTHON%" -B "%S6C_INVOCATION%" file --candidate B36 --wav "%S6C_WAV%" --output-root "G:\Just_Peachy_S6C\20260910T123540Z\user_invocations\b36_o0_example_v1"
"%S6C_PYTHON%" -B "%S6C_INVOCATION%" file --candidate C067 --wav "%S6C_WAV%" --output-root "G:\Just_Peachy_S6C\20260910T123540Z\user_invocations\c067_o0_example_v1"
"%S6C_PYTHON%" -B "%S6C_INVOCATION%" file --candidate C088 --wav "%S6C_WAV%" --output-root "G:\Just_Peachy_S6C\20260910T123540Z\user_invocations\c088_a15_o0_example_v1"
"%S6C_PYTHON%" -B "%S6C_INVOCATION%" file --candidate C091 --wav "%S6C_WAV%" --output-root "G:\Just_Peachy_S6C\20260910T123540Z\user_invocations\c091_b15_o0_example_v1"
```

Do not point B36 at the working C app. Do not replace A15/B15 with common-duration rosters. Ctrl+C delegates to the original CLI's stop/completion handling; an interrupted file is not a completed measurement. Working application defaults and GUI are unchanged by these process-local commands.

Initial C validation stopped before output on an overly strict composition-telemetry assertion. The long manifest retains the common composition telemetry declaration even when CUES_OFF; original long provider selection uses the registered cue condition. The repaired validation requires the exact cues-off profile and passes no telemetry. Original source/README and the initial successful B36 validation are preserved under STAGING/operating_invocations/before_composition_telemetry_guard_v1. No native operation occurred.
