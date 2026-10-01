# Runtime installation inspection V1

Purpose: collect the actual current Pi configuration, startup entry points, idle app identities, display, leases and resources needed by the production installer. This is read-only: no app Stop/restart, capture, model construction, firmware action or Pi file write. It does not establish offline readiness.

Inputs: existing private/local evidence roots, the immutable NATIVE_CLOSURE_V315.json historical identities, the selected collector19 source containing exact old nested OWNER pins, a fresh bounded host scope with room for1MiB metadata, and a new absent output directory. The current user completion boundary is October2,2026,14:14:20Z. No old deadline is extended. All sources and README must have exact backups and independent restores before use.

field_runtime_host_precheck_v1.inspect reads all matching private OWNER/supervision, lifetime/events/members and admission/result/preflight/envelope/census files. It writes compact counts and an aggregate path/content digest. All completed OWNER JSON is parsed; only the two exact historical7Bpartial HOSTfixtures are exempt. Actual host PID/create-time pairs are checked, excluding only this currently registered coordinator. Typed ownership closure is never a process identity. An alive prior host coordinator stops before SSH.

The native utility registers its actual boot/PID/start ticks before project inspection; CPU3/128MiB AS/1MiB stack/FSIZE0/55s alarm. It checks all recorded native owners plus the full previous closure identity list, with strict old nested-envelope pins and separate typed nonidentity closures. No unknown completed nested OWNER is ignored. It requires closed capture, free research/hardware leases, no active jp research units, original CM5/2GB/32GB device,5GiB free,192MiB available, saved auto-listen false and display270. It returns bounded startup files and current settings privately for backup planning.

Outputs: REGISTERED_OWNER, HOST_PRECHECK and details, READONLY_ADMISSION, raw STDOUT/STDERR/PHASE, early NATIVE_OWNER, raw independent closure check, and RESULT only after SSH readers/reap and inspector PID absence. All raw failures remain. Native output262144B, host phase65s, closure10s. No result authorizes a later mutation or proves physical cable/touch/noisy-world behavior.

PowerShell from the native report directory:
```powershell
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$l='G:\Just_Peachy_N1\20260924_campaign\local'
$b="$l\n5\research-extension-20260928\pi-native-20260928"
& $py -B .\inspect_runtime_install_v1.py --private $b --local $l --prior-closure "$b\NATIVE_CLOSURE_V315.json" --scope "$b\deployable-runtime-resume-v1\HOST_SCOPE_V23.json" --output "$b\deployable-runtime-resume-v1\install-inspection-v1"
```
CMD or Anaconda Prompt:
```bat
set "L=G:\Just_Peachy_N1\20260924_campaign\local"
set "B=%L%\n5\research-extension-20260928\pi-native-20260928"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B inspect_runtime_install_v1.py --private "%B%" --local "%L%" --prior-closure "%B%\NATIVE_CLOSURE_V315.json" --scope "%B%\deployable-runtime-resume-v1\HOST_SCOPE_V23.json" --output "%B%\deployable-runtime-resume-v1\install-inspection-v1"
```
The example scope expires and output is single-use. Use a fresh authorized bounded scope/output for a later inspection; preserve the original attempt. Strict known-host SSH settings come from the existing bounded host helper. Never use this tool to retry an app mutation.

