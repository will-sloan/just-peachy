# Selected application model boundary and streaming passage V1

Purpose: bind the explicit V87 diarizer selection contract to the installed N2ResidentModels.acquire_diarizer boundary and the exact retained streaming runtime. This is a D1-only component integration, not application Start enablement or a field release. Caller holds a fresh admission/research lease; no ASR, source, microphone, playback, GUI or original Controller/bundle constructor runs.

Inputs: D1_MODEL_BINDING_INPUT_V1.json pins the installed v12 app/n2_models.py, retained streaming source.wav, saved_full.npy/calls and prior receipts. The source remains private and is read in place. The new streaming request is a fixture of the exact V87 control schema, not a new GUI run. Its launchable=false field is preserved: bind_request authorizes no live source or application launch. Immutable d1_modes_v1.py and D1_MODE_CATALOG_V1.json validate all adapter/model/runtime library bytes, actual C-ABI geometry and mapped library paths. Common C-wrapper hashes alone cannot identify the runtime.

The selected installed acquire AST changes only its import/constructor region to call the bound guarded factory. Its D1 guard, model assignment, return, resident-reset branch and exact close body are retained. An outer lock and one-acquisition latch make the old resident-reset branch unreachable; concurrent/later acquisition, including after close/failure, rejects. This wake does not qualify concurrent caller stress or arbitrary failure cleanup. After a fresh guarded model is returned, reset binds the explicit independent application session before any samples. No midstream or ASR/VAD endpoint reset occurs. A different mode needs a fresh process because native libraries stay mapped. The bound mode is isolated from caller request mutation. No old runtime document can silently choose another geometry.

Changed checks: four malformed requests (launchable, boolean geometry, wrong runtime, extra field), three invalid sessions, wrong backend, resident reacquire and closed reacquire reject. Native streaming consumes only35127 retained mono16kHz float32 samples in1600-sample ordered pushes plus one EOF. Compare all pre-EOF output to the retained same-geometry reference at unchanged1e-5; endpoint EOF tail has count/clock/finite/range evidence only, without matched tail reference. Preserve all audio samples and eight probability slots. Costs include actual short passage/load/EOF/CPU/RSS/thermal/clock/throttle; startup-prefix speed is not whole-file or steady-state performance, speedup or accuracy. Do not rerun delayed/whole-file/control/helper/transport/timer tests.

Outputs: fresh Pi d1-model-binding-v1/code/control with bounded staging; mapped outer logs/resources/worker and gate results/closures; passage CABI/ASSETS/MAPPED/CALLS/PROBABILITIES and MODEL_CLOSURE including exact session, ten boundary rejections and empty native stream/model pointers/bundle field. Host private -evidence receives preflight, review, exact target backup and code/allocation reviews. No original installed source/config or old evidence is edited. Retain failures and partial files; no retry/delete. Review independently checks exact sources, pre-EOF probabilities, ordered source/frame counts, actual envelope and ownership closure, without model imports.

Admission: fresh WINDOW_V5 census including target,8MiB combined (4MiB target+4MiB host) within existing5GiB output/52GiB total including retained reservations; no reset/policy change. Fixed32GB Pi/5GiBfree. Actual main768MiBAS/1MiBstack/CPU2,3/shared200%/Tasks64/300s/Stop60/32MiBfile; one modelthread, GPUoff. Gate/bootstrap128MiB CPU3; sampled192MiBavailable/640MiB unique-owner RSS stops. Reused bounded stage/outer; passage512KiB/6files/256KiBfile-write,closure64KiB/2files/16KiBfile-write,2directories128KiBextentreserve. External host metadata remains admission-scoped. Not fullV3 field quota, hard filesystem quota or arbitrary parent/descendant-stall guarantee. October1 17:47:34UTC checkpoint unchanged.

## PowerShell

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B dispatch_d1_model_binding_v1.py --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V181.json'
& $py -B review_d1_model_binding_v1.py
& $py -B backup_d1_model_binding_v1.py
```

## Command Prompt / Anaconda Prompt

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_d1_model_binding_v1.py --census "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V181.json"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_d1_model_binding_v1.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B backup_d1_model_binding_v1.py
```

These are immutable run-specific recipes. Do not replay a closed run, invoke worker/gate directly or treat bind_request as an unguarded launcher. New mode/implementation needs a fresh destination, source binding and measured admission. Review before backup; keep all personal data/weights/probabilities private. Installed application controls remain launchable=false pending full model/source/Stop/ownership integration.
