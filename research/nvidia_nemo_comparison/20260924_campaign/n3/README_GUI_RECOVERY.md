# A2/A3 GUI label assertion recovery

Latest result: guifinalv1 is terminal. A2 passed all three cells. A3 failed its
first boundary cell because the ASR lane did not finish within the existing
60-second finalization join, and its archive did not close successfully. Earlier
A3 guilabelsv1 cells all passed; both outcomes remain separate evidence. The
final-state observer repair is not a fix for CPU drain capacity. Preserve the
failure and inspect actual backlog/CPU before admitting another runtime or
claiming real-time operation. No current native GUI worker remains active.
PORTABLE_RECOVERY_REVIEW_20260925.json binds the receipts. The commands below
are reproducibility examples for already preserved attempts, not relaunches.

The guilabelsv1 retest completed five of six cells. A2 returning failed because
the audit hook watched `_record_presentations`, which the unchanged common UI
skips when final text/labels need no rewrite. Seventeen already displayed spans
lacked a final-state observation; first displays and archive integrity were
present. A3 passed all three cells. Original failed and passing evidence remains.

The later `gui_finalaudit.py` derivative wraps actual `_render_rows` completion
and calls `final_state_audit.observe_final_rows`. For final rows it checks the
already recorded first display, current row cache and actual Tk mark text before
recording a separate final-state observation. It never fabricates a first
display, forces a redraw, changes presentation receipts or alters the app.
This observation is not physical scanout or evidence of a visible text change.
All six cells rerun because the measurement observer changed.

`test_final_state_audit.py` has three no-GUI fixtures: unchanged text receives
one final observation, mismatching widget text is refused, and a missing first
display cannot be invented. `prepare_gui_finalaudit.py` takes the terminal
guilabelsv1 parent plan and a fresh version, validates the actual failed cell,
then emits a bound two-job plan/worker specification and fresh output paths.
Use these current PowerShell commands after the model-free tests:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n3/test_final_state_audit.py
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n3/prepare_gui_finalaudit.py --parent-plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-guilabelsv1.json --version guifinalv1
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n3/supervise_n3.py check --plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-guifinalv1.json
```

CMD/Anaconda Prompt, from the worktree:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n3/test_final_state_audit.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n3/prepare_gui_finalaudit.py --parent-plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-guilabelsv1.json --version guifinalv1
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n3/supervise_n3.py check --plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-guifinalv1.json
```

The historical label-fix commands below describe guilabelsv1; do not relaunch
over its immutable outputs. Use the hidden wait procedure once for the fresh
plan, after checking current ownership. Its input and focus constraints remain.

The v4 actual private GUI panels both failed on their first boundary cell at
the expected assumed-label assertion. The test expected an extra U+00C2 before
the U+00B7 middle dot. Actual Tk receipts contained the correct suffix: 89 A2
and 106 A3 assumed-label receipts, all ending in ` Â· assumed`. Both cells closed
the Controller and passed archive integrity. This is a test encoding defect;
the failed attempts remain preserved and receive no successful GUI credit.

`gui_labels.py` is an exact derivative of the admitted `gui.py`, changing only
the two expected suffix literals to an ASCII `\u00b7` escape and its private
unittest module identifier. The application, common UI, inference, gallery,
timing, sources, modes and validation thresholds are unchanged. This includes
the same exact frozen n3-common-v4 prototype. All six planned GUI cells rerun.
The general runner inputs/outputs and private-desktop procedure are documented
in README_GUI.md. It never opens a visible window or takes desktop focus/input.

`prepare_gui_recovery.py` requires the matching terminal parent plan, absent
parent coordinator, unchanged admitted runner, exact original failure receipts,
successful teardown and actual expected label suffixes. Inputs: `--parent-plan`
and a fresh alphanumeric `--version`. Outputs: a private two-job plan and worker
specification, exact diagnosis/evidence bindings, and fresh GUI output paths.
It does not load a model or launch a process. The existing supervisor admits
one CPU-only private candidate at a time after ownership is released.

`test_gui_label_recovery.py` performs two model-free checks: the complete file
diff is limited to the three declared substitutions, and both parsed assertion
values use the actual Unicode suffix. It opens no GUI. Run from the worktree.

PowerShell:

```powershell
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& $py -B research/nvidia_nemo_comparison/20260924_campaign/n3/test_gui_label_recovery.py
& $py -B research/nvidia_nemo_comparison/20260924_campaign/n3/prepare_gui_recovery.py --parent-plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-v4.json --version guilabelsv1
& $py -B research/nvidia_nemo_comparison/20260924_campaign/n3/supervise_n3.py check --plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-guilabelsv1.json
```

CMD/Anaconda Prompt (explicit interpreter, no activation):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n3/test_gui_label_recovery.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n3/prepare_gui_recovery.py --parent-plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-v4.json --version guilabelsv1
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n3/supervise_n3.py check --plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-guilabelsv1.json
```

Use README_QUEUE.md's hidden `wait --plan` procedure once, after checking current
queue PID/creation identities. Do not launch a second copy or run a candidate
during another resource test. Failed originals, screenshots, source hashes and
all old plans remain immutable. A passing retest still needs visual/metric
review and is not N3 acceptance by itself. No Pi or microphone access occurs.
