# Modeled component input to the actual caption state

`component_presentation.py` connects separately verified raw ASR, caption-policy
and formatting records to the frozen application's actual S7 presentation and
N1 timestamped-span implementation. Purpose: develop the joint replay interface
without replacing the app's word ownership rules. It is not a model runner,
causal merge, complete Controller or integrated N4 result.

Inputs: an actual `build_presentation_state` instance with `max_display_rows=512`
and `ownership_mode='timestamped_spans_v3'`; sequential raw ASR observations;
actual caption-policy records; and formatting bound to the exact raw final ID
and text. Callers must supply records in causal modeled availability order and
must run the genuine policy separately. No reference text, true speaker name,
new acoustic alignment, model or hardware access occurs here.

Outputs: full actual presentation rows and event history, raw-word/fragment
reconstruction checks, rejected stale identities, formatting counts and an
explicit `MODELED_COMPONENT_REPLAY_NOT_OBSERVED_CONTROLLER_OR_WIDGET` scope.
The actual state implementation retains field names such as `*monotonic*`; in
this diagnostic their values are modeled. They must never be aggregated as
observed first-visible/GUI latency. No observed clock is inserted or synthesized;
observed-clock inputs are rejected. Physical widget observation, Controller
parity and integrated-cell credit remain false/zero. Raw ASR words survive
punctuation and speaker-label changes; zero-duration revision spans remain
coarse uncertainty, never phonetic timestamps.

API use inside an independently admitted future replay:

```python
from edge_speech_pipeline.research_s6d import S6DSettings, build_presentation_state
from component_presentation import ComponentPresentation
state = build_presentation_state(S6DSettings(max_display_rows=512), s7={
    'mode': 'M1', 'session_id': job_id, 'ownership_mode': 'timestamped_spans_v3'})
capture = ComponentPresentation(state)
capture.text(actual_raw_observation)
# After actual policy execution / verified final-only formatting:
# capture.policy(actual_policy_record)
# capture.formatting(actual_component_formatting)
snapshot = capture.snapshot()
```

`test_component_presentation.py` uses synthetic protocol text and the actual
frozen application state, without models or saved recordings. It tests full
word preservation after rewrites, exact-final formatting, multiple native EOU
finals at one source boundary, stale/current identity targets and rejection of
observed clocks/noncausal inputs. No app window is launched. Test results go to
the console. The default source is `local/releases/n4-catalog-v3/prototype`;
`JP_N4_SOURCE` may name only a separately verified equivalent source.

PowerShell:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
& $jpPython -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_component_presentation.py','-v']; runpy.run_module('unittest',run_name='__main__')" $jpCode
```

Command Prompt / Anaconda Prompt:

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
"%JP_PY%" -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_component_presentation.py','-v']; runpy.run_module('unittest',run_name='__main__')" "%JP_CODE%"
```
