# Bounded, lossless current-scope preparation

`prepare_production_scope_v3.py` is a host-only constructor for the actual compact
scope06 result. Earlier discovery attempts and preparers remain unchanged. The
native inspector's262,144-byte output limit is unchanged. The native action
returns a compressed transport envelope containing every original indexed fact;
the constructor restores that data before applying the existing V2 current-scope
and asset classification checks. No source members are dropped to fit transport.

Inputs: actual scope06 RESULT.json; actual same-boot selected-assets-01.json;
explicit full-copy reservation/lifetime; exact admitted immutable package pin;
fresh output directory and production-backup-NN label. Outputs remain SCOPE,
PAYLOAD, original input backups/independent restore copies, exact helper copies
and PREPARATION. They are preparation receipts, not successful backup receipts.
The script pins CPU14 and fsyncs the actual owner before any project/data reads.
It performs no SSH or native action.

Transport must contain exactly schema `just-peachy.production-scope-transport.v1`,
encoding `zlib-base64`, `uncompressed_bytes` at most2 MiB, lowercase SHA256 and
`payload` at most65,536 base64 characters. The decoder validates base64 and limits
zlib output to the declared size plus one byte; exact size/SHA, EOF, no trailing
stream or unconsumed input, and duplicate-free finite JSON are mandatory. Inner
schema is `just-peachy.production-scope-discovery.v2` and is decoded exactly once.

Up to64 roots and4096 members are reconstructed from integer `root_index`,
canonical `relative` and `bytes`. Absolute/traversing/noncanonical relative paths,
overlapping roots, duplicate members, bool indices and total mismatches are
refused. Empty relative names denote an exact root-file member with no descendants.
Original transport, inner hash and indexed-members hash remain in evidence.
The V2 constructor still preserves all historical exclusions and exact unused-slot
proofs, and keeps independently verified assets outside copy separate from
actual in-scope weight exclusions. See README_BACKUP_EXTERNAL_V2.md.

Actual scope06 decoded to26 roots,1932 files and657,980,201 copied bytes, with80
explicit historical exclusions and5 eligible never-started missing reservations.
All61 selected-asset references are outside the copy scope: no weight bytes are
subtracted. A640 MiB (671,088,640-byte) full-copy reservation covers those observed
bytes with13,108,439 bytes of margin;16 MiB metadata plus existing host mirror and
preparation allocations remain independent. Changed native membership still
refuses completion. Actual scope06 inner bytes221,634 hash to
`2ae3d7ad0b4c598fe31def4d71cd7427fba2b124063e5a88bfe05cf33345b17e`.

## PowerShell

Set package and manifest from the exact admitted package intended to run the
existing backup guard. Choose a fresh label/output and stamp preparation shortly
before the root-owned dispatch; the generated admission lasts600 seconds.

```powershell
[System.Diagnostics.Process]::GetCurrentProcess().ProcessorAffinity=[intptr]16384
$n='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003'
$q='G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003'
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B "$n/prepare_production_scope_v3.py" --discovery "$q/operation-production-scope-06/dispatch/RESULT.json" --external-model-pins "$q/selected-assets-01.json" --maximum-payload-bytes 671088640 --runtime-seconds 1800 --output "$q/production-scope-06-preparation-FRESH" --package $package --package-manifest-sha256 $manifest --label production-backup-01
```

Use the V2 external launch/reconciliation commands and separately backed host
runner in README_BACKUP_EXTERNAL_V2.md. No frozen runtime file is changed.

## Command Prompt or Anaconda Prompt

Run `powershell -NoProfile` and paste the same complete block. No new environment
or package installation is needed. For host-only checks, use README_STORAGE.md's
CPU14 early-owner test wrapper with `test_production_scope_v3`. The three focused
checks use actual scope06/assets metadata and malformed transport fixtures;
they verify exact decoding, copy totals, bounded decompression, trailing streams,
hashes, duplicate JSON and unsafe indexed paths. No native backup is claimed.
