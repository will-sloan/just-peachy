# Retained timing coverage audit

Purpose: determine whether the already-reviewed full-file Windows lifecycle evidence supports complete per-component timing totals. This reads existing receipts and bounded/rotated event journals; it performs no inference or model/device access. It checks event publication sequence coverage and counts retained D1, E0 and ASR dispatch cost entries. Values from retained entries are explicitly partial observations. It does not turn session elapsed time into compute RTF or assume costs for missing events.

Inputs: independent `a0-d1-e0-v2` and `a2-d1-e0-v1` lifecycle reviews, their bound phase results and existing `events.jsonl*` files. Outputs: a fresh private compact JSON with SHA256 bindings, event sequence range/gaps/duplicates, retained cost counts/sums, original lifecycle totals and explicit unavailable full-component RTF. Audio, embeddings and transcript contents are not emitted in the audit. No new model execution, hardware, training, capture, playback, downloads or enrollment. Run after the current numerical/preflight owner closes; the reader pins itself to CPU14.

PowerShell / Anaconda PowerShell:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B audit_retained_costs_v1.py --output 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\RETAINED_COST_AUDIT_V1.json'
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B audit_retained_costs_v1.py --output "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\RETAINED_COST_AUDIT_V1.json"
```

Use the existing environment directly. The command refuses an existing output. Any later justified audit uses a fresh receipt; do not repeat this static audit as a performance experiment. A complete accounting study needs persistent aggregate counters, including native calls that produce no frames, separate load/pacing/drain, and actual backend-specific ASR timing fields. No current full N4/N5 or Pi speed qualification follows from this audit.
