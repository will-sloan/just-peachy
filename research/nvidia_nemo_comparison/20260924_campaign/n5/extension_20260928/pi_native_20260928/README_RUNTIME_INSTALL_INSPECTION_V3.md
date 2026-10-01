# Runtime installation inspection V3

V3 extends V2 only to obtain the specific F06/F12/F17 installer inputs: actual existing TitaNet ONNX/frontend/manifest paths and hashes, bounded read-only gallery file/directory hashes and sizes, and exact current start-prototype.sh bytes. It also includes every actual earlier install-inspection utility identity in the current native closure check. V2's strict historical owner equality, full host preread, resource/time/SSH/closure guards remain.

No model is constructed, gallery vector compared/converted, recording started or target file changed. Private gallery metadata and startup bytes remain private. Each gallery has<=256files/64dirs/32MiB per file/128MiB complete snapshot reservation; TitaNet candidates are<=32files/90MiB each. Symlink model candidates are reported as ineligible, not silently copied. These inventories are installer inputs, not deployed gallery/model proof. Sources require verified backup and independent restore before use.

Inputs and outputs follow README_RUNTIME_INSTALL_INSPECTION_V2.md. Use a new absent output and current scope. PowerShell:
```powershell
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$l='G:\Just_Peachy_N1\20260924_campaign\local'
$b="$l\n5\research-extension-20260928\pi-native-20260928"
& $py -B .\inspect_runtime_install_v3.py --private $b --local $l --prior-closure "$b\NATIVE_CLOSURE_V315.json" --previous-inspection "$b\deployable-runtime-resume-v1\install-inspection-v2" --scope "$b\deployable-runtime-resume-v1\HOST_SCOPE_V25.json" --output "$b\deployable-runtime-resume-v1\install-inspection-v3"
```
CMD or Anaconda Prompt:
```bat
set "L=G:\Just_Peachy_N1\20260924_campaign\local"
set "B=%L%\n5\research-extension-20260928\pi-native-20260928"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B inspect_runtime_install_v3.py --private "%B%" --local "%L%" --prior-closure "%B%\NATIVE_CLOSURE_V315.json" --previous-inspection "%B%\deployable-runtime-resume-v1\install-inspection-v2" --scope "%B%\deployable-runtime-resume-v1\HOST_SCOPE_V25.json" --output "%B%\deployable-runtime-resume-v1\install-inspection-v3"
```
Preserve closed outputs and failed source1. Future current-state evidence needs a fresh scope and destination. No app/firmware action or new resource allowance follows automatically from this read-only result.

