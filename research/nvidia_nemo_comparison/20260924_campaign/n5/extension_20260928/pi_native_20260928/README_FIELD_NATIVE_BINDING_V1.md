# Actual native writer binding preparation

Purpose: finish the native transcript/control binding needed by the live delivery composition. This is an importable production adapter, with no capture command or model test in this preparation. Runtime acceptance remains open.

`field_native_binding_v1.py` checks the exact installed pipeline, vendor runtime and S7 module hashes, verifies the actual class chain, compiles four narrowly changed methods, and installs them only after validation. It reuses separately bounded native event journals. The revised transcript goes through the fixed 2MiB/64KiB-write sink. Summary, finalization and consumer closure each get a 64KiB primary plus a 64KiB pending reservation. Payload construction, scheduler finalization, lane/model release and consumer-drain checks remain from the installed source. Only publication blocks change; summary's old Windows replace retry is removed. A second control attempt rejects, including after an after-replacement fsync failure. No partial is deleted. The finalization error handler retains its original failure behavior.

`NativeOwner` requires a precreated empty session parent and permits one native-session entry per fresh process, reserving that attempt before session creation. It pins all text/control files to that session. It requests the supplied nonblocking Stop callback before diagnostics. The callback must signal the real source Event and latch the controller failure; it must not join workers. This adapter does not itself construct the controller or source, acquire a resource admission, or establish hardware closure. The process-local publication latch is not durable crash recovery.

`field_native_text_v2.py` preserves the V1 fixed sinks and real AsyncText/S7 binding, adding Stop/error handling for close errors and an initial trace-open failure. It is a fresh derivative; V1 remains unchanged. Neither derivative has native execution evidence yet. The four text sinks are nonrotating, retain earlier/partial bytes, and enforce their individual file/write maxima. No transcript is exported to Git or this handoff.

Inputs to `bind(pipeline, runtime, trace_module, owner, pins)` are the actual installed modules, a NativeOwner, and exact manifest-derived SHA256 strings for `pipeline`, `runtime`, and `trace`. The caller must install it in a fresh, single-run process before any native session. Outputs are in the already admitted native session directory; the returned object describes bindings, not execution proof. Before capture, the entry must also bind source/config/transport/TRACE, archive and controller, preserve FieldController restrictions, enforce all layout/cardinality/host-mirror maxima, and obtain a fresh target-inclusive admission. The unchanged proposed full layout is 79,999,532B target plus 84,193,836B host and remains unadmitted.

The preparation check reads the exact installed release manifest/source, derives/compiles changed methods, and checks that the unaffected native cleanup/payload AST remains intact. It does not import the installed native runtime, use detached Controller fixtures, run source/models, or rerun old component suites. It writes one immutable private receipt and refuses an expired admission or existing receipt.

PowerShell:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B check_field_native_binding_v1.py --preparation 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\field-native-binding-v1-preparation' --installed-mirror 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\field-artifact-install-v2-evidence\target\deployment\releases\b01-offline-20260930-v12'
```

CMD or Anaconda Prompt (explicit existing interpreter; no install/activation):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B check_field_native_binding_v1.py --preparation "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\field-native-binding-v1-preparation" --installed-mirror "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\field-artifact-install-v2-evidence\target\deployment\releases\b01-offline-20260930-v12"
```

These commands document this unique preparation. Do not replay a closed check. New changed work needs a fresh directory/admission. The check pins CPU14 before reading project files. Original app, display270, policies and all earlier bound evidence remain unchanged. Final deadline remains October 1, 2026 at 17:42:44UTC.
