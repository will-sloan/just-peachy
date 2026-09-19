# Independent native/Tk harness checks

Purpose: independently test the frozen harness's exact event-to-render receipt binding, verifiable widget content, setup failure cleanup, one native consumer with separate view inboxes, stable utterance revisions, old-session rejection, gallery failure observation, and committed-display overflow/closure. The probes import only standard-library helper logic, frozen pure presentation policy and event contracts. Two GUI methods and the harness's nested Window class are selected from their actual AST without changes and run against an in-memory widget double. The setup-failure probe runs actual `execute_gui` with a fake tkinter module whose window constructor fails. No actual Tk root, window, neural model, audio, or device is created/opened.

Inputs: frozen helper path, frozen `edge_speech_pipeline` directory, and a fresh G drive output directory. Outputs: exact-source `RECEIPT.json`, `TESTS.log`, `OBSERVATIONS.json`, and tiny synthetic per-view render logs under that directory. The initial v1 source is expected to reproduce three failing assertions belonging to two findings: missing triggering-event/widget evidence and setup cleanup. A repaired epoch must pass unchanged assertions; old artifacts remain immutable. Fixture teardown closes synthetic resources even when the reviewed helper fails to do so. These checks do not authorize a production launch or qualify real GUI timing/scanout.

PowerShell (use a fresh suffix if the output exists):

```powershell
$s6dSim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s6dReport = "$s6dSim\reports\S6D\20260913T195357Z"
$s6dPython = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $s6dPython -B "$s6dSim\scripts\s6d_native_tk_review_checks_v1.py" --helper "$s6dReport\application\native_tk_consumer_v1\helpers\s6d_application_tk_native_v1.py" --app-source "$s6dReport\source_epochs\application_direction_gui_v3\edge_speech_pipeline" --output 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\native_tk_v1_independent\adverse_v1'
```

Anaconda Prompt / CMD (existing environment, no package installation):

```bat
set "S6DSIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6DR=%S6DSIM%\reports\S6D\20260913T195357Z"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%S6DSIM%\scripts\s6d_native_tk_review_checks_v1.py" --helper "%S6DR%\application\native_tk_consumer_v1\helpers\s6d_application_tk_native_v1.py" --app-source "%S6DR%\source_epochs\application_direction_gui_v3\edge_speech_pipeline" --output "G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\native_tk_v1_independent\adverse_v1"
```
