# Native continuation resource window V2

Purpose: implement the user's September 29 permission to adjust allowances for useful Pi operation, without changing any prior source, admission or ledger. WINDOW_V2.json keeps the October 1 17:47:34 UTC checkpoint and raises only the initial combined file-output allowance to 3 GiB. Existing files count; the 50 GiB payload ceiling/reservations, disk floors, CPU restrictions and original-app protection remain. No new downloads are scheduled. Capture still needs physical readiness.

`window_guard_v2.py` preserves V1 ownership, reservation, inventory, reparse and supervisor checks, with the V2 policy binding and 3 GiB output ceiling. Host `snapshot` is not target admission: native dispatch must add fresh target bytes to both total/window accounting, enforce target RAM/disk/time/CPU/ownership/lease rules, and bind its executed limits exactly. Default native virtual cap remains 768 MiB; a measured isolated component may use a fresh 1 GiB admission with at least 1.25 GiB available before dispatch. This is not a measured fit or integrated-mode acceptance. Larger adjustments require an explicit recorded engineering decision under the user's authority, never silent removal of guards.

Inputs: existing private campaign tree, immutable V1 receipts and new V2 policy; positive requested bytes. Output: a small private host census; no model, microphone, Pi access, download or UI. `test_window_guard_v2.py` checks budget boundaries and retained constraints without executing numerical work.

PowerShell, from the campaign worktree:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/test_window_guard_v2.py
```

CMD / Anaconda Prompt: `cd /d G:\Just_Peachy_N1\20260924_campaign\worktree`, then the same command without `&`, double-quoting the interpreter. Reuse the installed environment. Dispatchers call `snapshot(local, requested_bytes)` and write a fresh exclusive census; never overwrite preserved receipts. Original V1 launchers keep their original cap and must not be patched in place.
