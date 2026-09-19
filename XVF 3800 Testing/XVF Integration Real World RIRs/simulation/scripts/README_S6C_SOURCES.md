# S6C local enrollment, calibration and query sources

`s6c_sources.py` inventories the installed original CMU ARCTIC, HiFiTTS v0 clean/other training manifests and the prepared self-reported older Common Voice 26 cohort. It freezes new research enrollment (E), calibration (C) and canonical query (Q) source roles, then prepares nested 5/15/30-second estimated-usable enrollment prefixes and up to 30 estimated-usable calibration seconds per person. It makes no model calls, downloads, hardware passes or private-gallery changes. It does not fit thresholds, enroll anyone or claim successful identification.

Inputs are the preserved S4/S4.5 source/split/QC/rights manifests, all 240 canonical scene records, the 34 never-captured optional reference preparations, native original corpus metadata and audio, and the S6B local evidence index. All 777 scheduled query occurrences remain in the Q manifest, including repetitions and legacy S4 development aliases. The 43 query identities are corpus-qualified metadata identities, with pseudonymous research names; they are not proven globally distinct people. Documented HiFi LibriVox reader aliases are retained without contributor identification.

The source inventory excludes every canonical Q source ID, original parent path, native/decoded exact hash, normalized text group, nonempty corpus-qualified native sentence/prompt ID and HiFi Q book. Prior selected probe roles, prior S4 material, previous source QC rejections, 413 historically excluded CV contributors, non-permitted upstream splits and L2 ARCTIC remain excluded. Original roles/splits are retained as historical fields; a new unused HiFi book can be assigned to C without changing the old source records. HiFi E/C uses distinct non-Q books where available and otherwise distinct chapters of the enrollment book, with an explicit same-book limitation. No book/chapter separation is claimed to establish independent recording sessions. The three expected same-book calibration fallbacks are readers 11697, 6671 and 9136, subject to actual source QC and coverage.

Role assignment and candidate order freeze before waveform QC. The existing optional references receive E priority, additional E/C prompt roles use a fixed seed, and cross-corpus text conflicts use explicit E precedence. Each person/role has at most 80 candidate files; the complete metadata screen remains local. Whole-clip header durations must remain within the inherited 0.25–10-second range. Preparation stops once the frozen prefix supplies 30 estimated-usable seconds in each role; unnecessary remaining candidates are listed without decoding. Sparse people and unavailable tiers are retained. No Q material is borrowed to reach a target.

The estimator is the unchanged S4 numerical 20 ms RMS mask, with threshold max(-50 dBFS, frame p95 minus 25 dB). Its active seconds are estimated usable support, not exact phonetic activity or an auditory clean-speech certification. The inherited source rail/DC/activity/amplification QC rules retain PASS and REVIEW records. Natural pauses inside whole clips remain. No cropping, looping, time stretch, silence removal, concatenation or gain is applied. Mono 16 kHz FLOAT WAVs use the same antialiased SciPy resampling convention at unity gain. Later enrollment/HIL frontends must declare and apply their own level rule exactly once.

An available duration tier is the shortest deterministic whole-clip prefix reaching its requested estimated usable seconds; actual duration can exceed the target by the last whole clip. An unavailable tier records the honest smaller prefix and shortfall. Nested tiers reuse the same earlier clips; these repeated views are not new independent evidence. Different native files/texts provide distinct clips, not a claim of independent sessions. This is a paragraph-like duration proxy, not a newly read paragraph or an XVF-domain enrollment recording.

Outputs:

- `simulation/staging/s6c/<run_id>/source_inventory/v2/CATALOGUE_SCREEN.jsonl`: local metadata eligibility screen; no raw contributor identifiers.
- `EC_CANDIDATE_FREEZE.json` and `Q_OCCURRENCES.json` in that directory: exact source-role ordering, metadata/rights bindings, original/decoded query aliases and all 777 occurrences.
- `G:\Just_Peachy_S6C\<run_id>\source_inventory\v2\decoded_16k\*.wav`: only the required new source audio. Resumable `clip_receipts/*.json` stay in the C: staging revision. Original corpora and previous stages stay unchanged.
- `simulation/reports/S6C/<run_id>/enrollment_inventory/v2/INVENTORY_RECEIPT.json`, `RESEARCH_PERSON_ALIASES.json`, `ECQ_MANIFEST.json`, `ENROLLMENT_TIER_COVERAGE.csv` and `PREPARATION_RECEIPT.json`: compact authority/coverage plus local source bindings and leakage checks. The full ECQ manifest stays local if too large for the handoff.

