# Serial paced dispatcher V1

`s6c_paced_dispatch_v1.py` launches a finite, explicitly approved queue of existing paced batch runners one at a time. It does not select candidates, alter their manifests, change resource/model/timing settings, perform scientific analysis or grant native execution permission. Source checks are implemented in `test_s6c_paced_dispatch_v1.py`.

Only the exact held canonical, arrival-sentinel and cross-route fast_v2 entrypoints and historical B00/B01/B36 paced fast_v1 entrypoints are allowed. Continuous helpers are excluded. The original runners retain all source, resource, owner, reserve, timeout and quiet checks.

No actual queue or dispatcher execution is included in this source preparation. Root supplies the reviewed finite queue and quiet authority after the first runtime/analysis handoff passes.

## Inputs

The CLI takes two explicit absolute JSON path/SHA256 pairs. Every nested binding has exactly `path`, `bytes`, `sha256`, generated from the exact file buffer. Queue schema:

```json
{
  "schema": "s6c-serial-paced-queue.v1",
  "status": "REGISTERED_FINITE_QUEUE",
  "namespace": "remaining_batches_v1",
  "items": [{
    "item_id": "EXACT_BATCH_ID",
    "helper": {"path": "ABSOLUTE_HELD_HELPER.py", "bytes": 123, "sha256": "EXACT_SHA"},
    "manifest": {"path": "ABSOLUTE_MANIFEST.json", "bytes": 123, "sha256": "EXACT_SHA"},
    "cells": 40,
    "output_root": "EXACT_ORIGINAL_MANIFEST_OUTPUT_ROOT"
  }]
}
```

The queue has 1–64 unique items, manifests and output roots. The original manifest's exact jobs/count/source-helper/schema/root/deadline must match. Existing invocation directories are refused: this dispatcher neither resumes nor diagnoses a prior batch. An already prepared manifest is allowed; preparation is not execution.

Separate root authority schema:

```json
{
  "schema": "s6c-serial-paced-authority.v1",
  "status": "AUTHORIZED_SERIAL_QUIET_PACED",
  "queue": {"path": "ABSOLUTE_QUEUE.json", "bytes": 123, "sha256": "EXACT_SHA"},
  "dispatcher": {"path": "ABSOLUTE_s6c_paced_dispatch_v1.py", "bytes": 123, "sha256": "EXACT_SHA"},
  "all_other_model_hil_work_stopped": true,
  "all_heavy_analysis_stopped": true,
  "expires_utc": "ROOT_APPROVED_AWARE_UTC"
}
```

The examples are schemas, not actual authorization. Expiry must be in the future and no later than **2026-09-13T11:35:40Z**. Each batch receives a new immutable `QUIET_ADMISSION.json`, bound to that exact manifest and the root authority, expiring at the earliest manifest/authority/stage deadline. The queue, authority, helper and manifest are rechecked before every launch. A shared quiet lease or stop request prevents the next launch. Root must maintain the declared quiet interval; the dispatcher is not a global process census.

## Execution and closure

The dispatcher invokes only `EDGE -B HELPER run --manifest MANIFEST --quiet-admission NEW_QUIET.json`, with the native window hidden. A successful Popen is recorded immediately before PID creation-time lookup. If lookup fails, its Popen handle/PID and failure are retained without inventing a creation time. No process is killed and no quiet lease is removed, including after interruption or expiry; root must resolve any possibly live child before another run.

The small 15-second heartbeat reports dispatcher/child identity, completed batches/cells and elapsed wall time. It performs no storage traversal or heavy telemetry scan. Original runner heartbeats/resource observations remain separate. The dispatcher waits for the original coordinator to exit, requires return code zero and a closed exact PID/creation identity, and then checks:

- C/sentinel/cross: one original `LAUNCH` → `OUTCOME` → `CLOSURE`, exact manifest/quiet binding and owner, all requested jobs complete, no errors/cleanup uncertainty, released original archived lease and per-cell COMPLETE owners closed.
- Historical paced: one original `LAUNCH` → `COMPLETION` plus `QUIET_OWNER_CLOSED`, exact helper/manifest/quiet/owner/count, every original per-cell COMPLETE and recorded child closed. The historical completion record has no owner field; ownership is explicitly bound through its invocation launch and archived lease.

Any missing, partial, mismatched or unknown chain stops the queue. The shared active lease must be absent before progression. Per-cell completion metadata is read; declared payload/model/audio bytes are not reopened. This transition proof is separate from strict V7/native source/tail admission and post-analysis/scoring. `DISPATCH_QUEUE_COMPLETE` never means final S6C acceptance.

## Outputs

Fresh `REPORT/serial_paced_dispatcher/NAMESPACE` contains `ADMISSION.json`, replaceable `HEARTBEAT.json`, and immutable `RESULT.json`. Each item directory contains its quiet admission, `RUNNER_LOG.txt`, immediate `SPAWNED_PROCESS.json`, finite `LAUNCH.json` or `LAUNCH_FAILURE.json`, `PARENT_EXIT.json`, and successful `BATCH_TRANSITION.json`. Native results stay in the original output roots. Failures preserve completed entries plus the active/possible child fields. No automatic retry, skip or resume exists.

## PowerShell

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
$edgePy = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $edgePy -B test_s6c_paced_dispatch_v1.py --output '..\reports\S6C\20260910T123540Z\serial_paced_dispatcher\source_checks_NEW'
# Run only with root's exact reviewed queue and authority; replace all placeholders.
& $edgePy -B s6c_paced_dispatch_v1.py run --queue 'ABSOLUTE_QUEUE.json' EXACT_QUEUE_SHA --authority 'ABSOLUTE_ROOT_AUTHORITY.json' EXACT_AUTHORITY_SHA
```

## Anaconda Prompt / CMD

The exact existing interpreter requires no environment installation or activation.

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B test_s6c_paced_dispatch_v1.py --output "..\reports\S6C\20260910T123540Z\serial_paced_dispatcher\source_checks_NEW"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B s6c_paced_dispatch_v1.py run --queue "ABSOLUTE_QUEUE.json" EXACT_QUEUE_SHA --authority "ABSOLUTE_ROOT_AUTHORITY.json" EXACT_AUTHORITY_SHA
```

The fixture command produces only a source-bound `SOURCE_CHECKS.json` and temporary synthetic closure/launch files; Popen is mocked. It starts no batch or model. Choose a fresh check output path every time.
