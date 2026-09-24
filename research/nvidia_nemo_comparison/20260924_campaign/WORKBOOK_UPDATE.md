# Proposed workbook insertion - N1

The master workbook was not rewritten. This proposed insertion is backed by
the completed `N1_METRICS.json` and `N1_HANDOFF.md`.

**Foundation and shared interface.** Preserved the accepted current prototype
and model hashes in a campaign branch and baseline tag. The old whole-paragraph
speaker overwrite was reproduced with a source-only A/B/A fixture. N1 adds a
separate BACKEND selector, an anchored active caption pane, stable timestamped
revision spans, speaker revision provenance and idle saved-audio startup. All
backends use one mode/interface contract; unavailable candidates are explicit.
The GUI stays 480 x 800. The actual installed entrypoint opens idle even with
saved auto-listen preferences, and closes cleanly without loading models.

**Data.** Bound all 240 accepted same-pass pairs and both taps (480 prepared
cells), retaining 156 complete nonoverlap, 47 overlap, 26 incomplete-reference
and 11 empty scenes. Full original and normalized transcripts were audited
locally for 777 occurrences. O0's existing +3 dB is applied once; runtime gain
is unity for both taps. All 30 Upper Loeb scenes remain; Loeb Caf stays excluded.
The fixed model-free screen has 48 scenes, four per family. Supplemental saved
C105/short/return/silence regressions remain separate from its denominator.

**Reference plan.** E/C/Q has disjoint verified source, file, decoded-PCM and
prompt identities. Clean references cover 43 people with explicit 5/15/30-second
availability; existing processed E covers 30 people. Fixed roster conditions
retain strangers, absent enrolled people and insufficient-duration cases.
Processed C remains collection-only until its projection admission is reviewed.
Embedding namespaces stay model-specific; no personal gallery or incompatible
ReDimNet vectors are reused by TitaNet.

**Validation.** The main software suite ran 386 tests with zero failures/errors
and two platform-specific skips. Release, supervisor, note-example and installed
entrypoint checks have separate receipts. Source EVENT and actual private-desktop
renders cover A/B/A, simultaneous updates, interruption, late correction,
scrolling and large paragraphs. Final metrics record 96 main-screen and eight
supplemental native audio cells, plus 96 final-snapshot GUI replays. Source-clock
event timing, Tk application and physical scanout are separate evidence scopes.
Noise-only S45_12_20 emitted one false one-word final utterance per tap; the
supplemental digital-silence case emitted no text. Execution success does not
assert error-free recognition.

**Assets and operations.** Five pinned official candidate weights were staged
and hash-verified, and the official native Windows CPU runtime built. Build/help
success does not establish candidate inference, 2 GB capacity or Pi performance.
A1/E1 NeMo/export setup and optional X1/PnC work remain later-stage conditions.
Real Windows 10/15/30-minute probes, independent workers, watchdogs, locks,
checkpoint resume and cleanup checks are installed and tested. Healthy unchanged
probes invoke no LLM. Automatic Codex resume is unavailable without a verified
competing-turn guard; continue manually in the existing task.

**Limits and next stage.** No Pi/hardware speech session, new acoustic bank,
denoising comparison, training or model ranking occurred. Exact word/phonetic
truth and independent conversational punctuation gold are unavailable. WD-40
reconstruction remains N3 work; existing Amir safeguards are source/interface
tests, not new human acoustic evidence. Progressive adaptation is off in the
primary comparison. Follow the N1 handoff's readiness decision before N2.

Use `NOTE_COVERAGE.csv` for the 73-item mapping, `RELEASE_RECEIPT.json` for launch
and rollback bindings, and `GIT_RECEIPT.json` for verified remote backup.
