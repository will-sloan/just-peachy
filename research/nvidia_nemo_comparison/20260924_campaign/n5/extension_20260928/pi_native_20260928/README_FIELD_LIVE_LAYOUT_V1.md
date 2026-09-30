# Live output map and native text binding V1

Purpose: prepare a single explicit output reservation for the actual live B01 pipeline, including source/config/TRACE, diagnostics, closure, native events, native transcripts/S7 clocks, compact archive audio/events/controls, and the complete host mirror. This is preparation, not a capturable launcher or offline acceptance. Old V3 allocation and all prior code/results remain immutable.

The installed pipeline opens more than its 16MiB event journal: labelled and readable transcripts use `AsyncText` with `RotatingText`, whose rotation deletes older files. The vendor runtime also writes S7 clock trace, latest revised transcript, summary, finalization and consumer closure. These paths must be individually bound; one journal limit does not cover them.

`field_live_layout_v1.py` describes fixed source/control/config/receipt names; ten separately reserved producer failures/closures; independent presentation/gate telemetry; source TRACE12MiB; native events16MiB; three native transcript slots2MiB each; native clock trace4MiB; conversation events16MiB; float+PCM2080000frames; shared archive ordinary auxiliary1MiB; separate primary/pending/detail/failure allocations. Directory reserve64KiB per declared directory is counted once, then conservatively mirrored to host. No duration-based reduction, no assumed compression, no deletion or reset of prior usage. The exact calculated plan is written to `FIELD_LIVE_LAYOUT_V1.json` after the host checks. This selected output map still needs all actual bindings and a transitive source/path census; it is not proof of complete runtime write interception.

`field_native_text_v1.py` prepares a fresh-process binding for actual installed `PrototypeEngine._open_journal_text` and actual S7 TraceWriter. Events keep their separately bounded artifact sink. Labelled/readable text use exact named, nonrotating sinks. Each file checks its byte/write ceiling before writing, preserves partial writes, latches failure, and requests nonblocking Stop before diagnostics. Trace drains already accepted queue items after failure without publishing or claiming completion. JSON lines reject nonfinite decoded values. No model/source is loaded by binding. The original modules must hash-match before substitution. The final revised transcript and three native controls are explicitly still unbound; `NativeTextOwner.open` is available for the former but is not automatically inserted into the runtime method. No installed constructor, native text/trace execution, concurrency or physical source Stop is claimed by this wake.

The declaration registry rejects missing native text/source/host mirror bindings before a future entry can use its arithmetic. Its `installed` values are declared preparation records, not execution receipts or a security boundary. No command here launches capture. The future entry must verify actual module hashes and install every listed binding, preserve the installed FieldController backend/mode/artifact/storage checks, bind the mandatory Stop callback, and acquire fresh resource admission.

Inputs: local installed v12 mirror and fresh CPU14 host-only admission/census; no audio, weights or network download. Output: immutable `HOST_CHECKS_V1.json`, source pins, calculated reservation and small verified private source backup. The checks inspect real installed AST writer sites and test changed allocation omissions; no old native/model/UI/helper suite is repeated. Native writer implementation is prepared and syntax reviewed only. Keep private transcript paths/evidence private.

PowerShell (existing unique preparation; do not overwrite/replay a closed receipt):

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B check_field_live_layout_v1.py --preparation 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\field-live-layout-v1-preparation' --installed-mirror 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\field-artifact-install-v2-evidence\target\deployment\releases\b01-offline-20260930-v12'
```

Command Prompt / Anaconda Prompt (explicit interpreter, no install or conda activation):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B check_field_live_layout_v1.py --preparation "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\field-live-layout-v1-preparation" --installed-mirror "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\field-artifact-install-v2-evidence\target\deployment\releases\b01-offline-20260930-v12"
```

The check pins CPU14 before any project read and requires the admission to be unexpired. A subsequent changed version needs a new preparation directory/admission. Pi hardware, baseline app, display270, existing policy and all closed files remain unchanged. Any larger output/payload allowance must be a fresh explicitly measured policy, not an edit to WINDOW_V5. Physical32GB/5GiB free floor, host floors, CPU/RAM/time limits and Oct1 17:42:44UTC deadline remain mandatory.


Current strict contract: `field_live_layout_v2.py` retains the V1 specification, but compares canonical encoded values instead of Python dictionary equality. V1 allowed Boolean/integer and float/integer equivalence in its declaration check; it was not deployed. V1 files/14-case receipt are preserved. Three new V2 cases reject True and 1.0 in an integer maximum and accept the exact contract; the earlier suite is not rerun. The prepared native writer imports V2. Post-check edit drafts were preserved and V1 exact prior bytes restored before publishing V2.

Run the changed type checks from the same directory/interpreter, with the same unexpired host-only admission:

```powershell
& $py -B check_field_live_layout_types_v1.py --preparation 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\field-live-layout-v1-preparation'
```

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B check_field_live_layout_types_v1.py --preparation "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\field-live-layout-v1-preparation"
```

Calculated reservation: target79,999,532B, host84,193,836B (exact target mirror +4MiB metadata), combined164,193,368B. This proposal is unadmitted. It exceeds current WINDOW_V5 headroom; neither policy nor usage changed. A larger allowance requires fresh measured admission after the remaining bindings and full path census are implemented. Native text/trace code has not run; its actual resource cost and failure-to-source Stop are not established.
