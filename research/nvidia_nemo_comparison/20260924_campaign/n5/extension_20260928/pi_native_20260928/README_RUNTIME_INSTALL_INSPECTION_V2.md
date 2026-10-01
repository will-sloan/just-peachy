# Runtime installation inspection V2

Purpose, inputs/outputs, resource bounds and strict SSH are as documented in README_RUNTIME_INSTALL_INSPECTION_V1.md. V1's actual read-only attempt found a new boot and rejected an old completed owner carrying historical admission/role fields. No app/config/data mutation occurred. V1 raw failure and early native identity remain immutable.

V2 requires exact equality to the full historical owner value for that exact path from the pinned prior closure before extracting its three identity fields. Unknown paths, fields or changed values still reject. No generic extra-field exception is allowed. The prior failed inspector's actual saved identity is checked too. A bounded independent PID-absence check is now retained even when the inspection itself fails, whenever early identity was received. This does not erase earlier missing-identity gaps.

Back up and independently restore V2 plus this README before use. The same compact full host precheck runs again because this is a new native dispatch. No healthy model/component test is repeated.

PowerShell:
```powershell
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$l='G:\Just_Peachy_N1\20260924_campaign\local'
$b="$l\n5\research-extension-20260928\pi-native-20260928"
& $py -B .\inspect_runtime_install_v2.py --private $b --local $l --prior-closure "$b\NATIVE_CLOSURE_V315.json" --previous-inspection "$b\deployable-runtime-resume-v1\install-inspection-v1" --scope "$b\deployable-runtime-resume-v1\HOST_SCOPE_V24.json" --output "$b\deployable-runtime-resume-v1\install-inspection-v2"
```
CMD or Anaconda Prompt:
```bat
set "L=G:\Just_Peachy_N1\20260924_campaign\local"
set "B=%L%\n5\research-extension-20260928\pi-native-20260928"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B inspect_runtime_install_v2.py --private "%B%" --local "%L%" --prior-closure "%B%\NATIVE_CLOSURE_V315.json" --previous-inspection "%B%\deployable-runtime-resume-v1\install-inspection-v1" --scope "%B%\deployable-runtime-resume-v1\HOST_SCOPE_V24.json" --output "%B%\deployable-runtime-resume-v1\install-inspection-v2"
```
Scope/output are finite and single-use. Private startup/config bytes must never enter Git. This inspection establishes current facts only; it is not activation, physical coldboot, offline or recording acceptance.

