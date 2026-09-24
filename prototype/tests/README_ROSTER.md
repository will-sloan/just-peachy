# Roster, closed-group and score tests

`test_roster_policy.py` uses temporary synthetic UUID references and deterministic
vectors/events to prove real matrix filtering, open rejection versus explicit
closed forcing, fresh-clean-voice gates, no personal-reference mutation,
separate always-selected display under missing/overlap evidence, causal fallback
and current-voice replacement without fake raw identity or scores,
duplicate names/rename/delete/route compatibility, safe parameter epochs, exact
spatial parent reuse and parameter validation/reset. `test_roster_ui.py` uses
real Tk controls with a stub controller to check roster cancel/empty/compatibility,
Advanced placement, constant Unknown, raw score labels and inactive controls.
Existing UI regression expectations follow the renamed modes and separate
full-view recovery. These are not model/hardware recognition accuracy claims.

Inputs: deterministic temporary arrays, profile metadata, clocks and Tk actions.
Outputs: unittest pass/fail; no production data, microphone or playback.

PowerShell from `prototype`:

```powershell
& '..\.edge-speech-env\python.exe' -B -m unittest discover -s tests -p 'test_roster*.py' -v
```

CMD / Anaconda Prompt:

```bat
"..\.edge-speech-env\python.exe" -B -m unittest discover -s tests -p "test_roster*.py" -v
```

The full suite discovers these tests automatically. See
`../tools/README_ROSTER.md` for the bounded native enrolled/other-person proof.
