# Gallery maintenance capacity

Purpose: remove the inherited 1024-member and 16 MiB aggregate refusal from
the private backup taken before enrollment Save, rename, delete and import.
The old helper's fixed 32 MiB hard file-size limit also blocked larger gallery
exports. These are normal gallery workflows, separate from the already repaired
used-gallery snapshot and first seed copy.

Status: source-only derivative of immutable build31 `gallery_worker.py`, SHA
`d270f6823bb0ec64b9f2dc85852cff6afd4d131e62d29621d58b73581defdb40`,
package manifest
`4b9e8fbc5c121435ecd46684b8bf55aa0996917e23892e883979668511d43767`.
Frozen31 and installed model/store sources remain unchanged. The corrected
combined host run passed all 20 cases (nine worker cases), with zero skips,
errors or failures. Receipt root is
`Q/audit-preparation/gallery-capacity-a525d42233084aa6b698420e3a371a5d`;
`RESULT.json` SHA256 is
`640d8da80ed93f85c2deaddd4da8dfe44a30241f415ad2cc16bc1c788162e182`.
The early CPU14 owner PID55404/creation FILETIME134357907885096802 exited
naturally0 and was independently absent; all 129 source backup/restore pairs
matched and fixtures closed. The first run remains preserved: two archive
fixtures correctly rejected their omitted explicit consent; only those host
fixture calls were corrected. Runtime/worker test bytes were unchanged.
No native dispatch, real gallery mutation or model execution was performed by
these fixtures. Native qualification remains pending separately.

`snapshot_gallery(root, destination, guard, budget=...)` walks one source member
at a time with explicit `os.scandir` iterators. It retains only the active
directory iterators; it does not use pathlib's per-directory materialized walk.
It writes each ordinary file to separate backup and restore copies
in 16 KiB chunks, fsyncs both, and independently verifies source/copy hashes and
source identity. Membership is streamed into the original receipt schema:
`files` (path, bytes, SHA256), `bytes`, `complete`, and
`scope="encoder-specific personal gallery before mutation"`. No list of the
whole gallery or its vector bytes is retained in working memory. Partial output
is retained; a complete receipt is published only after all readbacks succeed.

Every copy and receipt append preserves the actual StoragePolicy byte/fraction
reserve. The destination must be new, canonical, and outside the source tree;
source and target ancestors reject symlinks/reparse points. Files require one
link and a regular type. Individual files retain their 2 MiB validation bound;
individual receipt rows retain 256 KiB. Original namespace, source integrity,
consent, parent identity/acknowledgement, owner/RAM guards, 510/600-second helper
lifetime, model admission, 768 MiB address space, 1 MiB stack, CPU2/3 and command
parser limits remain. These are finite utility/working-set checks, not a total
gallery population or storage quota.

The bootstrap soft file limit remains at most 32 MiB until the validated binding
is read; its finite hard limit derives from actual filesystem capacity minus
the bootstrap reserve and never exceeds an inherited finite hard ceiling.
After binding/authorization, the soft allowance uses the actual StoragePolicy
reserve and the same inherited hard ceiling. `GALLERY_FILE_ALLOCATION.json`
records the measured filesystem, reserve and allowance. The worker's live guard
uses that same physical reserve. Export/import store methods remain separate
from this worker change and are audited by the paired capacity-store draft.

Inputs: the existing GalleryService's exact acknowledged request/binding,
encoder-specific private source gallery, new private snapshot directory, actual
free space and original owner/RAM guard. Outputs: exact backup/restore trees,
the same complete audit receipt, file-allocation metadata and the original
gallery state/result/closure evidence. No recording database, kept recording,
other encoder gallery or asset is read, deleted or replaced by this helper.

Runtime entry: include this versioned replacement only in a root-reviewed new
package. GalleryService invokes `gallery_worker.py --directory OWNED_DIRECTORY`
through the pinned native interpreter after creating its exact request/owner
acknowledgement. Do not invoke the worker directly on the PC or manufacture
native request/owner files. Use the new package's ordinary People/enrollment
commands and the separately reviewed stage/activation procedure.

## Focused host checks

`test_gallery_worker_capacity.py` has nine standard-library cases. It extracts
only the two pure helper ASTs for Windows compatibility and loads the exact
manifest-pinned frozen31 `runtime_support.py`. It never calls the native worker
entry, opens a database, imports a model or starts a microphone. Fixtures cover
a 1034-file gallery above 16 MiB, full independent copies/receipt, incremental
directory traversal with every member copied before the next entry, hardlink and
reparse/path rejection, physical pressure, corrupt restore rejection, retained
per-file bounds and finite capacity/inherited file ceilings. Fixtures are new
owned temporary files, unrelated to real gallery data.

PowerShell, after root assigns a host slot (fresh nonexistent output required):

```powershell
$g='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006/capacity_gallery_20261006'
$py='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
Set-Location -LiteralPath $g
$out='G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/gallery-capacity-UNIQUE'
& $py -B "$g/run_host_gallery_capacity.py" --output $out
```

Command Prompt and Anaconda Prompt:

```bat
cd /d "G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\core_repair_20261006\capacity_gallery_20261006"
set "JP_OUT=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\audit-preparation\gallery-capacity-UNIQUE"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B run_host_gallery_capacity.py --output "%JP_OUT%"
```

Replace `UNIQUE` with a fresh label. The paired capacity-store README maintains
the combined runner's final count/schema and exact closure instructions. No
conda install or model download is required. Acceptance must use early CPU14
PID/creation-FILETIME registration, source backups and independent restores,
bounded output, zero skipped cases, fixture closure and independently observed
natural process return/absence. Update this maintained README with the actual
registered receipt and hashes after each authorized execution. Host fixture PASS
does not qualify native gallery operations or speech quality.
