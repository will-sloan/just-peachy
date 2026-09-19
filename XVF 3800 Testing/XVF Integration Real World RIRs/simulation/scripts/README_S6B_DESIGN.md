# S6B design and deterministic challenge builder

`s6b_design.py` binds the accepted S6A scene/geometry/short-turn evidence and builds a reviewable S6B method registry. It uses Python standard libraries, reads metadata only, and does not load models, audio, application modules or hardware. Registry entries describe intended mechanisms; successful building does **not** certify that a method was implemented or executed.

The approved matrix contains 40 IDs: 27 main methods, nine matched companions and four controls. All inherited B00–B29 IDs are mapped. B23 is explicitly revised to protected endpoint-only on original neural settings; B27 is explicitly revised to lower-gain full-window RMS. B19/B21/B29 are explicitly revised from spatial companions into the five-cell post-policy/stride/purity fractional design. Component and tracker implementations must provide effective-profile and observable-effect receipts separately.

Four additional explicitly enumerated challenge-only diagnostics test duration by disjoint commitment count and fixed frequent/sparse admission. The total is44 named configurations:40 core plus four limited diagnostics. This bounded exception to the prompt's normal40 target is disclosed in the registry and is not a set of four extra general-purpose candidates.

## Inputs

By default, the script resolves the simulation root from its own location. It consumes:

- `scene_bank/s45_v2_20260909T031300Z/SCENE_MANIFEST.json` and `rir_library/v1/RIR_MANIFEST.json`;
- accepted S6A `PROBE_PANEL.json`, `REFERENCE_SHORT_TURN_RESULTS.csv`, `baseline_results/COVERAGE.csv`, and `design/S6B_JOINT_PLAN.json`.

The immutable scene, RIR, panel and short-table bytes must match embedded SHA-256 identities. All 480 accepted baseline coverage records must be scored. The all40 subsecond-instance denominator is independently derived from complete-reference scene segments and checked case by case against S6A B0/O0. Repeated clips at separate segment positions remain separate source-turn instances. Source clips exactly one second long are excluded from the subsecond bin.

Challenge selection first takes the union of the original36 and the nine scenes containing all40 complete-reference subsecond instances. It then greedily adds any missing available metadata condition with lexical case-ID tie breaking. Current result is44 scenes:43 required-union scenes plus S45_05_05 for nominal folded-angle ambiguity. The44 scenes are a post-S6A diagnostic screen, not an unseen holdout.

Geometry tags use nominal laboratory angle projection; they do not verify native XVF coordinates. The output contains offline truth and must never be supplied as runtime tracker, endpoint or feature inputs.

## PowerShell

Use the existing Anaconda Python; no environment installation is required.

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\anaconda3\python.exe' "$sim\scripts\s6b_design.py" --test
& 'C:\Users\amiri\anaconda3\python.exe' "$sim\scripts\s6b_design.py"
```

To build into a separate review directory without replacing the default design artifacts:

```powershell
& 'C:\Users\amiri\anaconda3\python.exe' "$sim\scripts\s6b_design.py" --simulation-root "$sim" --output "$sim\reports\S6B\20260909T230840Z\design_review_copy"
```

## Anaconda Prompt or Windows Command Prompt

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\anaconda3\python.exe" "%SIM%\scripts\s6b_design.py" --test
"C:\Users\amiri\anaconda3\python.exe" "%SIM%\scripts\s6b_design.py"
```

## Outputs and safe reruns

Default destination: `reports/S6B/20260909T230840Z/design`.

- `CANDIDATE_REGISTRY.json`: IDs, families, parents, cue routes, mechanism/risk contracts, implementation-pending status.
- `CHALLENGE_PANEL.json/.csv` and `SUBSECOND_SOURCE_INSTANCES.csv`: selected cases and exact40 reference instances.
- `METHOD_FAMILY_COVERAGE.csv` and `SEED_ID_MAPPING.csv`: matrix and preserved/revised inherited identities.
- `LIMITED_DIAGNOSTICS.json`: four challenge-only configurations, included in the disclosed total44.
- `NEW_HYPOTHESIS_DECISIONS.json`: N01–N08 requirements; N01/N03/N04/N05 require distinct implemented effects, N07 is additional only if proved.
- `INTERACTION_CONTRACTS.json`: paired comparisons and explicit confounds.
- `REQUIREMENT_ACCEPTANCE.json`: required execution/analysis/closure evidence, initially pending.
- `DESIGN_BUILD_RECEIPT.json`: exact inputs/output identities and tests.

Rerunning overwrites these generated design files deterministically. It does not change S6A or the root-owned executed profile/recipe registry. Preserve final acceptance annotations in a separate final audit file rather than hand-editing generated contracts. Eight conceptual expensive recipe families are **not** eight interchangeable neural cache keys: changed admission windows, full-window RMS, early-short-plus-long evidence and protected endpoint branches need separate exact effective identities.

`RECIPE_GROUP_PROPOSAL.json` is a separately written initial handoff to the root recipe compiler. It is explicitly a draft; the effective root recipe registry is authoritative for execution. This builder leaves that draft untouched.

## Validation

`--test` checks repeated-source instance retention, strict subsecond boundary, incomplete-reference exclusion, deterministic deduplication, duplicate-panel rejection, counts and all30 inherited mappings. A real build also requires immutable hashes, complete S6A coverage and exact per-case short-count agreement. These checks establish design integrity only; causal model effects, scoring and hardware/target qualification are separate tasks.
