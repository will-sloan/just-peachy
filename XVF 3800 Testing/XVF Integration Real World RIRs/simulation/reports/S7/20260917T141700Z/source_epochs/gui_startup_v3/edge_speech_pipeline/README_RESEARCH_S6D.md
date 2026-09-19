# S6D opt-in application delivery and display research

Purpose: isolate immediate text delivery, bounded active-utterance label repair, selected-person presentation, and independent direction association in the actual H2 CLI/GUI. Historical defaults, weights, original profiles and galleries remain unchanged. This is a research implementation; model-free checks are not neural, physical, timing-benefit or CM5 qualification.

Inputs: an exact v3 research profile, original admitted gallery when naming is enabled, prepared once-gained aligned mono16kHz WAV input(s), optional existing sanitized direction telemetry, and an explicit S6D settings JSON. Selection uses profile IDs bound before predictions. T1 needs one selected ID; T2 needs a selected set or `all_enrolled: true`. The actual gallery still evaluates all candidates with the parent's thresholds and Unknown rejection. V2/V3 require independently verified voice-to-direction evidence through `PipelineEngine.publish_s6d_direction`; generic selected-angle packets are not automatically linked to recognized names. Stored mono telemetry can leave association unavailable.

Outputs: complete original audio journals, complete events.jsonl, initial and latest labelled transcript exports, immediate `s6d_text_ready` records, stable utterance/token IDs, later punctuation/label/display revisions, monotonic publication/journal/consumer timing, bounded-queue counters, session finalization and a separate actual-consumer drain receipt. T0 is the full transcript; T1/T2 only change visible coverage. The GUI offers an unfiltered full view and pending indicator. No acoustic separation is claimed.

Direction/GUI follow-up is a separate source epoch from frozen native pilot v3. V1 is explicitly a global mono speech gate; it does not identify the speaking beam. V2/V3 require a nonempty matching capture_source_id, route_id and stream_id for the observation, named voice and speech record, plus explicit speech_evidence_id and voice_evidence_id links. Matching timestamps alone cannot make beam0 speech license a beam1 direction. Two independently supported speech streams may produce two V3 arrows; music, unknown identity, duplicate voices and missing route/evidence bindings remain hidden. Route/evidence IDs must come from native observation provenance, never scene truth or seat maps.

The actual Tk canvas displays at most two folded linear-bearing arrows and front/back ambiguity. Monotonic expiry combines remaining direction, speech and name freshness, includes queue delay from publication, and clears with the75ms GUI timer even if no new direction event arrives. Actual scheduling delay may exceed75ms under load and must be measured. Late/out-of-order updates cannot restore expired arrows. Widget updates/expiry are logged to s6d_gui_render.jsonl; this is not physical scanout timing. In S6D mode window close keeps the event consumer alive until the stop worker, finalization and event queue finish; native completion remains separate from model-free widget fixtures.

New words extending a previously named row return that enlarged row to pending. Delayed policy partials cannot relabel or replace newer text; stable-ID revisions declare the target span separately from voice-evidence support. This conservative row policy may hide previously visible target text while new words await support; its coverage/delay tradeoff requires scoring.

Same-track voice rejection/demotion can retract a prior confirmed name within the same bounded overlapping-source horizon; T1/T2 then hide the row and latest exports retain the anonymous replacement while preserving its first-final name. Nonfinite direction confidence or invalid source/availability clocks fail closed. Independent review identified both checks in the preserved v2 draft; regression fixtures cover them in the next epoch.

Actual GUI runs additionally write `s6d_gui_render.jsonl` with monotonic text-widget update start/end, source event publication, selected-name/visibility state and full-view use. These are actual Tk widget operations, not modeled GUI delays or physical display scanout timestamps. Controller-update timestamps remain separately named. Model-free withdrawn-widget tests alone do not qualify neural GUI timing.

Settings example (save as a fresh JSON file):

```json
{"schema_version":"edge-s6d.v1","text_delivery":true,"boundary_repair":true,"transcript_mode":"T0","direction_mode":"V0"}
```

