# Opt-in S7 candidate clocks and runtime

Purpose: evaluate source pacing, independent caption delivery and optional desktop modes in an isolated candidate. The original application and S6D source epoch remain unchanged. Inputs are the admitted mono 16 kHz paired WAVs at unity, exact C065/C088-A15/C105 profiles, unchanged model assets and explicit S7Settings. Outputs are original scientific journals plus s7_clocks.jsonl with block deadlines/read/append/commit, model and event boundaries.

The source epoch is currently under implementation; it is not yet qualified. Native execution must use a frozen manifest and the admitted runner command in the S7 run's application README. Do not launch this directory with inferred model paths or use an old S6D completed output directory.

Initial executable, model-free producer verification (after fixtures are provided):

PowerShell:

    & 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S7\20260917T141700Z\application\pacing_v1\Fixtures.py'

Anaconda Prompt or CMD:

    "C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S7\20260917T141700Z\application\pacing_v1\Fixtures.py"

Absolute pacing uses one monotonic origin after model startup, reads at most one block ahead, waits until the block-end deadline, then atomically publishes a common paired frame cursor after both journals are written. It never releases future samples to improve latency. Relative mode retains the old read/append/full-duration wait ordering as an instrumented control. Pauses preserve the origin and are explicitly logged; paused/catch-up execution is not source-speed qualification. All overruns remain in the trace and sample counts must match.

Trace submission is bounded and asynchronous; no vector or full transcript serialization occurs on that lane. Overflow is explicit run failure. Native time, source sample time, modeled availability and actual widget acknowledgments remain distinct. The timing trace must be drained and validated after native worker/consumer closure.

Historical defaults are untouched when S7 settings are absent. M0 bypasses actual optional speaker work where supported; other mode eligibility requires measured native and GUI results. No hardware input/output is used by these file tests.
