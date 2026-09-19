# Live source-support name episodes

## Purpose and scope

`s6c_live_name_episodes.py` adds a descriptive episode view to an already completed, explicitly hash-bound S6C V3 naming analysis. It imports the unchanged V3 name timeline, source-support mapping, roster classification and sample integration. It does not run models, the predictor, ASR scoring or anonymous scoring. Earlier code, scores, receipts and transcript-row episode metrics remain unchanged.

An episode is one maximal contiguous sole-active interval with the same assigned metadata identity within one source occurrence. An identity change, Unknown/expiry, silence/overlap gap or occurrence boundary splits it. Tentative-to-confirmed state changes alone do not. Correct and wrong known episodes are both retained. Undeclared assigned names remain wrong-known according to the original V3 rule and are identified separately by assignment_status; no identity is invented.

The end of a wrong episode is classified as an immediate observed correct name, an Unknown/expiry abstention, another wrong identity, or a censored support boundary. A gap is not evidence of correction. These are modeled availability/source-support intervals, with the existing0.75-second expiry, not phonetic word times or independently measured wall-paced latency. Transcript-row corrections and retained row-seconds remain in the original V3 outputs and are never pooled with these live episodes.

## Inputs and checks

Required: a COMPLETE_REQUESTED_NAME_INDEX V3 receipt and its explicit SHA256. Its completed prediction index, exact COVERAGE table and every per-cell name score must form the same unique declared route/case grid. The code verifies exact parsed table bytes, the score/prediction/support/Q/gallery/code binding chain, current V3 code hashes, gallery load receipts, and all777 frozen Q occurrences. It uses the actual identity tap once.

Every mapped turn must reproduce the original correct/wrong/Unknown sample partition exactly; assigned episode duration must equal the corresponding original sample numerator. Missing support remains missing, zero support remains zero, and source-empty controls stay separate. The aggregate tables separate enrolled, intended-but-unavailable, withheld/unselected and no-gallery status. They additionally distinguish complete-reference support from the incomplete known-target support. ALL_KNOWN_TARGET_SUPPORT is explicitly their union and is not the203-scene complete anonymous population.

The original scorer and prediction bindings provide transitive native/model provenance. This supplement does not re-open every native receipt or model. Source-support and timeline limitations are inherited. The descriptive extension was added after observed naming outcomes; it is not a new independent validation population.

## Outputs

A fresh contained REPORT child is required. The tool writes:

- PROFILE_LIVE_EPISODES.csv: exact pooled sample/episode/affected-turn and affected-person counts, roster and reference populations, missing/zero denominators, wrong-episode end counts.
- TURN_LIVE_EPISODES.csv: every source occurrence, including unmapped or no-support rows.
- ASSIGNED_NAME_EPISODES.csv: all contiguous assigned intervals, status and identity, sample bounds, duration and observed/censored ending.
- SOURCE_BINDINGS.csv: each exact source naming score, prediction and support binding.
- EMPTY_CONTROL_RESULTS.csv: source-empty capture and assigned-name samples, not stranger episodes.
- LIVE_NAME_EPISODE_RECEIPT.json: complete source/implementation/table bindings and partition-check counts.

No COMPLETE receipt is written on a failed assertion. Preserve a failed partial output directory; use a fresh output name for a corrected retry. Do not run concurrently with paced resource measurement. This is one analysis worker and should be queued after parent-authorized core/name scoring.

## PowerShell

Mapping follows the original V3 rule exactly: only a null sole-support mapping is missing. A non-null empty range remains a numeric zero even when activity_available is false; that activity flag and its denominator are retained explicitly. Undeclared assignments are also counted as a separate subset of wrong-known samples and episodes. Because the unchanged V3 timeline maps their unknown metadata identity to null, different foreign IDs or display names cannot be distinguished; consecutive such assignments can merge and are not claimed as distinct-person/name-switch counts. The first unexecuted source/README and14-fixture receipt are preserved under independent_review/live_name_episode_source_v1 and LIVE_NAME_EPISODE_CHECKS_V1.json; the corrected executor has a separate V2 fixture receipt.

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$py = "$sim\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
& $py "$sim\scripts\s6c_live_name_episodes.py" --test
& $py "$sim\scripts\s6c_live_name_episodes.py" --name-receipt full_n01_naming_names_v3/NAME_ANALYSIS_RECEIPT.json --name-receipt-sha 7fd6fbecd0cfbdd77e64333e65bb9ea19d5a9e5780f2b763a0d7470307b58bce --output-subdir full_n01_live_name_episodes_v1
```

## Anaconda Prompt / Windows Command Prompt

The explicit interpreter is the existing isolated analysis environment; do not activate or change the native environment.

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PY=%SIM%\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
"%PY%" "%SIM%\scripts\s6c_live_name_episodes.py" --test
"%PY%" "%SIM%\scripts\s6c_live_name_episodes.py" --name-receipt full_n01_naming_names_v3/NAME_ANALYSIS_RECEIPT.json --name-receipt-sha 7fd6fbecd0cfbdd77e64333e65bb9ea19d5a9e5780f2b763a0d7470307b58bce --output-subdir full_n01_live_name_episodes_v1
```

Other completed V3 naming groups can be supplied with their own exact receipt path/hash and a fresh output namespace. The pure fixtures exercise confirmation-only changes, wrong-identity switches, Unknown interruption, silence gaps, observed correction, missing/empty support, clipping, censoring, actual V3 availability/expiry and invalid support. They do not claim empirical episode incidence.
