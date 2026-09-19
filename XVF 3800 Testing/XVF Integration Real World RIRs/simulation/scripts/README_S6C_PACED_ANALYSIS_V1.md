# S6C paced observation analysis

This additive post-closure helper analyzes actual source-paced C-candidate events, process observations and native speech-gate context. It does not construct models, run a pipeline, change profiles, or create an experiment. It replays the original policy using the actual native observations and requires exact logical event/retained-utterance parity before exporting predictions for the unchanged core and naming scorers. The inventory dependency is pinned to independently reviewed V4 source `426a4eaada68e51d0e6af6decd8b9b56fa3c9660b3cca005f959862c03177876` (independent review receipt `a02cc8739e15036fefee98eb039e4eb4cbf832a18b6fb4603d89d6c1ad9f2829`). This collector itself remains in pre-execution source review. Do not treat pure checks or its existing accelerated control as completed paced evidence.

Inputs to the transformation functions are exact native events and process trajectory rows, measured source duration and complete artifact bindings. The event view retains actual UTC emission time, source cursor and modeled availability separately. Process statistics retain unavailable fields. Native speech activity is inferred from the pinned evidence gate's first rejection (`no_speech_gate`); overlap counts as active speech, and this is not reference-truth activity.

`checks` prints its JSON result without writing data. `context-check` verifies the original completed scorer-only enrollment map, all777 Q occurrences, all240 scenes and480 support routes, without events, model payloads or PCM. `prepare` admits the exact canonical manifest, completed index and externally closed coordinator metadata into a fresh `REPORT/paced_analysis/<namespace>` folder and binds the current helper/README/dependencies. `run` reads each cell's actual event, summary, finalization, transcript export and process trajectory buffers once, checks their hashes, and writes cell observations plus one canonical prediction index per repetition. It does not pool repeated scenes. Failure files and any completed prefix remain preserved; a failed analysis needs a new namespace. Original PCM/model hashes are retained through the exact closed native/COMPLETE chain without reopening those payloads.

Every actual canonical cell also passes its same-native prediction, original support/Q and exact resolved loaded gallery into the independently reviewed `s6c_paced_name_emissions.py` API (held SHA f3314d18dbd9578a9c2a6bf19b6aabb9306ab2415db9488aeae9fa1968ea2a3e; independent root receipt8145e9f20d2a0de697e74aa9b13b292e2685501231eff54c58b4cef5c1fd6a5a). Its actual UTC decision and retained-row metrics are stored separately in `actual_name_emissions`; no modeled V3 score is replaced. Per-cell outputs bind original events, finalization, support, all777 Q, scorer map and a semantic prediction digest. The pacing flag is established by the inventory-admitted unchanged worker call; it is not a separately logged producer flag. Actual source and trajectory observations remain independently reported. This narrow integration is awaiting independent source review; synthetic checks do not count as a paced run.

The actual native scheduler/utterance export is retained separately from a tracker snapshot reconstructed by the identical policy. All nested speaker decisions, shared transcript/identity fields and retained final utterances must match; execution/release timestamps remain separately measured. `policy_wall_sec` is the converter's measured post-closure replay time, never native inference time. Gallery loads by the analyzer are policy reconstruction inputs and are not counted as new native model or gallery execution.

The actual native gallery event must separately equal the native result's receipt and the registered manifest's backend, dimension, dtype, count and template declarations. A no-gallery session requires its exact explicit `mode: none`, zero-load, no-private-access event and a null gallery receipt. A reconstructed gallery load cannot substitute for native evidence: its receipt is checked independently, including the current profile cap on every cached use. The reconstructed spatial provider's digest and actual in-memory observations must match the admitted cue buffer, guarding its original two-read loader. Native and outer process sample counts must match their declared receipts; evidence roles must match the registered role policy at each shared dispatch. The actual application summary must also match the registered profile, cue digest and unity input gain. `test_s6c_paced_native_conversion_v1.py` provides a bounded check against one already accepted accelerated native case; its README explains why that test is not a paced execution. The pre-review-repair source is preserved in staging under `paced_analysis/before_independent_repair_v1`.

## PowerShell

```powershell
$s6cRepo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$s6cSim = Join-Path $s6cRepo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s6cPython = Join-Path $s6cRepo '.edge-speech-env\python.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
& $s6cPython (Join-Path $s6cSim 'scripts\s6c_paced_analysis_v1.py') checks
& $s6cPython (Join-Path $s6cSim 'scripts\s6c_paced_analysis_v1.py') context-check
```

After the independently reviewed dependency pin and actual paced closure, use the exact completed namespace. The gate6 example below requires its real `PACED_INDEX.json`; preparation alone does not create that file:

```powershell
$s6cReport = Join-Path $s6cSim 'reports\S6C\20260910T123540Z'
$s6cScript = Join-Path $s6cSim 'scripts\s6c_paced_analysis_v1.py'
& $s6cPython $s6cScript prepare --manifest (Join-Path $s6cReport 'paced_candidates\gate6_c071_c082_v1\MANIFEST.json') --index (Join-Path $s6cReport 'paced_candidates\gate6_c071_c082_v1\PACED_INDEX.json') --namespace gate6_observations_v1
& $s6cPython $s6cScript run --plan (Join-Path $s6cReport 'paced_analysis\gate6_observations_v1\PLAN.json')
```

## Anaconda Prompt or Windows CMD

Use the existing exact Python even if another Anaconda environment is active. No installation is needed.

```bat
set "S6C_REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "S6C_SIM=%S6C_REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PYTHONDONTWRITEBYTECODE=1"
"%S6C_REPO%\.edge-speech-env\python.exe" "%S6C_SIM%\scripts\s6c_paced_analysis_v1.py" checks
"%S6C_REPO%\.edge-speech-env\python.exe" "%S6C_SIM%\scripts\s6c_paced_analysis_v1.py" context-check
```

After the same actual closure and reviewed source admission:

```bat
set "S6C_REPORT=%S6C_SIM%\reports\S6C\20260910T123540Z"
"%S6C_REPO%\.edge-speech-env\python.exe" "%S6C_SIM%\scripts\s6c_paced_analysis_v1.py" prepare --manifest "%S6C_REPORT%\paced_candidates\gate6_c071_c082_v1\MANIFEST.json" --index "%S6C_REPORT%\paced_candidates\gate6_c071_c082_v1\PACED_INDEX.json" --namespace gate6_observations_v1
"%S6C_REPO%\.edge-speech-env\python.exe" "%S6C_SIM%\scripts\s6c_paced_analysis_v1.py" run --plan "%S6C_REPORT%\paced_analysis\gate6_observations_v1\PLAN.json"
```

The helper refuses to run while `PACED_QUIET_OWNER.json` exists. Keep other heavy analysis stopped during actual paced measurements. Historical B00/B01/B36 workers and long compositions have different source schemas and are not silently converted by this canonical C-cell adapter. Core/name scoring follows separately from each `REPETITION_<n>_PREDICTION_INDEX.json` using the maintained scorer READMEs and the same registered candidate extensions as the full-bank analysis.

The observer reports sampled maxima, gaps and first-to-last trends, not continuous peaks or proof of a memory leak. UTC order reversals are retained. Negative emission-minus-source-cursor values can follow the original producer's block-before-sleep convention. None of these measures is GUI, phonetic-onset, DSP-age, CM5 or physical-hardware latency.
