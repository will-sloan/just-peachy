# Read-only native closure census

Purpose: collect compact, fresh closure/resource receipts without repeating model tests or the full payload admission census. This is an audit, not a dispatch admission or stage acceptance. It uses the existing strict SSH transport; no capture, playback, model loads, setters, downloads or process termination.

Input: an unused positive `--version`, this campaign's existing paths, exact expected Pi boot/original app identities and install/config hashes. It checks all recorded research PID/start identities and units, closed capture, both available leases, current storage/RAM/thermal/global swap observations, and exact host supervisor/launcher creation times. A changed boot/app/config or active owner fails closed and needs investigation; do not rewrite identities just to make the audit pass. Global swap is not per-job attribution. Storage counts are observations before the two small receipts are written.

Outputs are private `NATIVE_CLOSURE_V<number>.json` and `NATIVE_RESOURCES_V<number>.json` beneath `local/n5/research-extension-20260928/pi-native-20260928`. Existing receipts are never overwritten. Host runs on CPU14; target read-only collector on CPU3. Requires existing psutil/Python; no installation.

PowerShell (replace 20 with the next unused version):

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/collect_native_closure_v1.py --version 20
```

CMD or Anaconda Prompt, using the existing Python without activation:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/collect_native_closure_v1.py --version 20
```

Validation: the V20 audit ran against the actual Pi after the separately reviewed restart and quiet check. All101 recorded owners were closed and both leases free. It did not rerun either operation. Detailed per-run readers still govern acceptance.
