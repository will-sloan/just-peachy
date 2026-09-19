# C epoch4 continuous fast observer wrapper

Purpose: separately admit and run the original continuous C epoch4 native helper over the existing 1827.426625-second composition, using the reviewed faster resource enumerator.

The frozen native body, epoch4 APP/models/profile routing, canonical inputs, gain, cue/gallery rules, source dispatch, lane drain, native sampling policy, CPU/thread policy, resource floors and deadlines are unchanged. The periodic full-scan timer additionally uses completion-to-next-start spacing described below. The scanner still replaces only the process-local frozen `common.tree_bytes` callable. Fast_v2 additionally corrects the observer's protected-code fingerprint as described below. The exact reviewed scanner is `s6c_historical_fast_observer_v1.py` (SHA256 579963cb5e873a0a08504bb4f022ea8a92a158886d36abfd87ee4a0f9cd6d299), using its common-mode tree_bytes API. It enumerates each current tree afresh with scandir and explicit fresh os.stat for each nondirectory size, with no cross-call size cache. File links follow target size; internal directory symlinks are skipped. Unreadable traversal fails closed, stronger than the old os.walk default; inaccessible/dangling file stat and unsupported reparse entries fail. These fixed campaign roots are directories. Existing scanner fixtures disclose optional link tests unavailable on this host; no general reparse-point equivalence is asserted.

Mandatory admission, between-cell and terminal full scans remain. Periodic full scans now start at least 20 seconds after the previous full scan completes, preventing consecutive scans when a scan exceeds 20 seconds. Cheap RAM/free-space checks remain at their original opportunities. The fresh-stat benchmark measured 40.4269 seconds; gaps of this magnitude can delay observer samples. The prior 13.071137-second f725 scan used potentially stale Windows hardlink directory-entry sizes (a tiny growth case gave 46 versus 58 fresh-stat bytes), so it is not installed or treated as exact accounting here. The old full resource probe was bounded between 46 and 81 seconds. The scans still consume host CPU/time, interrupt observer sampling and create irregular mixed-time observations. Report actual sample gaps and observed maxima, not continuous resource maxima or phonetic/GUI latency. No timing guarantee or 8-hour batch completion is implied. Canonical actual preparations should use separately declared per-profile 40-cell namespaces.

A required additive `observer_policy` binds scanner code and README. Original schema identifiers and report/payload directory families remain, while every new namespace must end `_fast_v2`. Old manifests are rejected; they are never rekeyed or overwritten. `observer_scope`, `install_observer_scanner` and `observer_entry` in the new long wrapper are reusable by separately reviewed adapters. Installation checks the exact frozen common source, its global function resolution and REPORT/STAGING/PAYLOAD roots. The decorator restores the original scanner in finally and verifies resource/admit functions were not replaced.

Separate `REPORT/observer_fast_v2/attempts/*.json` records bind the entry, actual argv/PID/creation time, manifest/job (when known), scanner source, metered per-root call/time/error counts and post-entry restoration status. They do not replace native outcomes, quiet-lease closure, or external PID/creation checks. Forced process termination can prevent this receipt; missing restoration evidence remains missing. A receipt write failure is fatal. Preparation/check entry receipts are not physical native sessions.

Prerequisites: use the existing environment and preserved bundle paths below; no package installation. Maintain these READMEs if new wrapper code changes. No fast_v2 actual paced/native run has been performed. The first fast_v1 C065 cell completed native work but failed its outer marshal-based protection guard; that failed outcome and every V1 file remain unchanged. Run commands require a separately source-bound quiet authorization that names the fresh manifest and confirms all other model/HIL/heavy analysis work has stopped. Never manufacture that authorization or reuse an old manifest's authorization.

Inputs: the exact old composition and its PCM/telemetry/model/epoch bindings, a registry candidate with explicit ASR/identity taps, fixed A/B or no gallery, a fresh `epoch4_..._fast_v2` namespace, and bounded deadline. The original 4 GiB pending output reserve and 7200-second wrapper bound remain. The original source-composition epoch2 and actual execution epoch4 stay distinct.

