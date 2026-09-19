# Supported prefix and pending suffix: S7 candidate_v2

Purpose: implement one explicit display-history alternative, `ownership_mode="supported_prefix_v2"`, in `research_s7_presentation.py` and `gui.py`. The default `conservative_v1` retains the prior whole-caption clearing behavior. No frozen pilot/source, model, identity threshold, freshness duration, correction horizon or direction gate is changed here. Root owns S7Settings/runtime wiring, source freeze and production authorization. This mutable source must not be launched as a production experiment.

## Inputs and ownership

The controller receives original prediction-only caption/identity events with exact session, utterance, event, source span and text revision joins. It still rejects wrong target spans, disjoint support and old/conflicting identity versions. If `target_text_revision_id` is supplied it must match the current caption revision, including replaced words at identical source extent. Old saved events without that field are explicitly marked `LEGACY_MISSING_COUNTERFACTUAL`, not upgraded to an exact revision certificate. Tracker IDs are never fabricated.

An accepted identity is retained as an independent snapshot with its exact accepted raw text, text revision, token IDs, identity/evidence IDs and original support/target spans. Lexical tokens use non-whitespace runs only; character ranges preserve every original whitespace character. They have durable session/caption-local IDs. New hypotheses keep IDs and accepted ownership only through the exact unchanged token prefix. Replaced and newly appended suffix tokens get fresh IDs and pending ownership. Truncated tokens do not regain ownership if reintroduced. An admitted identity targeting the current full revision can collapse the segments. No word timestamps or phonetic alignment are invented.

Each caption's segments partition its raw text and token IDs exactly. A segment has its own stable ID, token/character ranges, current text revision and accepted identity revision. Accepted identity snapshots are shared internally rather than copied per token. Existing row/pending capacities remain in force. Existing append-only native display/event journals record returned transitions; the controller retains bounded current rows, not an unbounded duplicate history.

The whole row has no known-person attribution while supported/pending segments coexist. M0/M1 strip known-name display per segment. M4 applies selection per segment; full view restores hidden segments without rewriting canonical text. M5 places each segment once in its stable person column or unresolved/other area; token ranges retain the original cross-column order. Mixed segments render exact raw strings. A single segment can render the original accepted punctuation display string; canonical raw text remains unchanged.

## Clocks and GUI

Segments carry original observed policy-ready, publication, source-end, fixed-expiry and history-clock fields. All supported prefix attribution is `historical_caption_annotation_only`; it grants no current voice/direction permission. GUI receipt, render-finished application and idle callback are separate acknowledgments containing deep copies of exact segment states and rendered token IDs.

At widget application completion, freshness is observed again from the same actual monotonic source origin. Where the explicit origin is absent, the exact same-clock mapping `policy_decision_finish_monotonic_sec - observed_policy_decision_ready_at_sec` is permitted; this is not a model-cost estimate. Readiness/publication flags remain unchanged. Application can expire prior freshness and cannot renew it. Missing/inconsistent clocks are unavailable (null), never assumed fresh. Idle acknowledgments describe the last actual applied state plus callback time; they do not claim physical scanout or grant a continuing live indication.

No GUI direction/arrow permission is added. Historical captions may remain visible after evidence expires. Root's separately reviewed policy clock and target-join repairs must be admitted before a new live run.

## Fixture inputs and outputs

`test_presentation_prefix_v2.py` reuses the 11 original presentation fixture bodies in an isolated candidate_v2 namespace, adds focused prefix/replacement/empty/correction/clock/partition tests, and optionally exercises real Tk widgets. Model/audio/hardware/startup dependencies are explicit forbidden stubs. It does not run an engine or inference.

With `--saved-pilot`, it reads only the four exact completed consumer journals bound by `application/presentation_saved_replay_v1/SAVED_REPLAY_v1.json`, verifies their bytes and hashes, and replays presentation events. It writes an append-only `SAVED_TRANSITIONS.jsonl` and a source-bound `RESULT.json`. Every changed state must partition all raw characters/tokens, and each final must preserve exact raw words and finalization. These are counterfactual saved-log transitions, not measured GUI dwell or a new native result. The short pilot has no confirmed enrolled name or after-final identity correction; synthetic fixtures cover those state contracts, not empirical accuracy.

The output directory must be fresh. Existing receipts and earlier draft source bytes remain preserved. The commands below use a new manual namespace; choose another explicit fresh suffix for subsequent runs.

## PowerShell

```powershell
$R7 = 'C:/Users/amiri/Documents/GitHub/just-peachy/XVF 3800 Testing/XVF Integration Real World RIRs/simulation/reports/S7/20260917T141700Z'
$Py = 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
& $Py -B "$R7/application/presentation_prefix_v2/test_presentation_prefix_v2.py" --tk --saved-pilot --output "$R7/application/presentation_prefix_v2/checks_manual_01"
```

## Anaconda Prompt / CMD

Use the existing absolute interpreter; no installation or environment mutation is required.

```bat
set "R7=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S7\20260917T141700Z"
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%PY%" -B "%R7%\application\presentation_prefix_v2\test_presentation_prefix_v2.py" --tk --saved-pilot --output "%R7%\application\presentation_prefix_v2\checks_manual_01"
```

Omit `--tk` for model-free state checks without a window; real Tk checks will then be explicitly skipped. Omit `--saved-pilot` to avoid journal reads. Actual C105, handoff, named profiles, policy delay and GUI timing still require root-authorized frozen native evidence.

