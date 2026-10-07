# Portrait startup and operator Mode presentation

Purpose: wire the small backend chooser into the original portrait application,
make chooser → controller → visible window startup observable, preserve its
original Modes/People/Settings/History/enrollment interfaces, and remove only
the standalone Anonymous conversation menu choice. No source, model,
threshold, gallery, recording-count or manual Stop policy changes occur here.

These are new `classic_frontend.py` and `mature_frontend.py` derivatives for a
new versioned package. Build21 remains unchanged and recoverable. The compact
chooser is described in [README_OPERATOR_PROFILES.md](README_OPERATOR_PROFILES.md).

## Actual failure and responsibilities

The root's current native read-only diagnostic retained
`ValueError: Unsupported portrait setting: direction`. That is the observed
constructor failure; merely exiting the chooser was never application success.
The separate `application_controller` settings adapter must validate and preserve
the real persisted `direction` setting. This frontend does not delete personal
settings or infer accepted values to bypass that validation.

Inputs: the existing owned `launcher.Manager`, exact installed original UI
manifest/source, current application settings, and a validated named backend
selection. Outputs: the same portrait GUI, a complete `RuntimeSelection` from
the chooser, and bounded private startup diagnostics. No model is created by
the chooser; the original manual Start delegates to the existing worker.

`classic_frontend.choose(root, manager, config)` delegates to
`operator_profiles.choose` and returns a selection or None. `show(manager)`
preserves the original portrait class/controller construction and actual Tk
mainloop. A selected choice must produce a viewable portrait window; a
ten-second initial visibility guard detects a missing window. A first Map
observation records actual geometry and viewability, not a stable fullscreen or
physical-touch qualification. The parent smoke test still checks the real
portrait remains visible and idle, Start/Stop, and actual source/model closure.

Unhandled Tk callbacks no longer disappear into stderr while startup silently
stalls. Their real exception/traceback causes abnormal exit, owned Stop/poll and
a critical error notice. The original exception is re-raised, including separate
notes if cleanup, diagnostic publication or error presentation also fails.
Ordinary experimental selections have no acknowledgement popup; critical real
startup failures remain visible. Abnormal cleanup uses existing manager and
gallery Stop/poll APIs with finite configured load/drain/cleanup time. It never
asserts physical process death; the independent native finalizer must verify it.

## Diagnostic allocation

One unique context is created under the existing manager's `launches` control
directory: `gui-<UUID>`. `OWNER.json` records the actual same GUI owner. It is not
a new speech process, and no exit-intent receipt proves that owner dead.

Each context permits at most four immutable phase files plus OWNER:

- `CREATED.json`: control context prepared.
- `SELECTED.json`: explicit profile/source chosen.
- `VISIBLE.json`: actual Tk viewability and geometry observed.
- `EXIT.json`, or `FAILED.json`: normal closure or actual primary error.

Failure earlier in startup naturally produces fewer files. Receipt fields
include exact release content pin, complete selection, actual owner and clocks;
errors include bounded reasons/traceback, without copying settings, profiles,
audio or transcript content. A critical failure before context creation stays in
the owned service's original stderr; an unwritten receipt is never invented.

Maximum8KiB per receipt, at most64KiB metadata including transient pending
publication, plus one independent64KiB directory reserve. Before creating the
context, free storage must be at least5GiB+128KiB. Writes recheck the5GiB floor.
Pending bytes are preserved after failure. New contexts for explicit Return to
backend choices do not replace old failures. The parent packager/admission must
account for this independent128KiB control reserve; it does not remove any
existing allowance/floor or infer storage credit from tiny actual receipts.

## Original Mode behavior

`mature_frontend.operator_mode_menu(method)` reuses the original function's exact
code object and all existing globals, except for a copied `MODES` presentation
dictionary without `anonymous_conversation`. Both ordinary and Advanced Mode
menus use this projection. Original module globals and internal mode policy are
unchanged; Unknown tracks, continuity, Open with names and conflict handling
remain. A direct attempt to invoke the hidden menu choice receives a notice.
Existing persisted standalone anonymous intent should be migrated to a named
operator default by the controller; this module does not overwrite that intent.

The original page geometry, touch controls, rosters, seats, paragraph enrollment,
gallery domains, Save/Discard, rename and settings remain in the same portrait
application. History's displayed folder is corrected to the actual store path
`recordings/sessions/<UUID>`, rather than the nonexistent `recordings/<UUID>`.
No files are moved, removed or renamed by this display correction.

## Configuration/compile checks on Windows

Back up these new sources and independently restore/read back them before any
check or native use. No native/GUI/model action is part of the following compile
commands. Choose a fresh output path every time. Root source review must compare
the exact build21 baseline and run the separately documented operator selection
check; native smoke tests are independent evidence.

PowerShell, from this directory:

```powershell
$env:JP_STARTUP_CHECK_OUT='G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/startup-source-check-YOUR_UNIQUE_LABEL'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B -c "import psutil,os,json,pathlib; p=psutil.Process(); p.cpu_affinity([14]); out=pathlib.Path(os.environ['JP_STARTUP_CHECK_OUT']); out.mkdir(); (out/'REGISTERED_OWNER.json').write_text(json.dumps(dict(pid=p.pid,create_time=p.create_time(),affinity=p.cpu_affinity()))); import ast; files=['classic_frontend.py','mature_frontend.py','operator_profiles.py']; [compile(ast.parse(pathlib.Path(name).read_bytes()),name,'exec') for name in files]; print(json.dumps(dict(status='COMPILED_ONLY',files=files,native_execution=False,gui_execution=False)))" > "$env:JP_STARTUP_CHECK_OUT-stdout.json"
```

Command Prompt or Anaconda Prompt, from the same directory:

```bat
set JP_STARTUP_CHECK_OUT=G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/startup-source-check-YOUR_UNIQUE_LABEL
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B -c "import psutil,os,json,pathlib; p=psutil.Process(); p.cpu_affinity([14]); out=pathlib.Path(os.environ['JP_STARTUP_CHECK_OUT']); out.mkdir(); (out/'REGISTERED_OWNER.json').write_text(json.dumps(dict(pid=p.pid,create_time=p.create_time(),affinity=p.cpu_affinity()))); import ast; files=['classic_frontend.py','mature_frontend.py','operator_profiles.py']; [compile(ast.parse(pathlib.Path(name).read_bytes()),name,'exec') for name in files]; print(json.dumps(dict(status='COMPILED_ONLY',files=files,native_execution=False,gui_execution=False)))" > "%JP_STARTUP_CHECK_OUT%-stdout.json"
```

Native runtime entry is the existing reviewed owned `native_scope` →
`launcher` → `classic_frontend.show(manager)` path in the new immutable package.
Do not run this module bare, create an unowned manager, or launch from historical
consumed admissions. The root-owned deployment README supplies the final fresh
package/binding command before native use.
