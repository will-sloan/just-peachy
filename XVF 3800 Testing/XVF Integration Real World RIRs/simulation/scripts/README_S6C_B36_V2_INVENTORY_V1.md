# Explicit B36 V2 inventory metadata branch

Purpose: recognize the separately reviewed s6c-historical-paced-b36-fast.v2 coordinator and C-side lease archive in a private V7-compatible inventory namespace. Original V7, historical worker and all original schemas stay unchanged. No models, raw payloads or scientific arithmetic run here.

make_inventory(base_inventory=None) returns the namespace. The optional base is the already explicit recovered-controls namespace when a later reviewed whole-study join needs both branches; otherwise it delegates to unchanged held V7. Every unrelated schema, failed attempt and unknown branch delegates unchanged. Caller must bind this helper/README and the exact observer index; admit_observer_index remains the base V7 function (or existing recovered-controls admission). No default observer success is invented.

The new schema alone calls pinned B36wrapper.admit_plan, verifies40 byte-equivalent original job objects and original native driver/epoch, and returns the original admitted S6B spec. Invocation discovery is the identical V4 historical metadata function. The wrapper's admit_complete_batch verifies exact source/schema/owner/grid/C archive/observer counters and current closure. Its observer exit must also occur exactly once in the explicitly attached index. Closure points to the actual C LEASE_RELEASE.json, with a separate archived_lease binding; no original G closure is fabricated.

collect_job calls the unchanged V4 historical native row collector directly: that branch derives the actual worker command from plan.driver and needs no source or schema literal change. Native result, journal/source, launch, COMPLETE payload and owned-process checks remain original. A complete native row whose new closure admission fails becomes NATIVE_COMPLETE_OBSERVER_UNVERIFIED with its original physical/native identity retained. Missing, failed and partial native metadata are never upgraded. Recovery/archival produces no new physical session count.

collect reuses the identical held V7 collection code in private globals, supplying only these explicit metadata callbacks and augmented source bindings. This is not an actual census or final acceptance. A final whole-study run still requires fresh offline enumeration and explicit source/authority review; a stale prior snapshot remains insufficient. The actual prepared B36V2 manifest is passed as an explicit input; it is never treated as execution evidence.

## Reproduction and use

This helper is an API module, not a native executable. test_s6c_b36_v2_inventory_v1.py shares this README. Its inputs are pinned wrapper/V7 code and the two small prepared manifests; all completion/owner/observer cases are synthetic. It writes SOURCE_CHECKS.json in a fresh directory. No actual closed batch, runtime inventory or payload is read by its fixtures.

PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B test_s6c_b36_v2_inventory_v1.py --output '..\reports\S6C\20260910T123540Z\paced_controls\b36_inventory_checks_NEW'
```

Anaconda Prompt / CMD (existing interpreter):

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B test_s6c_b36_v2_inventory_v1.py --output "..\reports\S6C\20260910T123540Z\paced_controls\b36_inventory_checks_NEW"
```

Reviewed post-analysis adapters inject make_inventory() via the existing private Reader/source context. No shell inventory collection command is authorized by this source-only preparation. Later actual collection must receive an explicit bound finite manifest/observer-index and fresh offline prior from root, with all processes/quiet leases closed.
