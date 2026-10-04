# Discover the complete current backup scope before copying

Purpose: prepare an exact scope from current source/data membership rather
than infer that an old source-only backup includes recordings or galleries.
`discover_production_backup_action_v2.py` is read-only and runs through the
existing native ownership/lease precheck. The preparing agent does not run it.
It holds the research and hardware exclusion leases while reading filesystem
metadata; it opens no audio stream and constructs no model.

It reads actual v27/v28 `control/RELEASE.json` recording-root references and includes
every existing `field-operator-sessions-v<number>` root in the campaign, even
when absent from those two lists. It includes existing versioned profile and
gallery roots, every current `data` and `config` child (including calibration),
all11known retained Desktop files, kanshi, disabled autostart, start-prototype,
the actual current selector and the release source named by that selector.
Missing known roots are reported explicitly. Only an actual empty or exact
RESERVED-only indexed journal slot, with no source root, independent backup
slot or start/owner/data receipt, permits an uncreated future reservation.
It does not invent absent roots or silently omit prior recordings.

The current observed selector names
`/home/peachyprototype/JustPeachy/install/releases/proto1-cm5-20260923-rc5`.
Frozen08's backup helper does not support that outside-campaign tree. Use the
separately pinned external helper described in `README_BACKUP_EXTERNAL.md`;
do not edit08 or claim it already had this support.

Discovery is bounded at64roots,4096regular files and2MiB of result metadata;
it rejects symlink/special/shared-link sources and oversized membership for
separate review. It records full member paths/lengths and selector/release
metadata hashes, without hashing or copying model weights. `hashes_verified`
is false: only the later locked native census and independent copies prove
content. Exceeding a bound stops, rather than dropping members.

## Inputs and outputs

Discovery input JSON contains actual `boot_id` and numeric `expires_unix`
within600seconds. Its output is `action_result` in the ordinary host operation
`RESULT.json`, including roots, all regular members/extents, campaign/Desktop
membership, missing known roots and actual selector/release receipts.

`prepare_production_scope.py` runs locally on CPU14 after publishing its actual
owner. Inputs: discovery result; reviewed JSON list of immutable model pins
`[{"path":"...","resolved_path":"...","bytes":123,"sha256":"..."}]`
(or `[]`); full independent PC-copy byte reservation; finite180–3600second
guard lifetime; actual08 package path/manifest pin; and fresh backup label.
Only explicit current model-weight extents may be excluded as external
references. Settings/configuration, recordings and galleries remain copied.
The native guard will still verify every model hash independently; a local
pin is never a fabricated current-byte proof.

Outputs in a fresh private directory: `REGISTERED_OWNER.json`, `SCOPE.json`,
`PAYLOAD.json`, `PREPARATION.json`, and independent input/helper backup+restore
copies. The scope reserves all observed non-model bytes; insufficient capacity
or missing known roots fails. Unsupported roots remain in the saved scope and
are reported, never silently removed. `complete_backup_claimed` remains false.

## PowerShell

Set `N`, `Q` and the qualified interpreter as in `README_STORAGE.md`; no new
environment installation is required. Root/operator executes native discovery
only after current jobs close and mirrors finish. The preparing agent did not.

```powershell
& $py -B "$n/host_operations.py" --label production-scope-01 --action "$n/discover_production_backup_action_v2.py" --payload "$q/reviewed-scope-discovery.json"
& $py -B "$n/prepare_production_scope.py" --discovery "$q/operation-production-scope-01/dispatch/RESULT.json" --external-model-pins "$q/reviewed-current-model-pins.json" --maximum-payload-bytes <reviewed-independent-copy-bytes> --runtime-seconds 1800 --package /home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-08 --package-manifest-sha256 <actual-admitted08-manifest-sha> --label production-backup-01 --output "$q/production-scope-01-preparation"
```

## Command Prompt and Anaconda Prompt

Use the identical arguments with the qualified interpreter; no activation or
dependency installation is needed:

```bat
"%PY%" -B "%N%/host_operations.py" --label production-scope-01 --action "%N%/discover_production_backup_action_v2.py" --payload "%Q%/reviewed-scope-discovery.json"
"%PY%" -B "%N%/prepare_production_scope.py" --discovery "%Q%/operation-production-scope-01/dispatch/RESULT.json" --external-model-pins "%Q%/reviewed-current-model-pins.json" --maximum-payload-bytes <reviewed-independent-copy-bytes> --runtime-seconds 1800 --package /home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-08 --package-manifest-sha256 <actual-admitted08-manifest-sha> --label production-backup-01 --output "%Q%/production-scope-01-preparation"
```

Do not literally execute the angle-bracket placeholders. Choose capacity from
the actual discovery and independent C:50GiB/G:75GiB reserves, then inspect
the saved scope and allocation before launching the finite copy. Subsequent
steps are in `README_BACKUP_EXTERNAL.md` and `README_PRODUCTION_BACKUP.md`.

Focused host tests: use the CPU14 early-owner wrapper from `README_STORAGE.md`
with `test_production_scope`. Synthetic isolated fixtures check inclusion of
historical/current recordings, galleries/calibration/selected source, refusal
of missing known recordings, exact model extent references and full-copy
capacity. They do not contact the Pi or prove a current production backup.

## Explicit absence of unused retained slots

A retained release may reserve future roots that never existed. Discovery
reads the actual `control/RELEASE.json` root-to-slot ordering and checks the
corresponding real `recordings/recording-NN` directory. Empty membership proves
UNUSED; exactly one valid policy/root/slot-bound RESERVED.json can prove
RESERVED_NEVER_STARTED. An absent journal directory, STARTED/OWNER/FAILED/data
file, independent backup directory, changed policy or ambiguous membership
never qualifies. The missing path and all evidence stay in the scope receipt.

The external native helper rechecks each explicit `absent_reserved_slots`
proof under its actual snapshot leases both before and after its full census,
and again during final source verification. If a formerly unused source or
any start/owner/data evidence appears after discovery, the backup fails. No
generic ignore-missing rule or old fixed-slot limit is added to new storage.

## Read-only discovery02 lossless grouping

Actual discovery01 stopped before copying because enumerating every direct
`data`/`config` child as a separate root exceeded64roots. Keep its source and
failed receipts. Version2 selects each complete existing data/config tree as
one root; it still enumerates every descendant file and preserves calibration,
recordings, galleries and settings. No root/file bound is raised and no member
is filtered out. If other current roots still exceed64, the read-only result
returns the complete bounded root list with an explicit review-required issue,
so the constructor cannot admit an incomplete scope. The4096file bound remains.
The external copy helper must explicitly support the two whole directory roots
before transfer; this read-only action does not imply that support or copy data.

Run `test_production_scope_v2.GroupingTests` through the early CPU14 wrapper.
The two focused checks preserve100direct data children in one complete scope
and verify that65additional operator roots produce a complete diagnostic list
rather than silent omission. Native discovery02 remains a separate operation.
