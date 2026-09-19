# Prepare the held twelve-job native pilot queue

Purpose: freeze the reviewed runner/wrapper source and prepare exactly the12native cells already declared by application/native_pilot_v3/MANIFEST.json. This script never launches a production job. It binds the exact root-reviewed manifest/helper hashes and uses the root-verified task/session ID01a0812d-3ff0-7ed0-a06c-4df61b62a459 for both owner fields. It does not substitute the child agent task ID.

Inputs: the S6D report directory, reviewed native v3 manifest (ec110adcbaf230c5f33b49629967e163f5d526b7a339123c05fb000a14d7138f), helper(29ccc47374d8830d72b5214e64e62c08c41ad141265571fb149a5420fe0aed12), current reviewed runner/wrapper/readmes and frozen native application files. Existing interpreter+psutil are sufficient; no install/conda activation. No model asset audio is read or changed by preparation; large assets remain once-validated by native constructors if root later runs the pilot.

Outputs: runner/source_epoch_ready_v2 copies reviewed sources and preserves ready_v1. runner/native_pilot_proposed_v1 contains PROPOSED_QUEUE.json, PROPOSED_APPROVAL.json and PROPOSED_ADMISSION_CHECK.json. These directories must be new. Protocol output paths are declared under report/runner/production_protocol_v1/<job>; native outputs stay at the manifest's exact G: paths. Twelve serial jobs use360s outer timeout,180s progress-stall allowance,45s stale heartbeat warning and75s STOP grace around the native helper's180s cell limit/60s drain. Root must review these numerical margins before adoption.

The proposed approval is intentionally rejected by the runner: authorization_ref=null and approved_job_sha256 is empty. Candidate job hashes are stored only in proposed_job_sha256. The script performs an in-memory structure check with a clearly nonpersisted review-only approval, then verifies the persisted pending approval is rejected. Root must create a separate adopted approval citing actual authorization and exact reviewed job hashes, bind its hash and perform --validate-only before any production launch. Preparation is not authorization, model execution or scientific success.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' "$sim\scripts\s6d_runner_prepare_native_pilot_v1.py" --report "$sim\reports\S6D\20260913T195357Z"
```

Anaconda Prompt or Command Prompt:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%SIM%\scripts\s6d_runner_prepare_native_pilot_v1.py" --report "%SIM%\reports\S6D\20260913T195357Z"
```

On deliberate revision, preserve existing proposed files and change the output epoch/version in a new helper revision after review. Do not delete prior proposals or overwrite source epochs. The parent runner README documents root launch/resume; no production command is executed by this preparation script.
