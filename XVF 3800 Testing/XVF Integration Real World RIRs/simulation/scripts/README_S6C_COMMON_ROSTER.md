# S6C common-roster duration gallery controls

`s6c_common_roster.py` adds six gallery mappings without changing the original
enrollment outputs. It uses original native E templates and actual frozen
`ProfileStore.load()`. It performs no embedding, model loading, calibration fit,
Q scoring or hardware operation.

## Purpose and amendment status

The controls are `COMMON30_FIXED_ROSTER_A` and `COMMON30_FIXED_ROSTER_B`, each at
5, 15 and 30 seconds. A/B membership is the original fixed intended roster
intersected with metadata-eligible full 30-second E enrollment. Every member
must also have an available original 5- and 15-second template. Within each
condition, all three tiers therefore have identical people and competitors.
No person is selected by a C/Q score, template consistency score or observed
recognition success. Original review-status templates remain eligible.

This is an **outcome-informed, exploratory amendment** added after initial S6C
results exposed changing available rosters as a duration confound. It is not an
untouched prospective comparison or independent validation population. The
common cohort has CMU ARCTIC and HiFiTTS people; it cannot establish a Common
Voice enrollment-duration effect. Whole-clip content and native window count
still change with duration. Existing source/domain/person-metadata limitations
remain. All 240 canonical Q cases, all 777 scheduled occurrences, visitors and
all source-empty controls remain eligible for downstream evaluation.

## Inputs and integrity

The completed `enrollment/ENROLLMENT_COMPLETION.json` binds the original gallery
index, scorer map, template index and native enrollment plan. The material
manifest supplies E tier eligibility. The original Q/scene manifests certify the
unchanged evaluation population. The new pre-build plan binds all these sources,
the helper/README and the frozen native app modules.

Original template receipts are checked against exact metadata person, tier,
ordered E source files, backend hash, native embedding count and isolated sibling
paths using the existing template validator. The actual frozen ProfileStore
loads every result and its normalized vectors must be bit-exact to the original
native tier. Existing arrays are never averaged or recomputed.

Tier-30 manifests are reused verbatim when they already contain the exact common
roster. Other galleries copy only the existing native metadata/NPY bytes into
`G:\Just_Peachy_S6C\20260910T123540Z\enrollment\common30_v1`. Nothing is written to
the original gallery, private/default profile directory or old completion.
Existing mismatched or foreign files stop execution and remain for diagnosis.

## Outputs

Under `simulation/reports/S6C/20260910T123540Z/enrollment/common30_v1`:

- `COMMON30_GALLERY_PLAN.json`: frozen roster definition, amendment disclosure
  and original source/code bindings before copying any gallery files.
- `RESEARCH_GALLERY_INDEX_EXTENSION.json`: six unique condition/tier mappings,
  each with `case_id: null` and an exact native gallery manifest binding. Append
  these mappings to a separately versioned execution input; do not overwrite
  `RESEARCH_GALLERY_INDEX.json`.
- `SCORER_GALLERY_MAP_EXTENSION.json`: six evaluator-only roster/name mappings,
  excluded original members, withheld identities and original template receipts.
  It binds the old scorer map and retains all canonical case IDs and Q counts.
- `COMMON30_GALLERY_COMPLETION.json`: exact output/template dependencies, actual
  ProfileStore checks, reused/new manifest counts, copied bytes and zero model/
  calibration/Q-score calls. Original authority hashes are rechecked after build.

Use `verify` to validate an existing completed extension without rewriting it.
Original indexes, scorer maps, templates and completion remain byte-identical.
The parent experiment registers candidate IDs and configuration routing; this
helper does not change recognition thresholds or generate candidate results.

## PowerShell

```powershell
$jpRoot = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$jpCommon = Join-Path $jpRoot 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6c_common_roster.py'
& (Join-Path $jpRoot '.edge-speech-env\python.exe') $jpCommon checks
& (Join-Path $jpRoot '.edge-speech-env\python.exe') $jpCommon freeze
& (Join-Path $jpRoot '.edge-speech-env\python.exe') $jpCommon build
& (Join-Path $jpRoot '.edge-speech-env\python.exe') $jpCommon verify
```

## Anaconda Prompt or CMD

Use the original native environment directly; no dependency installation:

```bat
set "JP_ROOT=C:\Users\amiri\Documents\GitHub\just-peachy"
set "JP_COMMON=%JP_ROOT%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6c_common_roster.py"
"%JP_ROOT%\.edge-speech-env\python.exe" "%JP_COMMON%" checks
"%JP_ROOT%\.edge-speech-env\python.exe" "%JP_COMMON%" freeze
"%JP_ROOT%\.edge-speech-env\python.exe" "%JP_COMMON%" build
"%JP_ROOT%\.edge-speech-env\python.exe" "%JP_COMMON%" verify
```
