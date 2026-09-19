# Inactive captured C support proposal

`s6d_C_support_prepare_v1.py` converts the frozen 138-event common-clock proposal into small evaluator-only support proposals for the 12 already-closed C recordings. It verifies original case/source identity, the exact collection-only partition, original C source metadata, and the actual original A15 gallery's 15 metadata/vector bindings. It never uses the enrollment plan's larger intended rosters. Unknown actual-gallery identities retain a null profile ID.

Inputs are pinned inside the helper: C clock dc428887, collection partition98d4f5bd, original enrollment plan6cbcd082 and actual A15 gallery8042fbec. `--output` must be a fresh directory directly under this S6D report. Outputs are 12 `*_SUPPORT_PROPOSAL.json` files, a receipt with exact source/input bindings, and copied helpers. No audio is generated or changed, and no models, UI or hardware run.

Every copied interval must equal the already-computed conservative fragment: `16000 + input_left + upper_case_lag` through `16000 + input_right + lower_case_lag`. The equality of exported min/max means that the interval is already eroded; it is not a claim of zero DSP uncertainty. The adapter adds no further guard, lag, RIR origin or per-beam alignment. Intervals with multiple source IDs/identities or less than1.5seconds are retained as exclusions. The proposed interval count is not the observed native mature-window count. Actual native windows must later satisfy whole-span and existing clean/exclusive speech gates.

All outputs remain `PROPOSED_CONSERVATIVE_SOURCE_SUPPORT_PENDING_ROOT_REVIEW`. The extraction helper rejects this status. Root must independently review the original empirical lag envelope and exclusions before separately adopting any support. Collection route acceptance supplies neither label authority nor NN launch permission. No selector threshold or unique competing-beam truth is inferred.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$sim\scripts\s6d_C_support_checks_v1.py" --output 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\C_support_v1_checks'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$sim\scripts\s6d_C_support_prepare_v1.py" --output "$sim\reports\S6D\20260913T195357Z\physical_C_support_proposed_v1"
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%SIM%\scripts\s6d_C_support_checks_v1.py" --output "G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\C_support_v1_checks"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%SIM%\scripts\s6d_C_support_prepare_v1.py" --output "%SIM%\reports\S6D\20260913T195357Z\physical_C_support_proposed_v1"
```

Use fresh suffixes if the supplied directories exist. `s6d_C_support_checks_v1.py` writes only seven tiny metadata-only checks and a receipt on G. The checks cover exact unshifted bounds, unknown profile retention, a second guard error, a wrong identity join, overlapping identities, insufficient duration and noninteger clock rejection. They do not validate physical latency or model outcomes.
