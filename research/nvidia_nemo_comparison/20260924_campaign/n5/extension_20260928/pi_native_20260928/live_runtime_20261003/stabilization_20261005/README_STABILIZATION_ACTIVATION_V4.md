# Activate the build26 portrait shortcut

Purpose: point the sole owned Just Peachy desktop entry at immutable build26,
after actual current-boot portrait/physical-capture/closed-worker PASS. V4's only
executable change from V3 is the permitted package basename25→26; the native
transaction, rollback, proof, storage and data-integrity guards are unchanged.
Build25 activation remains its original verified result. Actual build26
desktop-only activation PASSED; no application or capture was started.

Inputs: exact package/manifest/data_root, native_check_path/native_check_sha256,
autostart_sha256, observed previous_desktop with exactly one path/SHA and fresh
evidence_root. Current desktop expected SHA must come from real prior evidence;
it may be historical CAS expectation, which the transaction checks freshly
before any backup/mutation. Disabled login autostart is preserved. The native
proof must independently match current boot, manifest, actual portrait UI,
capture_function_passed and workers_closed. A Saved-only result cannot qualify.

Output: the freshly backed/restored before shortcut, atomically published new
shortcut and ACTIVATION.json with hashes. Code/models/calibration/galleries and
recordings are not modified; the app is not started and capture remains off.
The original16MiB independent allocation/free floor and bounded metadata remain.
There is no standalone bare SSH or direct activation CLI.

PowerShell, only using an independently prepared/closed actual payload:

```powershell
$PY='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
& $PY -B './host_stabilization_operations_v5.py' --label stabilization-desktop26-01 --action './activate_full_desktop_action_v4.py' --payload 'ACTUAL_CLOSED_ACTIVATION26_PAYLOAD.json' --writes
```

CMD and Anaconda Prompt:

```bat
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B host_stabilization_operations_v5.py --label stabilization-desktop26-01 --action activate_full_desktop_action_v4.py --payload "ACTUAL_CLOSED_ACTIVATION26_PAYLOAD.json" --writes
```

Root's fresh guarded wrapper checks native identities/resources/leases and
captures exact action/utility closure. Returned before/restore/new bytes require
independent PC hash/readback. No old proof is relabeled and no hidden autostart
or additional backend shortcuts are created.

Actual activation receipt: private operation-stabilization-desktop26-01/dispatch/RESULT.json; current boot 0561d730-3cad-48e0-940a-fe3930c89665.
The sole desktop SHA256 is d014baa64a8330bc802a59616c8d3a0874a97402d6ff9cef77d29c6dd8d24fe4.
The transaction freshly verified prior build25 SHA 85c61144e899e20f36c3353e9456af3134c72a83491d33815b5e56b0ca392a3a
before its independent native before/restore copies and atomic publication.
Returned before/restore/new bytes were independently reconstructed and read back
on the PC; this verifies returned bytes, not a complete native evidence-tree mirror.
Package manifest f4c9cc2fd841e3b240b8c16799858ec87839e265cc9f6f6dfbd0db6c772c55a0.
The original capture/portrait/closed-worker proof gate remains unchanged; Saved
replay alone did not authorize this mutation. App login autostart remains disabled.