The switches independently isolate text delivery and label repair. For a selected-person prototype add `"transcript_mode":"T1","selected_profile_ids":["ACTUAL_ADMITTED_PROFILE_ID"]`. V0 is a recent diagnostic; V1 requires current exclusive speech; V2 additionally requires selected confirmed identity and independently associated spatial evidence; V3 permits at most two distinct confirmed identities with such evidence. Freshness, current speech and association remain separate gates. Unknown/stale/overlap/conflicting association hides arrows.

Acceptance goals declared before S6D native outcomes: naming adds at most 0.10 seconds paired first-text p50 and 0.25 seconds p95 against its same anonymous application parent. Report p99, never emitted and raw-word equality as well. These are provisional goals, not measured results. The active-utterance repair uses the latest ASR publication as its bounded revision anchor; finalized utterances retain first-final anchoring. Source overlap, fresh voice evidence, count limits and committed adjacent-speaker protection still apply. Original first display and final labels/times remain preserved.

## PowerShell: model-free tests

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B -m app.edge_speech_pipeline.checks_research_s6d
```

## Anaconda Prompt / Windows CMD: model-free tests

No activation or installation is required; the existing interpreter is explicit.

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -m app.edge_speech_pipeline.checks_research_s6d
```

`checks_research_s6d.py` takes no inputs and prints unittest results. It uses synthetic vectors, no neural calls, no playback or device access. Its Tk window remains withdrawn while actual text widgets verify filtering/full view. It tests queue drain/overflow/failure, stable IDs, late identity addressing, rejected single-candidate voice, stale/music/overlap direction suppression and bounded arrival repair.

## Native file/GUI invocation

Run only a predeclared admitted matrix. Replace PROFILE, GALLERY, SETTINGS and WAV with exact existing files. Omit gallery for a matched anonymous profile. Use `--identity-wav` only with an aligned admitted split tap. The following commands start models; they are reproduction templates and do not claim that any run occurred.

PowerShell, from the directory above:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B -m app.edge_speech_pipeline file 'WAV' --research-profile 'PROFILE' --research-gallery 'GALLERY' --s6d-settings 'SETTINGS'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B -m app.edge_speech_pipeline gui --research-profile 'PROFILE' --research-gallery 'GALLERY' --s6d-settings 'SETTINGS'
```

Anaconda Prompt / CMD:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -m app.edge_speech_pipeline file "WAV" --research-profile "PROFILE" --research-gallery "GALLERY" --s6d-settings "SETTINGS"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -m app.edge_speech_pipeline gui --research-profile "PROFILE" --research-gallery "GALLERY" --s6d-settings "SETTINGS"
```

The default session destination remains documented in README.md; research orchestration should supply a bounded run-specific `PipelineConfig.session_root`. Queues reject overflow explicitly; they never silently discard audio or committed text. Only obsolete same-utterance UI partials coalesce, counted separately from the full journal. One owner drains policy, punctuation and journal workers at closure; CLI/Tk consumers record their own drained closure. Unlimited scientific logs/corpora are not a CM5/eMMC retention policy. Separate measured ARM64/storage qualification remains required.

Direction GUI review v2: every S6D event is stamped with its actual session ID. A verified `session_created` event clears prior rows/arrows and resets only that session's direction clock; ordinary Clear Display retains the watermark. Directions and display rows from a prior session are rejected, including after a100s session followed by a new1s source clock. Startup background workers and queued UI completion/error messages are tracked so an initially IDLE engine cannot cause close to destroy a window while a pending startup can still launch. Model-free checks include actual Tk session rollover and pending-startup close guards. Frozen direction_gui_v1 remains preserved as the reviewed adverse draft.

Independent review follow-up v3: starting another S6D session now rejects an undrained previous event inbox and requires that session's actual-consumer closure receipt. The previous committed events remain accessible. GUI close performs another stop/cancel after all previously admitted startup work and its UI messages finish, so a delayed enrollment startup cannot outlive the first cancellation; no new startup is admitted while closing. A named direction requires a nonempty common intersection of direction, voice and speech support; separate overlap with a broad observation is insufficient. Preserved GUIv2 reviewer fixtures cover these adverse cases without neural inference or hardware.
