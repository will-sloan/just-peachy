# Exact future S6D beam-native manifests

Purpose: `s6d_application_beam_plan.py` prepares and freezes explicitly requested comparisons from accepted NEW same-pass physical captures. It validates routes, waveform hashes, common clocks, physical stream/tail qualification, fixed weights, original or separately admitted device-domain gallery, and exact C-only selector calibration context. It loads profile/gallery data but never creates a model session, starts a device, executes a native job or launches a supervisor.

Inputs: a `s6d-beam-native-request.v1` JSON with `jobs`, `declared_job_limit` and `purpose`, plus fresh output/proposed payload directories. Every job has exactly `job_id`, `control_group`, `role`, `admission`, `beam_settings`, `research_profile`, `research_gallery`, `s6d_settings`. The final five fields are exact path/bytes/sha256 bindings. Roles are `same_pass_auto_control`, `mono_asr_beam_identity`, or `selected_beam_association`. Each group needs exactly one same-pass auto control plus at least one explicitly selected variant, with identical capture result, parent profile, gallery and ASR stream. This planner supports source files up to600s; continuous long-session declarations remain separate. Uncalibrated nominal selectors cannot become native family-failure experiments through this planner.

An empty request explicitly records an unfilled interface, not executed or accepted physical evidence:
```json
{"schema":"s6d-beam-native-request.v1","jobs":[],"declared_job_limit":0,"purpose":"Interface preparation; waiting for independently accepted physical inputs and C-only calibration"}
```

Outputs: immutable MANIFEST.json, frozen application sources and ASSETS.json. Each admitted job includes complete source/provenance bindings, source duration, physical-pass counts distinct from native-job counts, exact CLI argv, and a separate model-free `--check-only` argv. The manifest specifies a frozen PYTHONPATH, one CPU thread per backend and serial jobs. Empty input writes `INTERFACE_FROZEN_NO_ADMITTED_INPUTS`, zero jobs and no guessed paths to recordings. Source/transport PASS alone is insufficient. Ordinary old O0/O1 cached predictions never stand in for new waveforms. No matrix executes automatically; the root must review the exact code, bindings and supervisor before launch.

PowerShell:
```powershell
$s6dSim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$s6dSim\scripts\s6d_application_beam_plan.py" --request 'C:\PATH\TO\beam_request.json' --directory "$s6dSim\reports\S6D\20260913T195357Z\application\beam_native_plan_v1" --payload 'G:\Just_Peachy_S6D\20260913T195357Z\application\beam_native_plan_v1'
```
Anaconda Prompt / CMD:
```bat
set "S6D_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%S6D_SIM%\scripts\s6d_application_beam_plan.py" --request "C:\PATH\TO\beam_request.json" --directory "%S6D_SIM%\reports\S6D\20260913T195357Z\application\beam_native_plan_v1" --payload "G:\Just_Peachy_S6D\20260913T195357Z\application\beam_native_plan_v1"
```

Use fresh suffixes; preserve old failed/empty plans. The application README_RESEARCH_S6D_BEAMS.md documents admission/calibration schemas, native hooks, known limitations and model-free fixtures. Setting `--check-only` validates files without a native session. The corresponding argv without that flag loads the fixed models and is for a separately reviewed future run only.

The additional `calibration_collection` role forms separate C-only groups with selectors disabled. It requires a bound edge-s6d-beam-calibration-partition.v1 proof containing the exact accepted physical case result, C partition and checked E/Q disjointness; selector thresholds are not required to collect C evidence. Such jobs are not beam-family performance experiments. Prepared C30 and narrow two-person overlap controls can supply accepted inputs later without inventing additional hardware attempts or broad efficacy. Evaluation groups still require their matched same-pass auto control and accepted selector calibration.

Each admitted job also writes a small JOB_INPUTS.json containing all six exact input bindings (admission, beam settings, profile, gallery, S6D settings, fixed asset manifest). Both emitted CLI argv variants include --input-bindings and --input-bindings-sha256; a changed input or receipt fails before model creation. Fixed model files themselves are hashed by their existing constructors at actual startup, not during this metadata planner.

Evaluation controls also bind the same S6D delivery/boundary/presentation settings. The planner freezes itself, its checks and README in helpers; a frozen helper uses its adjacent frozen application source. Prior interface_v1 is a preserved draft; use a fresh suffix for the current planner. This does not authorize a model run.

Model-free integration checks: s6d_application_beam_plan_checks.py creates temporary synthetic capture/C proof fixtures on G:, reads the original named-parent profile/gallery metadata, freezes a temporary plan, and runs the actual CLI --check-only subprocess. It verifies no session/payload starts, rejects uncalibrated evaluation and mismatched control delivery policies. Outputs are unittest results; temporary synthetic artifacts are discarded and never counted as physical captures. No neural model or device is loaded.

PowerShell:
```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$s6dSim\scripts\s6d_application_beam_plan_checks.py"
```
Anaconda Prompt / CMD, using S6D_SIM set above:
```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%S6D_SIM%\scripts\s6d_application_beam_plan_checks.py"
```
