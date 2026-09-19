# S6D capture owner V4: explicit shared stop event

`s6d_capture_owner_v4.py` is an additive copy of reviewed V3
`s6d_capture_owner.py`. V3 remains unchanged and historical. V4 adds only an
optional `external_stop_event` argument to `execute` and `capture_to_disk`,
checks before ownership/recipe/audio, and checks in the callback and existing
50 ms capture watchdog. No runtime monkeypatch is used. The supervisor bridge
passes its own threading.Event directly. A stop-file write failure cannot prevent
that same-process event from reaching the capture callback.

Inputs, six decoded profiles, exact accepted DSP recipe, source/guard clocks,
global480-attempt/21600-second ledger, C50/G75/40 GiB storage limits, raw-unity
and per-stream LIMITED policy, native telemetry and fail-closed restoration
remain those documented in `README_S6D_CAPTURE.md`. V4 additionally requires
this README in the root's exact source authorization graph. The V3 README and
all original source dependencies remain bound. A shared stop is cooperative;
it does not terminate a hardware process or claim restoration from PID exit.

The new bridge uses bounded atomic metadata publication (six PermissionError
attempts, delays20/40/80/160/250 ms, unique temporary names), records stop-event
delivery separately from file relay, checks STOP through finalization and again
immediately before completion publication, and checks stop/closed between
progress scan entries. Persistent I/O failure remains a failure. RESTORED is
published only from actual closed, hash-bound owner/ledger receipts, separately
from COMPLETE. No COMPLETE is published for an observed matching or malformed
final STOP. STOP arriving after completion's final admission check is a later
request against an already-restored owner; no additional attempt is launched.

`s6d_capture_checks_v4.py` is the original model-free capture fixture suite
retargeted to V4, with small event checks. `s6d_physical_prepare_checks_v1.py`
adds synthetic bridge I/O, late-stop, scan cancellation and actual input checks.
All fixtures use arrays, temporary files and fake sounddevice objects. They do
not initialize vendor DLLs, enumerate a device, issue setters, open a real audio
stream, or use a neural model.

PowerShell, model-free (use fresh output filenames):

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$r = "$sim\reports\S6D\20260913T195357Z"
$py = 'C:\Users\amiri\anaconda3\python.exe'
& $py -B "$sim\scripts\s6d_capture_checks_v4.py" --output "$r\capture_owner_v4_checks_v1.json"
& $py -B "$sim\scripts\s6d_physical_prepare_checks_v1.py" --prepared-result "$r\physical_preparation_v2\PREPARATION_RESULT.json" --output "$r\physical_preparation_checks_v5.json"
```

Anaconda Prompt/CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "R=%SIM%\reports\S6D\20260913T195357Z"
set "PY=C:\Users\amiri\anaconda3\python.exe"
"%PY%" -B "%SIM%\scripts\s6d_capture_checks_v4.py" --output "%R%\capture_owner_v4_checks_v1.json"
"%PY%" -B "%SIM%\scripts\s6d_physical_prepare_checks_v1.py" --prepared-result "%R%\physical_preparation_v2\PREPARATION_RESULT.json" --output "%R%\physical_preparation_checks_v5.json"
```

Future execution uses the reviewed supervisor bridge command shape in
`README_S6D_PHYSICAL_PREPARATION.md`, with `--owner` pointing to V4 and its
new reviewed SHA256. Root must review V4 and the latest supervisor source epoch,
create the actual safety/plan/source authorization and literal queue, and restore
physical disk headroom before launch. No authorization is supplied here. The
native C#/transport sources and all prepared WAVs remain unchanged.
