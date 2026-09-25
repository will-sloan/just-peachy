# A1 shared Controller and private GUI validation

The unlaunched v1 preparation is preserved. V2 adds the NeMo license and
attribution notice to the exact frozen source inventory before testing; it
changes no model math or GUI assertions.

`prepare_a1_controller_v2.py` freezes the reviewed A1 application derivative and
creates a two-job plan: the full prototype source suite, then three actual
source-paced A1 GUI cells (boundary interruption, short turn, returning speaker).
Inputs are the existing GUI plan, successful service-parity plan, nominal A1
plan with a passing two-cell application-runtime smoke, and fresh version.
Outputs are a private immutable source release, runtime catalog, plan and worker
specification. It launches no inference. Original releases and failed evidence
are preserved. Preparation is not Controller or stage acceptance.

The freeze permits only the reviewed n3_models/catalog/test/README edits plus
seven explicit new package/test/license files. It verifies every previous source file,
common UI/layout and auxiliary file, and refuses unexpected worktree changes.
Model and P0 inputs stay in their existing private locations. The A1 component
is independently hash-bound to its qualified service export and inference-only
frontend; no previous dither-enabled predictions are reused.

`gui_a1.py` derives from the native GUI audit using the same common Controller,
480x800 Tk interface, captured-widget evidence, final-state observation, source
clock and archive-integrity checks. The only selected backend is compact A1
with D0/E0 and P0. D0 activity and E0 identity run on actual query audio against
the admitted research-only gallery. Closed labels remain assumptions; the
uncalibrated open mode must remain Unknown. The main application performs the
inference. No prerecorded text or evaluator truth enters it.

PowerShell:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B -m unittest prototype.tests.test_n3_a1 prototype.tests.test_backend_catalog
& $py -B research/nvidia_nemo_comparison/20260924_campaign/n3/prepare_a1_controller_v2.py --gui-plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-guifinalv1.json --service-plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-a1servicev2.json --nominal-plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-a1nominalv1.json --version a1controllerv2
& $py -B research/nvidia_nemo_comparison/20260924_campaign/n3/supervise_n3.py check --plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-a1controllerv2.json
```

CMD or Anaconda Prompt (no activation required):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -m unittest prototype.tests.test_n3_a1 prototype.tests.test_backend_catalog
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n3/prepare_a1_controller_v2.py --gui-plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-guifinalv1.json --service-plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-a1servicev2.json --nominal-plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-a1nominalv1.json --version a1controllerv2
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n3/supervise_n3.py check --plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-a1controllerv2.json
```

Use README_QUEUE.md's single hidden wait launch after inspecting fresh owner
PID/creation identities and excluding any other waiter. Never edit bound source
or race another pending queue. Tests start only after the existing numerical
owner releases its lock. All process windows remain hidden; Tk tests run on a
separate private desktop without switching to it or injecting input. No new
capture, microphone enumeration, playback, personal-gallery import or Pi access.
CPU, disk reserves and the unchanged campaign deadline still apply.

Outputs are source-suite RESULT.json and private GUI_PANEL_REPORT.json, with
per-cell hashes, actual widget captures, exact input samples, raw/final caption
evidence, process samples and joined archive receipts. Review every requested
cell and failure. A queue reaching READY_FOR_REVIEW never certifies acceptance.
N4 must still use the accepted source, frozen nominal configuration and required
full-bank/resource evidence; it cannot treat this three-cell test as completion.