Outputs: metadata `REPORT/long_native_epoch4/<namespace>/MANIFEST.json`; invocation admission/outcome/closure there; native output under original `REPORT/long_session/<namespace>` and `G:/Just_Peachy_S6C/20260910T123540Z/long_session/<namespace>`; separate observer exit receipt. `source-checks` writes a fresh `REPORT/long_native_epoch4/observer_fast_v2/SOURCE_CHECKS_V1.json` and reads exact native dependencies/assets/source; it performs no neural call but is more than the pure fixture command.

PowerShell (pure checks first; preparation is an explicit subsequent step):
```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$edge = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $edge -B "$sim\scripts\s6c_long_native_epoch4_fast_v2.py" checks
& $edge -B "$sim\scripts\s6c_long_native_epoch4_fast_v2.py" source-checks
& $edge -B "$sim\scripts\s6c_long_native_epoch4_fast_v2.py" prepare --namespace epoch4_long_c065_o0_fast_v2 --candidate C065 --asr-tap O0 --identity-tap O0 --deadline-utc 2026-09-13T11:35:40Z
# Only after exact quiet admission, replace the last path with its actual authorized file:
& $edge -B "$sim\scripts\s6c_long_native_epoch4_fast_v2.py" run --manifest "$sim\reports\S6C\20260910T123540Z\long_native_epoch4\epoch4_long_c065_o0_fast_v2\MANIFEST.json" --quiet-admission C:\path\to\AUTHORIZED_QUIET_ADMISSION.json
```

Anaconda Prompt / CMD:
```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "EDGE=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%EDGE%" -B "%SIM%\scripts\s6c_long_native_epoch4_fast_v2.py" checks
"%EDGE%" -B "%SIM%\scripts\s6c_long_native_epoch4_fast_v2.py" source-checks
"%EDGE%" -B "%SIM%\scripts\s6c_long_native_epoch4_fast_v2.py" prepare --namespace epoch4_long_c065_o0_fast_v2 --candidate C065 --asr-tap O0 --identity-tap O0 --deadline-utc 2026-09-13T11:35:40Z
rem Run only with the actual separately authorized quiet file.
"%EDGE%" -B "%SIM%\scripts\s6c_long_native_epoch4_fast_v2.py" run --manifest "%SIM%\reports\S6C\20260910T123540Z\long_native_epoch4\epoch4_long_c065_o0_fast_v2\MANIFEST.json" --quiet-admission C:\path\to\AUTHORIZED_QUIET_ADMISSION.json
```

The C065 command is a reproducible control example, not operating-profile selection. Other exact conditions require their own manifest and full actual long session. Independent source/AST/closed-subtree tests are documented in README_S6C_FAST_OBSERVER_CHECKS_V1.md. Public `load_sources/admit` must be called inside `observer_scope` (entry commands already do this); pure metadata tools should use their own separately reviewed admission.



## Stable protection guard in fast_v2

Quiet recognition retains the original wrapper names and all fast_v1 wrappers and adds the new fast_v2 canonical, long, sentinel and cross names. No earlier active process becomes unrecognized through renaming. The initial V2 candidate/source receipt is preserved before this additive recognition correction.

The required `protected_guard_policy` manifest field pins the original s6c_long_session.py bytes, the complete structural code hashes of all six protected functions and this exact L wrapper. `code_sha256` now means the declared typed structural algorithm, never the old marshal digest. Source/module/global ownership and all six original function bodies are validated from the pinned whole-module compilation without executing it. Constants carry explicit types; nested code, tuples, frozensets, bytecode, names, variables, arguments, flags, location/line/exception tables and float/complex IEEE bytes are covered. Same-process function and code-object IDs are also checked, with strong object references held across the override so identity reuse cannot hide replacement. Only the three previously allowed observer functions may be temporarily replaced. Changed functions produce per-function before/after records in the exception; restoration remains mandatory.

This fixes demonstrated reference-sensitive marshal serialization, including the exact original source_bindings helper after normal pathlib use. It does not infer the unlogged per-function fingerprints of the earlier failure or relabel its outer result. Old manifests are refused; new namespaces end `_fast_v2`. Source/profile/PCM/cue/gallery/native algorithms, scanner579963cb, completion-to-next-scan spacing and limits are unchanged. Use test_s6c_protected_guard_v2.py and README_S6C_PROTECTED_GUARD_V2.md for the focused model-free regression tests. No automatic retry, migration or actual run occurs.
