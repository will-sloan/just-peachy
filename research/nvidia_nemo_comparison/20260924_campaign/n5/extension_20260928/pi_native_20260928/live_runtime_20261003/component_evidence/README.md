# Copied component evidence

Purpose: bind the experimental `chunk52_threads2` option to one actual completed
native build and same-source numerical comparison. Input is the exact private
`chunk52-threads2-01-review-01/REVIEW.json`; output is this unmodified metadata
copy, consumed by `native_variant.verify_component_evidence` before admission.
No audio, weights or probability arrays are included. This is not a production,
speaker-accuracy or sustained real-time qualification receipt.

Expected `chunk52_threads2_review.json` SHA256:
`8ef69dd6333c2a1432cb08fd34a905c60c49044cce869b89b43fc7cb3a926ef6`.
Do not reformat it. A changed byte is deliberately rejected.

PowerShell read-only verification (CPU14 first):

```powershell
[System.Diagnostics.Process]::GetCurrentProcess().ProcessorAffinity=[IntPtr]16384
Get-FileHash -Algorithm SHA256 -LiteralPath 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/component_evidence/chunk52_threads2_review.json'
```

CMD or Anaconda Prompt can invoke the same PowerShell command. For Python
verification, use the early-owner/CPU14 registered wrapper described in
[README_NATIVE_VARIANT](../README_NATIVE_VARIANT.md); do not execute an
unregistered model verifier. Hash checking loads no model and produces only the
observed digest. Native trial launch uses the reviewed root action and a fresh
process with separate release authorization.
