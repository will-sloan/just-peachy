# Prepublication conversation metadata and real consumer checks

Purpose: fix the V57 static gap in a fresh `b01-offline-20260930-v4` candidate. V1 valid copied-archive import remains a scoped pass; its bound source/admission/release and missing-metadata finding remain immutable. `field_archive_schema_v2.py` validates required creation/update timestamps, boolean audio state, epoch identifiers and structured annotations, with finite/depth/node/string bounds. Unsupported stored audio-review imports are explicitly rejected. `field_archive_v2.py` applies conversation validation before extraction, then checks decoded event/row types and source intervals before publication. A controller consumer callback is mandatory for import; it cannot be silently omitted.

`field_entry_v4.py` supplies that callback using a detached view of the actual controller, actual SessionStore.list/rows, history refresh and Controller.snapshot. It never swaps unpublished rows into the running UI. Projected caption IDs must be unique and display fields bounded/type-correct. Metadata/consumer failure leaves the public history untouched; any already extracted content stays private with a rejection receipt and counts toward512MiB. The existing atomic no-replace publication,512MiBprivate-root/5GiBfree/32MiBStart policies and no-automatic-delete behavior remain. No original baseline/pointer/config changes.

Inputs: fresh source-bound admission, existing original manifest-bearing V57 private export, exact saved raw/display references and staged prior release. No waveform/model recopy, inference, new capture, playback, training or enrollment. Prior ZIP/member/path/hash/resource guards remain. This change qualifies specific schema/consumer cases, not arbitrary application compatibility, authenticity of imported identities or speech quality.

Outputs: fresh code-only staged release, twelve targeted malformed conversation fixtures (internally correct transfer manifests, intentionally incomplete nonmetadata content; they must fail specifically at the metadata gate before extraction), five constructed row-type checks, one nonfinite check, one missing-consumer-hook rejection and two actual UI rejection cases. The crafted duplicate-ID full ZIP changes one compact journal while preserving original saved audio; its manifest remains internally correct. It must fail the actual controller projection before publication. Then the valid saved archive passes the changed installed UI import path with exact source file hashes/40display rows. This is21new negative checks, four GUI actions and one changed positive import, not a rerun of V57path/quota checks or prior model/capture passes. Rejected content/evidence is retained. Natural closure, resource limits and private backup require independent review.

Limits: WINDOW_V5 and fresh (<15min) host+target census;96MiB combined output reservation split48MiBtarget/48MiBhost, main768MiBAS/1MiBstack/CPU2,3/shared200%/Tasks64,300s runtime/60sStop/8MiBfile. Sampled stops640MiBaggregateRSS/192MiBavailable. Fixed32GBPi retains5GiBfree. Actual GUI opens idle under manifest/authority/data-root/180s expiry binding. No unsupervised launch. LiveStart/Stop/endurance and original baseline activation remain separate later boundaries. Every previous failure and the recipe pixel-stability mismatch remain preserved; no unchanged screenshot comparison.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B dispatch_field_archive_v2.py --census '<fresh HOST_CENSUS JSON absolute path>'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B review_field_archive_v2.py
```
CMD / Anaconda Prompt (existing interpreter, no activation):
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_archive_v2.py --census "<fresh HOST_CENSUS JSON absolute path>"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_archive_v2.py
```
Never reuse a completed output directory. Reader verifies exact input/release bindings, malformed manifest hashes, rejection/nonpublication receipts, changed valid import, actual limits, natural owners and a byte/hash-verified private backup. Audio/transcripts/ZIPs/screenshots stay private; only reviewed small code/docs are committed.
