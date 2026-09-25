# One bounded A3 CPU-budget contrast

The latest A3/D1/E0 full-GUI boundary attempt kept advancing but could not drain
its ASR backlog within the existing 60-second join. The earlier passing attempt
also finished well after source delivery. GUI_DRAIN_REVIEW_20260925.json binds
the diagnosis; neither result establishes real-time performance. The existing
campaign policy permits two CPU cores, while those GUI attempts used only CPU4.

This is one separately labelled host resource contrast: rerun the same A3
boundary, short-turn and returning-speaker files on affinity `[4,14]`, with one
thread per model, one candidate, CPU-only inference and the same GUI/identity
stack. Keep the original one-core failure and all timings. A completed drain
will qualify only functionality at the new allocation; it cannot turn the
one-core result into a pass or establish CM5 throughput. Do not repeat resource
rescues indefinitely. Later N4 paired resource comparisons need equal budgets.

`gui_twocore.py` is an exact derivative of `gui_finalaudit.py`, changing only its
module name, explicit affinity admission/check, worker affinity and legacy
`--cpu 4` selector. The complete actual affinity is recorded as `[4,14]`.
All model threads, source-speed delivery, audio, epochs, gallery modes, GUI
assertions, final-state observation, archives and join limits remain identical.
`supervise_n3_twocore.py` changes the execution-description string to identify
two cores and defers the waiter's initial full binding verification until the
existing numerical owner has released its slot. Full verification still runs
inside the free-owner lock immediately before dispatch and again in the child.
This prevents multi-gigabyte model hashing from competing with another paced
candidate. Ownership, N2 prerequisite, cutoff and single-child checks remain.

`prepare_gui_twocore.py` takes the exact terminal failed GUI plan, actual drain
diagnosis and a fresh alphanumeric version. It verifies both derivatives are
limited to the declared substitutions, that the old failure/plan still bind,
that the old owner is gone, and that the current policy permits two cores.
Outputs are a new private plan and worker specification with all inherited
application/model bindings, the three original cells and resource metadata.
Preparation starts no model or GUI. No current source is edited. Only this
already-diagnosed A3 panel is admitted; A2 and different cells are rejected.

From PowerShell in the campaign worktree:

```powershell
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
& $py -B research/nvidia_nemo_comparison/20260924_campaign/n3/test_gui_twocore.py
& $py -B research/nvidia_nemo_comparison/20260924_campaign/n3/prepare_gui_twocore.py --parent-plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-guifinalv1.json --diagnosis research/nvidia_nemo_comparison/20260924_campaign/n3/GUI_DRAIN_REVIEW_20260925.json --version gui2corev1
& $py -B research/nvidia_nemo_comparison/20260924_campaign/n3/supervise_n3_twocore.py check --plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-gui2corev1.json
```

CMD/Anaconda Prompt (explicit interpreter; no activation needed):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n3/test_gui_twocore.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n3/prepare_gui_twocore.py --parent-plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-guifinalv1.json --diagnosis research/nvidia_nemo_comparison/20260924_campaign/n3/GUI_DRAIN_REVIEW_20260925.json --version gui2corev1
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n3/supervise_n3_twocore.py check --plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-gui2corev1.json
```

`test_gui_twocore.py` runs six model-free checks: exact derivative equality,
changed/duplicate-anchor refusal, and preservation of all nonresource job flags,
three cells and timeouts; the actual cleanup-error/diagnosis binding; plus mocked
queue checks proving that an occupied slot
causes no binding hashes/launch and that a free slot is reverified before start.
It launches no GUI/model. After preparation, keep these
bound sources immutable. Never recreate an existing plan/output directory.

Use README_QUEUE.md's hidden `wait --plan` launch with
`supervise_n3_twocore.py`, only after the existing A1 Controller waiter dispatches
and no competing waiter remains. Register one waiter, then allow the active
owner to finish. This waiter performs only small status reads while waiting.
Do not run the entry point directly, hash large model bindings
during paced/resource measurements, or create a second numerical owner.
The actual test uses a private desktop without switching or injecting input.
Outputs are numerical-gui2corev1/RESULT.json, gui-A3/GUI_PANEL_REPORT.json,
per-cell measured timings/resources/affinity, private widget captures and
lossless archive checks. All private captions/audio/profiles stay outside Git.

Preserve C:50 GiB/G:75 GiB and the existing payload allowance. Packaging cutoff
and campaign deadline are unchanged. The Pi remains off. No device enumeration,
capture, playback, training, enrollment or visible desktop launch is involved.
