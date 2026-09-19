# S6B executed method-family coverage

`s6b_family_coverage.py` creates the reviewable map between the eight required families, actual frozen application mechanisms, the N01–N08 proposals and exact paired profile differences. It imports no neural models, creates no predictions, changes no APP files and uses no truth for prediction.

The reviewed map identifies 27 mechanisms and two additional control rows. A row points to the actual executable function and source hash. The AST check locates that function; it is not an implementation-effect test. Separate columns distinguish focused fixture receipts, actual application activity on cached real neural observations, missing component recipes and benefit. Activity, implementation and benefit must never be treated as synonyms.

N01, N03, N04 and N07 implement the named core mechanisms. N05 is explicitly a narrower adaptation: global time since an admitted voice observation with event cadence, not a per-track unique-evidence deficit queue. N02 cue-driven segmentation refresh, N06 clipping-transition freeze and N08 independently maintained clean shadow prototypes remain NOT_IMPLEMENTED with concrete scope reasons. This report does not invent evidence that an omitted proposal is dominated.

## Inputs

- The authoritative `EPOCH2_EXECUTION_MANIFEST.json`, frozen APP sources, effective profile registry and fixed 44-scene/two-tap challenge panel.
- A passing actual comparison mechanism audit from `s6b_mechanism_audit.py`. The R0 subset is supported while the remaining recipes are pending. A canonical neural-pilot audit is rejected because it is not the comparison-method population.
- Existing tracker/component/pilot/neural-smoke receipts and the inherited 68-idea registry, retained as evidence with their exact scope.
- `R0_ALL_FEATURE_PARITY.json`: separate full-bank R0 comparison of 480 outputs / 15,649 vectors. Exact spans and legacy anonymous labels are distinguished from floating-point array equality and scheduler-dependent transcript attribution.

The builder verifies code, registry, panel, audit and prediction-index bindings. It rejects duplicate profile/case/tap rows, cells outside the challenge population and changed inputs in an existing output namespace. Completeness checks use the exact panel case/tap set, not just the presence of a profile name. It does not repeat the full nested prediction rehash done by the bound mechanism audit.

## Outputs

The default output is `reports/S6B/20260909T230840Z/coverage/challenge_final_v1`, using the complete `mechanisms/CHALLENGE_MECHANISM_AUDIT_FINAL.json`. Use a new explicit output namespace when code or evidence changes. Supporting validation now binds `ACTUAL_PILOT_VALIDATION_FINAL.json` and `PILOT_INDEX_LINEAGE.json`, so the completed pilot index is resolved through its immutable copy.

- `METHOD_FAMILY_COVERAGE.csv`: family/mechanism mapping, bound functions, actual activation counts, fixture scope, pending populations and limitations.
- `MATCHED_INTERACTION_TABLE.csv`: sixteen required/auxiliary contrasts with exact effective-field differences, including once-applied prepared-input gain. It exposes the B24/B25 scheduling-plus-tracking bundle and the B22/B28 endpoint/search confound.
- `N01_N08_IMPLEMENTATION_STATUS.csv`: complete/adapted/absent proposal status, observed operations and concrete limits.
- `FAMILY_COVERAGE_SUMMARY.json` and `FAMILY_COVERAGE_HANDOFF.md`: compact scope and interpretation.
- `RESIDENT_REUSE_EVIDENCE.json`: bounded early-event witnesses from actual native sessions, with `session_index > 1`, `weights_reused` and `fresh_asr_stream`. Up to eight jobs per recipe and 32 initial lines per job are inspected. The mechanism audit already verified complete source-event hashes; this builder reads only those bounded prefixes. It does not substitute native job count for proof of reuse or claim every session was independently checked this way.
- `COVERAGE_RECEIPT.json`: input and output hashes plus reporter checks.

Native jobs are deduplicated within each row; different rows overlap, so do not add those counts as independent runs. Unknown decision fractions and operation counts are not speech-time or word-error denominators. Historical B00 internals are uninstrumented. No ranking, equal-work claim, empirical benefit or real-human/CM5 generalization is produced here. Paired score/resource analysis remains separate.

## PowerShell

```powershell
Set-Location -LiteralPath 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' '.\scripts\s6b_family_coverage.py' check
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' '.\scripts\s6b_family_coverage.py' build --audit '.\reports\S6B\20260909T230840Z\mechanisms\CHALLENGE_MECHANISM_AUDIT_FINAL.json' --output '.\reports\S6B\20260909T230840Z\coverage\challenge_final_v1'
```

The script does not silently discover a newer or incomplete index. Developmental `r0_v1`, `r0_v2` and `r0_v3` outputs are retained. The final builder distinguishes baseline-only activity from pending changed policies, separates resident processing from proof of reuse, and clarifies that N07 budget exhaustion preserves the latest label rather than forcing Unknown. Earlier partial outputs remain historical; final packaging should use the complete challenge namespace.

## Windows Command Prompt or Anaconda Prompt

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "scripts\s6b_family_coverage.py" check
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "scripts\s6b_family_coverage.py" build --audit "reports\S6B\20260909T230840Z\mechanisms\CHALLENGE_MECHANISM_AUDIT_FINAL.json" --output "reports\S6B\20260909T230840Z\coverage\challenge_final_v1"
```

The builder itself uses Python's standard library. The explicit repository interpreter keeps the study commands consistent; no environment activation, package installation, hardware connection or model-worker slot is needed.