The E/C manifest is a source pool, not a tested gallery. Each later fixed gallery condition must admit only its predefined known identities to both the gallery and its identity-calibration subset. Strangers must be absent from both. No template may change after observing its query scene. Clean-source domain mismatch, unknown global identities and unavailable calibration/tier coverage must remain in later results.

PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
$env:OMP_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' s6c_sources.py self-test
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' s6c_sources.py prepare --run-id 20260910T123540Z --revision v2
```

Anaconda Prompt or Command Prompt (the existing project interpreter is selected explicitly; no environment installation is needed):

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
set OMP_NUM_THREADS=1
set OPENBLAS_NUM_THREADS=1
set MKL_NUM_THREADS=1
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" s6c_sources.py self-test
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" s6c_sources.py prepare --run-id 20260910T123540Z --revision v2
```

The metadata inventory for the authorized `v2` is already complete. The commands above start or resume only its source preparation. The default revision is `v2`; `--revision v3` or a later positive version creates a separate namespace for an explicitly changed source design. The first metadata-only v1 inventory remains unchanged in the parent directories, with exact helper/README snapshots and `V1_REVIEW_FIX_LINEAGE.json`. It was not admitted for source preparation after independent review required a native Common Voice sentence-ID guard and stronger query/completion binding checks. No v1 enrollment audio, gallery or model result exists. Existing completed outputs are verified rather than replaced. For an interrupted preparation, use the same `prepare` command with the same frozen code/README/candidate manifest; exact per-clip receipts resume the deterministic prefix. Do not edit bound source code while preparation runs. A failed/incomplete inventory namespace must be retained for inspection and restarted in a new authorized namespace rather than overwritten. Preparation checks both volumes before writing, preserves 50 GiB on C: and 75 GiB on G:, and places new enrollment/calibration audio only in the new G: S6C namespace.

The self-test is model-free and covers nesting, missing duration tiers, normalization aliases, known-parent crop/gain aliases, deterministic pseudonyms, native same-sentence-ID/different-text aliases, exact artifact mutation rejection and namespace safety. Preparation verifies the Q manifest before use and on resume. Completed preparation resumes verify the bound ECQ manifest and tier CSV through the existing PREPARATION_RECEIPT, then the original/decoded source bytes. The actual audit checks native/decoded exact bytes and known metadata parent/prompt lineage. It is not an exhaustive acoustic near-duplicate search for undocumented crops/re-encodings in unrelated recordings, and it does not establish unique human identities across datasets. License assertions and missing per-voice notices are carried from the existing rights evidence; this script grants no new rights or future training/redistribution clearance.

The v2 metadata pass used the exact helper/README now preserved under `source_inventory/v2/metadata_executor_snapshot`. Its original inventory receipt is unchanged. Independent review then required a preparation-only checkpoint fix. `enrollment_inventory/v2/PREPARATION_CODE_ADMISSION.json` binds the original metadata executor, the later preparation executor, the exact candidate freeze and the model-free check receipt. At preparation entry, the helper verifies those hashes and checks AST equality of every original function except `prepare`/`self_test`, plus all non-function module statements and unchanged estimator/QC dependencies. The later helper is not presented as the original metadata executor.

Every reused clip receipt must have an allowed ACCEPTED/REJECTED status, the exact freeze hash, a canonical frozen-candidate-row hash, the same outer source ID/person/E-C role, and every original frozen field unchanged inside the accepted source payload. Its original/decoded audio bindings are verified. A correct outer row hash attached to a swapped accepted payload is rejected. The model-free fixture checks these cases before any audio materialization.

Do not rerun `inventory --revision v2` using the later preparation helper: the completed metadata authority intentionally retains its original executor hash. To intentionally create a new independent inventory with this current helper, use a fresh revision, for example `s6c_sources.py inventory --run-id 20260910T123540Z --revision v3`, followed by `s6c_sources.py prepare --run-id 20260910T123540Z --revision v3`, with the same interpreter and shell setup above. That is a new source revision, not the resume command for the authorized v2. Preserve all earlier outputs.
