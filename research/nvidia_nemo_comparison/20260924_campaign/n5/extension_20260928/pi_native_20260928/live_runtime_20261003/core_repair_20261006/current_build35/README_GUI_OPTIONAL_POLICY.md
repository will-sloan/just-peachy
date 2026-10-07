# Exact reviewed optional policy in the GUI

This is a GUI-only derivative of admitted14. It replaces launcher.py and adds
this README; it does not change frozen14 or admit a new model/policy. The only
new functions are gui_session_policy and gui_policy_summary. The only changed
preexisting function is show. Manager, headless commands, all worker/source/model
paths and the normal admission/asset checks remain unchanged.

The original GUI always supplied ordinary SessionPolicy defaults, including
120-second drain and backlog, even when the optional proof required60/30. It
also disabled the revision-window entry before the optional checkbox could be
enabled, preventing selection of an exact window60 proof from the default30.

The new GUI enables revision-window editing for experimental Pyannote before
checking optional refinement. Set the exact reviewed window and complete
selection. Eligibility resolves exactly one accepted optional reference for
all selection fields, constructs its complete policy, rejects developer/over300
policies, and calls the unchanged reviewed_options proof/asset validator.
Missing, ambiguous, malformed or changed references remain unavailable. The
Advanced status and Launch summary explicitly show source, load, drain, backlog
and cleanup. Start resolves/validates that policy again; Manager and worker
retain their independent checks. Unchecked ordinary sessions still use the
unchanged300/load120/drain120/backlog120/cleanup60 defaults.

The source file alone cannot enable the optional checkbox. A separately reviewed
exact-content/UI-derivative evidence certificate and actual production authority
are required. Prior measurements keep their original executed14 identities.
This GUI fix neither repeats nor claims new native compute, speaker quality,
physical touch or sustained operation.

## Inputs and outputs

Runtime input is the existing binding, exact production optional-reference list
and validated GUI selection. Output is one displayed, exact SessionPolicy passed
to the existing Manager. No source/model field or receipt is rewritten.

test_gui_optional_policy.py requires the exact actual admitted14 package as
--base-package and an existing private --output-root. It pins CPU14 and records
actual Windows FILETIME before project access. It verifies source AST limits,
ordinary/optional policy behavior and refusal cases, then exercises real hidden
host Tk controls with a fake Manager. Simulated Start records only arguments;
there is no subprocess, Pi access, model or capture. The output is a fresh owner
directory and RESULT.json. Synthetic reference fixtures do not create authority.
Use --test test_actual_withdrawn_tk_controls_and_start_policy to rerun only that
changed host fixture; omit --test for the six focused contracts. The original
fixture's redundant cleanup after normal Exit raised TclError; its failed
receipt is preserved. The correction only tolerates an already-destroyed test
window and changes no runtime source.

## PowerShell

```powershell
$PY='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
$D='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/gui_optional_policy_derivative_20261004'
$Q='G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003'
& $PY -B "$D/test_gui_optional_policy.py" --base-package "$Q/audit-preparation/package-preparation-44b6fb3f972446219644fd4f53e008b6/package" --output-root "$Q/audit-preparation"
```

## Command Prompt and Anaconda Prompt

Use the existing qualified interpreter directly; no environment installation.

```bat
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "D=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\gui_optional_policy_derivative_20261004"
set "Q=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003"
"%PY%" -B "%D%\test_gui_optional_policy.py" --base-package "%Q%\audit-preparation\package-preparation-44b6fb3f972446219644fd4f53e008b6\package" --output-root "%Q%\audit-preparation"
```

This check does not install the derivative. After a reviewed fresh package and
production proof are available, the separately owned native idle/Exit check
must inspect experimental Pyannote/TitaNet/live/window60, the enabled optional
checkbox and exact300/60/30 summary without pressing Start, then exit normally.
