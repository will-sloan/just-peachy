# Reconstruct actual ASR and D0 lane commands from sealed components

`component_commands.py` recovers the exact prediction pushes and source-progress
watermark calls from complete ASR component events. Purpose: prepare joint cache
replay without replacing source watermarks with availability times. This matters
because the shared scheduler releases only events strictly below both lane
watermarks; sorting words alone does not reproduce that behavior.

Inputs to `asr_commands(rows, variant=..., duration=...)`: the full verified raw
event list from one A0/A1/A2/A3 cell and its actual source duration. Call the
component reviewer first; this helper is not a substitute for source, model,
waveform, gzip/CRC or cache-key verification. Final-only formatting events are
recognized as a separate phase and do not enter the ASR predictor queue.

Outputs: ordered `push`/`advance` command dictionaries with an explicit modeled
availability, original raw observation, or source lower bound. Closure uses
`closed=True, lower_bound_sec=None` rather than a nonfinite JSON number. A0
advances after every full block and its endpoint reset; a partial tail advances
only at close. A1/A2/A3 advance after every feed/publish call, including the exact
tail, then close after native drain. This is the unchanged application's actual
protocol. No observations or source times are invented or clamped.

`d0_commands(rows, duration=...)` recovers exact D0 fixed-cadence pushes and
250-ms source watermarks from the full segmentation/admission/vector log.
Rejected admissions are required: they retain the modeled lane-ready time even
when no vector is produced. Both short/mature admission roles must be present.
The partial tail produces no invented model call. D0's closing lane-ready value
can precede the end of that unanalyzed tail; it remains unchanged. A future merge
must separately ensure all actual input has been delivered before closing the
lane, rather than relabeling this value as an observed finish time.

This helper does not supply D1 commands, merge the two lanes, execute policy,
observe a Controller/widget, or qualify modeled times as live measurements.
Missing dispatch/drain evidence, source discontinuity, future observations and
wrong raw-event sequence are rejected. Actual formatting results stay separate.

`test_component_commands.py` instruments the actual frozen application ASR
loops with stub models. It compares the complete real push/watermark call sequence
with reconstruction from those loops' emitted logs, including endpoint resets,
multiple native finals and partial tails. It also checks damaged evidence.
The D0 tests compare reconstructed commands against the actual unchanged speaker
loop with stub models, including silence, rejected windows and a 200-ms tail.
No neural models, saved recordings, desktop windows or hardware are used.
Test output goes to the console. The source default is the verified campaign
`n4-catalog-v3` derivative; `JP_N4_SOURCE` can select only a verified equivalent.

PowerShell:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
& $jpPython -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_component_commands.py','-v']; runpy.run_module('unittest',run_name='__main__')" $jpCode
```

Command Prompt / Anaconda Prompt:

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
"%JP_PY%" -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_component_commands.py','-v']; runpy.run_module('unittest',run_name='__main__')" "%JP_CODE%"
```

A real-evidence probe also reconstructed commands from all eight reviewed ASR
smoke cells and the first four reviewed D0 bank cells (E0/E1, O0/O1). All 12
sealed logs parsed successfully without loading models. The private receipt is
`local/n4/component-command-probe-v1/RESULT.json`, bound by
COMPONENT_COMMANDS_CHECK_V1.json. This is a reconstruction check, not observed
Controller/policy parity or 12 integrated results.
