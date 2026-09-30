# Review retained dependency pins and candidate rollback

Purpose: independently review the completed `field-dependency-v2` run without repeating dependency collection, imports, models, capture or GUI. `review_field_dependency_v3.py` checks the retained lock and import probe, current dependency bytes and identities, exact release descriptors, all three pointer history entries, eight rejection receipts, preserved private canary/config/schema, actual limits and closed owners. It backs up every new target file and verifies the copied hashes.

Inputs: immutable V1 dependency lock/probe and failure review/backup; V2 admission, results and original baseline bindings. Outputs: private `field-dependency-v2-evidence/REVIEW.json`, `BACKUP.json` and exact target mirror. Host coordinator uses CPU14; the Pi reader uses CPU3/256MiB and disables bytecode. Audio, weights and runtime binaries are not copied. The completed reader must not be rerun into its existing destination.

PowerShell:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B review_field_dependency_v3.py
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_dependency_v3.py
```

The V1 pass reader was executed but rejected absent RESULT.json; the V2 failure reader preserves that failed run with a separately admitted host backup. V3 is the executed success reader for native protocol V2. The bound run README remains unchanged; this addendum records the later review limitation below.

## Static finding after the scoped pass

`field_dependencies_v2.activate` writes `previous.json` and `current.json` through `release_tools.write_json` before the bounded `exclusive` writer creates history. If the history write rejects quota, pointer publication has already occurred. The protocol's injected lower-limit test calls `exclusive` directly before any mutation; it does **not** exercise quota failure during activation or rollback. No such failure occurred in the passing V2 protocol, and its successful v5-to-v7-to-v5 sequence remains valid. Atomic failure behavior for the complete pointer/history operation is unqualified.

Before a launcher consumes these pointers, a fresh derivative must reserve/check all planned output before mutation and define recoverable commit/history semantics. Test the specific prepublication quota rejection with exact unchanged pointers/history and preserve malformed fixtures. Do not edit bound V1/V2 helpers, admissions, releases or evidence; do not repeat their passed catalogue/import/model checks. Current pointers remain isolated research metadata, unused by the original rc5 installer. No original baseline activation, relocation, endurance or field-release acceptance follows.
