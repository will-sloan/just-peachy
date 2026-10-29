# Whistle findings report

This code maintains one Word document dedicated to the local Whistle campaign.
It appends completed measurements, their interpretation, weighting/method
decisions, model provenance, microphone quality findings and analyst notes.
The existing `followup/campaign.py` and `followup/decide.py` already make the
bounded development decisions and advance to the next stage automatically.
Reporting does not control training, use the GPU, scan audio, rescore models,
change the frozen plan, or wait for another Codex turn.

## Inputs and outputs

The reader uses an allowlist of JSON files smaller than 2 MB: original config,
plan, completed model manifest and evaluation summary; follow-up audio-quality
summary, completed baseline/run scores, queue, dataset contributions, weighting
and method decisions, production recipe, final comparison and final summary.
Incomplete score files are ignored. Training/development manifests, prediction
JSONL, audio and model weights are never read. Evidence snapshots record the
source path and SHA256; no completed measurement is fabricated for pending work.

Output directory:

`C:\Users\amiri\Documents\GitHub\just-peachy\training\whistle_followups_v1\reporting`

- `Whistle_Fine_Tuning_Findings.docx` is the growing report.
- `report_status.json` records publication state and visual review status.
- `evidence/` retains the exact JSON behind each appended section.
- `analyst_notes.json` optionally stores durable explanatory notes.
- A `.pending.docx` is retained if Word locks the main document. Close the Word
  document to allow the next scheduled attempt to publish; training is unaffected.

Unique bookmarks inside the document prevent duplicate sections even if the
small status file is lost after a crash. Existing report text and human edits
are preserved when new sections are appended. Do not delete the hidden
bookmarks or move the report out of this directory. Corrections to source
results create a new recorded section rather than rewriting history.

## Run from Anaconda Prompt or Command Prompt

No Conda activation or package installation is needed. The launcher uses the
bundled Codex document Python with `python-docx`.

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Training Tool\whistle_lab\reporting"
powershell -NoProfile -ExecutionPolicy Bypass -File update_report.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File install_report_task.ps1
```

The first command updates once. The second installs the single Windows task
`JustPeachy Whistle Findings Report` at sign-in and every 15 minutes. It uses
the signed-in user, no saved password, hidden execution and no overlapping runs.
No-change checks leave the Word file untouched and consume no model tokens.

## Run from PowerShell

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Training Tool\whistle_lab\reporting'
.\update_report.ps1
.\install_report_task.ps1
Get-ScheduledTask -TaskName 'JustPeachy Whistle Findings Report'
Get-Content -LiteralPath 'C:\Users\amiri\Documents\GitHub\just-peachy\training\whistle_followups_v1\reporting\report_status.json'
```

Direct Python command, also usable from Anaconda Prompt/cmd:

```bat
"C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" report.py
"C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest test_report.py
```

The optional `--repo ABSOLUTE_REPOSITORY_PATH` and `--output ABSOLUTE_OUTPUT_PATH`
arguments support a relocated copy. On this computer the launcher intentionally
uses the runtime returned by Codex's workspace dependency loader. If that runtime
moves, resolve it through the loader and update the launcher path. The report
task is separate from the two training recovery tasks.

## Automatic interpretation and visual review

The 24 October amendment is collected from the immutable
`extension_snapshot.json` as a separate evidence event. Earlier findings stay
intact. The queue already supplies scores for the three longer pilots and any
conditional refit. `extension_decision.json` adds development comparisons and
actual exposure; `extension_production_decision.json` explains why the existing
model is retained or one additional fit is required. No report is labelled
campaign-complete until the amended supervisor publishes `summary.json` after
the selected final model and frozen comparisons. The same commands, inputs and
CPU-only task above apply; no extra reporting process or model call is needed.

The reporter computes descriptive WER changes and explains the saved promotion
decisions. It does not rerun statistical tests: the campaign already computes
the paired intervals and guards from complete development results. Negative
probes, test/development separation, repeated microphone views, unequal pilot
exposure and the absence of product hardware validation stay explicit.

The existing adaptive Codex heartbeat reads new completed findings, adds concise
interpretation when needed, and checks this report's status. Add an analyst note
by preserving the existing entries in `analyst_notes.json` and appending:

```json
{"id":"stable_unique_milestone_id","title":"Plain descriptive heading","paragraphs":["Observed evidence and its interpretation.","The bounded next action and remaining uncertainty."],"evidence":["Repository relative summary path and SHA256"]}
```

Wrap entries in `{"entries":[...]}`. The updater appends the note once; a content
change appends a revision. Keep entries tied to existing results. Do not change
data or hyperparameters through a note, and do not use frozen tests for tuning.

Before delivering a new report revision, render with the Documents skill's
`render_docx.py` and inspect its page images when a supported renderer is
available. `visual_review` stays `pending` until actual review, or records the
specific unavailable-renderer limitation. Do not label OOXML validation as a
visual review. The report remains useful and training continues if rendering
or publication is temporarily unavailable.

After the final comparison, final interpretation and document review are
recorded, disable just this producer task and the existing Codex heartbeat:

```powershell
Disable-ScheduledTask -TaskName 'JustPeachy Whistle Findings Report'
```

Use the Codex automation tool for the heartbeat; do not edit its TOML manually.
Stopping the report task does not stop training. Existing user pauses and the
campaign's finite error recovery remain authoritative.

## Separate exploratory transcription run authorized on 25 October

The earlier campaign is complete. The user separately authorized
`training/whistle_transcription_guarded_v1`, a bounded continuation of the initial
model with mixed-domain clean replay. Its commands and fixed scope are in
`../guarded_ami/README.md`. The existing report task and heartbeat were reactivated
for this experiment; a `campaign_complete` value for the old campaign does not
close the new run.

The collector's existing allowlist is unchanged. The heartbeat adds completed new
experiment evidence through stable, hashed `analyst_notes.json` entries and runs
`update_report.ps1` once per new milestone. It records the last analyzed milestone
and published report revision in the new run's `monitor_state.json`. Preserve the
initial model as default and label all new comparisons exploratory. Disable the
report task and heartbeat only after the new complete summary and final report
publication, following the active heartbeat instructions.

This separate run completed on 25 October at 4,000 updates under its declared
early-stop rule. Neither nonzero checkpoint passed all retention guards; the
initial model remains the default and no confirmation or refit was run. Final
analysis is retained under analyst milestone
`exploratory_final_interpretation_5830c14cd32cec2a`. The completed report retains
its explicit unavailable-renderer limitation.

## Full-training rerun authorized on 26 October

The user requested one entire rerun of initial-model training. The active root is
`training/whistle_full_rerun_v1`; maintained commands and frozen design are in
`../rerun_full/README.md`. It starts from the pinned pretrained base and trains
all parameters for three complete passes of the qualified training pool, keeping
the original four-domain objective weights and excluding development/evaluation.
The initial tuned model remains default. This is separate from every completed
campaign and the short exploratory continuation.

The existing CPU report task and Codex heartbeat are active again. The collector
still uses its existing allowlist: add new-root milestones through stable,
evidence-hashed analyst notes, then run update_report.ps1. New-root monitor_state.json
tracks report revisions and analysis. Preserve the layout-review limitation and
do not retry the blocked renderer installation. Final shutdown applies only
after this rerun's complete summary and final interpretation are published.
