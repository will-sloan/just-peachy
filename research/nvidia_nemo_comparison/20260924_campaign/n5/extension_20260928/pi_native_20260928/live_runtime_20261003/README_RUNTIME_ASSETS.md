# Inventory the actual selected native model assets

`inventory_runtime_assets_action.py` is a read-only external action for the
existing guarded `host_operations.py`. It does not change frozen build08, start
a model/capture, download weights or copy large assets. The native helper's early
owner, CPU3/128MiB, write prohibition, alarm and all current lease/owner checks
remain enforced by that dispatcher. Run only after active jobs and mirrors close.

Input is a fresh JSON payload containing actual `boot_id`, numeric `expires_unix`
within600seconds, the exact staged build08 `package`, and its manifest SHA256.
After complete package verification it calls that package's actual
`required_assets` implementation for Pyannote, Delayed, Streaming and the explicit
two-thread variant with both embedding namespaces where applicable. Other
geometries share those same asset sets; this is not a quality or fit inference.
It includes the separately pinned TitaNet ONNX/frontend observed in the native
baseline, the selected Python executable and XVF control tool.

Output is `RESULT.json.action_result.assets`: exact path, resolved path, bytes
and actual SHA256. File identities are checked before and after streaming64KiB
reads. Bounds are128 assets,1GiB/file,4GiB total and60seconds. The result establishes
local asset identity only. Physical RAM, address-space fit, live functionality,
performance and quality need their separate execution evidence.

PowerShell, with an actual reviewed fresh payload:

```powershell
$PY='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
$N='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003'
& $PY -B "$N/host_operations.py" --label selected-assets-01 --action "$N/inventory_runtime_assets_action.py" --payload 'FRESH_ASSET_PAYLOAD.json'
```

Command Prompt and Anaconda Prompt use the same installed environment:

```bat
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "N=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003"
"%PY%" -B "%N%\host_operations.py" --label selected-assets-01 --action "%N%\inventory_runtime_assets_action.py" --payload "FRESH_ASSET_PAYLOAD.json"
```

Do not pass `--writes`. The wrapper registers CPU14 and its real host owner
before reads, backs up and independently restores this action and its payload,
then performs current native preflight before the action. Existing labels are
single-use. Preserve failures; a hash mismatch does not authorize replacing a
model. Feed only reviewed actual inventory rows into production acceptance.
