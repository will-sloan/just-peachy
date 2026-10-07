# Capacity-governed personal gallery draft

This maintained draft removes the inherited global 256-person quota, 20-reference quota and 256-selected/display-ID quota. It preserves actual naming, encoder-specific namespace and preprocessing, UUID/root ownership, duplicate-source checks, vector shape/dtype/checksum checks, quality evidence, consent, atomic metadata replacement and no-overwrite imports. Frozen build31 is unchanged. No model weights or calibration gates change.

Runtime files are `personal_gallery.py`, `capacity_personal_store.py`, `application_contract.py`, `gallery_capacity_admission.py` and the narrow `installed_engine.py` derivative. The paired worker change has its own `README_GALLERY_WORKER_CAPACITY.md`. These runtime modules are imported by the staged application; they are not standalone native commands. Do not copy them into an installed immutable release in place.

`capacity_store_type` derives only three exact count conditions from the manifest-pinned installed `app/people.py` (SHA256 `9005a8c987961100c45fdb63ddb23d2969a4e690b8f5e78141ed6571b5714ea5`). All remaining original validators/math and bound module globals run unchanged. The runtime adapter derives only the baseline count rejection or the N2 count limb from their exact pinned admission methods, retaining N2 receipt count integrity and backend/namespace checks. The profile's `max_gallery_profiles` field remains in its immutable historical profile document and validation; normal product gallery admission records it diagnostically and uses actual allocations instead of that count quota. Research manifest-path loading is not broadened.

Inputs are an owned encoder-specific personal directory, validated backend/namespace, original route/quality evidence, optional selected UUID list, validated storage budget and the existing owner/RAM guard. Outputs are validated personal records, summaries, model-compatible original gallery objects, capacity diagnostics, or consented unencrypted archives. Archives contain personal vectors; the host tests use only explicitly synthetic vectors and metadata. No private vector/text payload is printed into evidence.

Metadata is validated one person at a time. The optional detached metadata cache is at most 8 MiB; larger rosters remain iterable and the list API admits them when actual memory permits. Before the original gallery constructor, metadata and vector bytes determine the reserved working allocation. Admission keeps the 192 MiB available-RAM floor and the existing finite POSIX address-space limit. Allocation estimates reserve 12 times serialized metadata and four times input/vector matrix bytes for Python objects, centroids and matrices. They are memory safety estimates, not a roster quota or a guarantee of unlimited matching capacity/performance.

Export streams payloads, manifest and a temporary membership ledger in 16 KiB blocks, then independently reads every archived payload and unchanged source hash. Both the export destination and gallery-root temporary files check the actual physical reserve. Import streams payloads into a private same-filesystem temporary directory, reserves for the actual ZIP central directory/manifest allocation, validates the whole staged membership through the selected capacity store class, and atomically publishes absent UUID directories only. On failure, only newly published UUIDs are rolled back. It removes whole-archive 16 MiB/6000-entry quotas after introducing streaming and allocation checks; individual 128 KiB person metadata, 4 KiB NPY, 256 KiB script, and 32 KiB provenance safeguards remain. Application intent remains a bounded individual 64 KiB message. Installed `atomic_json` has no independent count/size quota: it retains a CreateNew temporary file, fsync and atomic replace.

## Focused host regression

Run `run_host_gallery_capacity.py` only after root coordination confirms one free CPU14 host process. The runner registers its owner before project reads, backs up and independently restores all source inputs, binds both frozen31 and installed manifests, runs pure host fixtures, checks fixture/source closure, and returns naturally. It loads original pure validators and NumPy; it never loads models, opens devices, runs SSH/native actions, edits runtime data, or makes a publication ZIP. Synthetic temporary ZIP fixtures are authorized for these changed regression cases only.

The maintained check sources are `test_capacity_personal_store.py` and `test_gallery_worker_capacity.py`. They exercise 257 people, 21 references, selected/display rosters above256, streamed aggregate archive payload above16 MiB/import above256, unchanged invalid vector/checksum/namespace/no-overwrite rejection, actual RAM/free-floor refusal, cross-filesystem export-temp guarding, and the worker's streamed1034-member snapshot. This is integration/validity evidence, not speaker quality, model startup, throughput or natural-conversation evidence.

PowerShell (fresh nonexistent output required):

```powershell
$draft = 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\core_repair_20261006\capacity_gallery_20261006'
$out = 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\audit-preparation\gallery-capacity-UNIQUE'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' "$draft\run_host_gallery_capacity.py" --output $out
```

Command Prompt and Anaconda Prompt (use the same exact configured interpreter; do not install dependencies or activate an unrelated environment):

```bat
set "DRAFT=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\core_repair_20261006\capacity_gallery_20261006"
set "OUT=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\audit-preparation\gallery-capacity-UNIQUE"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%DRAFT%\run_host_gallery_capacity.py" --output "%OUT%"
```

Choose a new `UNIQUE` name each run. Read `RESULT.json`, `SOURCE_CLOSED.json`, `SOURCE_UNCHANGED.json`, `HOST_EXIT.json` and the bounded test log. Root must independently check the exact PID/creation FILETIME is absent before another host Python owner starts. Source-only preparation is not a PASS. Native Start257 and model-scale memory/performance remain pending until a separate root-authorized staged build check; host fixtures do not prove them.
