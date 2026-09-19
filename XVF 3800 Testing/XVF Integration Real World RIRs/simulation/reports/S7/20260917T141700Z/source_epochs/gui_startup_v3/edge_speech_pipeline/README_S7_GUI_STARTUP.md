# GUI controls before session startup

The original real window builds widgets before PipelineEngine._begin_session sets _s7_presentation_options. The window's construction-time predicates therefore omit selection/view controls and speaker-column widgets. Scripted controller actions and isolated widget fixtures do not test this constructor path.

Build_v2.py copies the52 declared execution files to a fresh source_epochs/gui_startup_v3. It changes only GUI construction: a small helper uses explicit S7 configuration while runtime presentation options are not yet available, then returns actual session options once present. It creates no session, source clock, identity evidence or model. All51 non-GUI files remain byte-identical; running source is untouched.

Inputs: exact mode_panel_v1 predecessor manifest/files and this README. Outputs: isolated source epoch and immutable BUILD.json with source/method compatibility evidence. Checks.py constructs real PipelineEngine and real withdrawn Tk windows before source startup, with model-start guards and device enumeration suppressed. It compares original/repaired widgets and writes CHECKS.json. It starts no source, model, audio or hardware.

## PowerShell

```powershell
$R7 = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S7\20260917T141700Z'
$Task = "$R7\application\gui_startup_controls_v1"
$Python = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $Python -B "$Task\Build_v2.py"
& $Python -B "$Task\Checks.py"
```

## Anaconda Prompt / CMD

```bat
set "R7=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S7\20260917T141700Z"
set "TASK=%R7%\application\gui_startup_controls_v1"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%TASK%\Build_v2.py"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%TASK%\Checks.py"
```

Use the existing environment directly; no installation. Outputs must be fresh and failures preserved. These commands are run once by the task. Do not rebuild into the existing epoch or overwrite receipts; a further change needs a new version.

The required GUI cohort must use the repaired epoch and verify actual controls/columns, including actual M5 widget text. Prior11 compatible no-action GUI controls remain valid historical evidence but are not exact repaired-GUI reuse. Plan119 repaired GUI jobs (four pilots then115), about11extra short runs relative to the earlier108new plan. No core model results are silently relabelled. Final headless core/scoring still closes its unchanged epoch; new GUI outcome/timing claims belong to this repaired GUI cohort.

Ordinary desktop launch preparation should use the repaired epoch. Actual native pilot, mode/outcome analysis, ordinary launch smoke and downstream requirements are still mandatory. Do not claim product or physical touchscreen/scanout qualification from constructor checks.


Failed first builder: Build.py and build_01.stderr.log are preserved. Its global predicate-count assertion incorrectly assumed all seven predicates were construction-time; three are construction-time and four runtime. The untouched partial copied source_epochs/gui_startup_v2 is never admitted. Build_v2.py confines changes to the three construction predicates in a fresh v3 epoch.
