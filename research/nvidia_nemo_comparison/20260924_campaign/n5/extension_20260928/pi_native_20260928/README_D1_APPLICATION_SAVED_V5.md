# Installed application delayed diarizer saved test V5

Purpose: qualify the remaining delayed selected-model/application path through actual installed v12 Controller and withdrawn PrototypeUI Mode navigation, Delayed selection, Start, saved SoundFile worker, Stop and Close. Fresh V5 reuses V4 mode-aware controls and unchanged V88 model adapter/V85 factory. Prior Streaming V3 and Chunk52 V4 app receipts are separately pinned. No normal/live pipeline, release activation, ASR, capture, playback, visible rendering, physical touch or accuracy claim.

Inputs: D1_APPLICATION_SAVED_INPUT_V5.json pins existing mono16kHz source/reference, installed module/config/manifest origins, independent session, three native receipts and two app receipts. Libraries/weights/adapters/source/release are reused in place. Public d1-saved-mode-selection.v1 exposes saved-only availability/live_start_available=false; canonical translation to the immutable legacy adapter stays private. One mode/run per fresh process because libraries remain mapped after close; no fallback or same-process reacquisition.

This admission selects Delayed only. Ordered1600-sample pushes use cancellable0.1s waits. Actual Stop is invoked after the first observed340800 accepted samples (21.3s source), below352127 ceiling; exact accepted count is measured. Finish runs once. All native frames remain. Pre-EOF probabilities must match retained delayed reference within1e-5; new EOF tail has count/clock/finite/range evidence only. Timing includes pacing/UI/startup, not sustained RTF/live latency/speedup.

Fresh d1_endpoint_contract_v3.py and D1_ENDPOINT_CONTRACT_V3.json verify the exact delayed LRU1 main7db8afef2e37b28c0f9d56690b4c0d5fcd8c85a50fa6034f8e6fb53674ceb45a, admitted build script, successful compile/link, LRU1 object, 2MiB metadata runtime, prior LRU8 patch lineage, retained frontend source/objects and Q8 metadata before acquisition. This is retained build provenance, not a new reproducible compile. Nonempty EOF adds n_fft/2 then frontend floor((audio_end-n_fft/2)/160)+1 gives floor(N/160)+1. Empty0 is source-derived; native empty input is not newly qualified. Changed host count checks cover the extended ceiling only, without rerunning old suites.

Stop requests cancellation before queueing. Ownership remains until worker join and actual source/model/stream/bundle closure. App Close releases original RuntimeLock afterward and joins command worker. ERROR alone never releases ownership. Constructor/reset/close failure or concurrency stress is not claimed.

Outputs under fresh Pi d1-application-saved-v5: bounded code/control/outer logs/telemetry/receipts; passage START_REQUEST/ENDPOINT_BINDING/ASSETS/CABI/MAPPED/CALLS/PROBABILITIES; passage_closure MODEL_CLOSURE; app_receipts GUI_STOP/LOADED_MODULES/APPLICATION_CLOSURE/last_application; bounded first worker traceback when needed. Private data contains DATA_SCHEMA, original lock lifecycle, empty people/conversations directories. Independent review and exact private target backup follow. No audio copy.

Limits:4MiBtarget+4MiBhost; existing5GiBoutput/52GiBtotal including retained reservations, fixed32GBPi/5GiBfree. Passage512KiB/8files/max256KiB; closure64KiB/2files/max16KiB; app receipts64KiB/4files/max16KiB; failure128KiB/2files/max64KiB. Seven app directories448KiB and RuntimeLock record/temp/guard4096B reserve. Existing bounded stage/outer and sampled target stop, not hard filesystem quota/full field integration. CPU2,3/shared200%,Tasks64,768MiBAS,1MiBstacks,onemodelthread,GPUoff,300sservice/60sStop;gate128MiB CPU3. Host coordinatorsCPU14 before reads. Originalrc5 concurrent; checkpoint2026-10-01T17:47:34Z unchanged.

## PowerShell

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B dispatch_d1_application_saved_v5.py --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V187.json'
& $py -B review_d1_application_saved_v5.py
& $py -B backup_d1_application_saved_v5.py
```

## Command Prompt / Anaconda Prompt

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_d1_application_saved_v5.py --census "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V187.json"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_d1_application_saved_v5.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B backup_d1_application_saved_v5.py
```

Run-specific commands once after fresh owners/census/admission review. Never replay completed/failed runs or directly invoke worker/gate. Preserve raw failures and independently review closure before a justified fresh derivative. The success reviewer cannot relabel failure. Old code/admissions/results/policies remain immutable. Preparation-only exclusive-create filename failure is retained privately; old protocol bytes were never overwritten and no native process started at that point.
