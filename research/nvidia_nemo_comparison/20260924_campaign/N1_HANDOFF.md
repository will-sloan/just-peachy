# N1 handoff

Status: **COMPLETE. N2 may proceed** using this frozen version and the existing
campaign ledger. `N1_METRICS.json` contains the checked acceptance decision.
N2 has not been started automatically.

The original Windows prototype was preserved in an isolated campaign worktree.
Its 112 runtime/config files matched the saved Pi rc5 copy at initial inspection;
the Pi itself remained off. The source-event A/B/A probe reproduced the original
whole-paragraph identity overwrite. The repaired common interface retains the
unchanged neural weights and replaces paragraph-level ownership with stable
timestamped revision spans and separate speaker corrections.

## Implementation

One 480 x 800 Tk application now has a visible BACKEND selector independent of
logical mode, recipe and O0/O1. Switching a backend stops the active session and
preserves those choices; unavailable candidates cannot silently use baseline
models. The common mode list is preserved, including spatial/seat choices with
an honest unavailable state when matching telemetry is absent. Generic Unknown
is the ordinary display; numbered identities stay Advanced.

The active caption pane is anchored below independently scrollable history.
Partial text revises a stable suffix. Compact fonts/spacing, current navigation,
bounded pending labels, score/margin diagnostics and conditional full-caption
rescue remain. Stable span IDs survive supported label corrections; unchanged
prefix words cannot be relabelled by a later speaker simply because they share
a paragraph. Rewritten suffix spans are retired with their provenance. Raw,
formatted and optional edited text stay separate. Exact acoustic word timing
is not invented.

Startup is idle and saved-audio-only. The actual installed entrypoint ignored
saved auto-listen preferences, loaded no models, and closed normally with its
lock released. Live enrollment and existing personal data structures remain for
future use, with isolated persistence/interface tests now. Personal profiles
and existing recordings were not migrated or shipped.

The complete note ledger contains 73 items across the 13 supplied summary
sections. It distinguishes observations, requests and hypotheses, and links
changes/tests/deferrals. The full original notes were not supplied; the ledger
does not pretend its paraphrases are verbatim original wording. WD-40
reconstruction and new phonetic/adaptation efficacy remain later-stage work.

## Bound data and assets

The audit verified 240 accepted same-pass O0/O1 pairs, 480 prepared waveforms and
their 480 original PCM24 tap captures, exact sample formats/counts/hashes, gain and
offset provenance. It compared full original/normalized text for 777 utterance
occurrences locally. The 240-row catalogue preserves 156 complete nonoverlap,
47 overlap, 26 incomplete-reference and 11 empty scenes. No Loeb Caf scene was
admitted; all 30 Upper Loeb scenes remain. Prepared O0 already has +3 dB, and
both taps are passed to inference at unity gain.

The fixed model-free screen has 48 scenes, four per family, including 32 complete
nonoverlap, 9 overlap, 6 incomplete and 1 empty case. The main denominator never
changes. Four existing C105/short/return/silence scenes supply eight explicit
supplemental tap cells. All 240 scenes remain bound for later comparisons.

E/C/Q checks verified 385 clean E clips, 367 C clips and 449 unique Q waveforms
underlying the 777 occurrences. Exact source/file/decoded-PCM/prompt intersections
are empty. The 43-person, 5/15/30-second capability matrix retains shortfalls.
Existing processed E covers 30 people and 360 conditions. Processed C has 72
conditions but remains collection-only pending projection admission. Clean and
processed domains are distinct; model-specific galleries must be re-extracted,
never filled with another encoder's vectors or private personal recordings.

Five official core candidate files total 2,110,660,032 bytes, verified against
official SHA-256 identities. The official pinned native Windows CPU runtime
was built with microphone/CUDA/server/TTS routes disabled, then version/help
checked. The model/access matrix separates release dates from card changes,
weights from code licenses, and build success from inference/parity. A1/E1 need
isolated NeMo/export setup; optional X1 and unverified standalone PnC are explicit
deferrals. N1 does not rank models or claim CM5 feasibility.

## Acceptance evidence

The application suite ran 386 tests with zero failures/errors and two Linux-only
skips. Separate checks cover release tooling, supervision, WD-40/Amir text
invariants and the actual installed entrypoint. A/B/A, short interruption,
simultaneous events, late correction, scrolling and large paragraphs have
source-event fixtures and seven actual 480 x 800 app renders. The final receipts
record 96/96 paired-screen cells, 8/8 supplemental cells and 96/96 final-state
GUI replays, with no execution failures. All input frames were delivered; no
clock-order violations, duplicate span IDs or missing first/committed labels
were observed. Full private events are referenced by path and hash, not copied
into the handoff.

The paired baseline uses the real common Controller/core with fresh per-scene
state and no gallery; only weights are resident between cells. Delivery is
source paced. Its actual final snapshots are separately rendered through the
same frozen GUI. That replay verifies text/span retention and layout, not the
original online GUI latency. No historical neural predictions substitute for
the new N1 runs. The descriptive lexical report omits metrics whose reference
conditions do not support them; it is not a model comparison. On the 32
complete nonoverlap scenes per tap, descriptive lexical WER was 11.38% for O0
and 12.61% for O1. These are reference-limited baseline diagnostics. The noisy
empty control S45_12_20 produced one nonempty one-word final utterance on each
tap; supplemental digital silence S45_12_15 produced no text on either tap.
These are observed recognition limitations. N1 acceptance covers execution,
integrity and interface behavior.

## Freeze and release

| Item | Exact binding |
| --- | --- |
| Campaign branch | `codex/n1-foundation-20260924` |
| Preserved baseline commit/tag | `509195b8c95c3a93eb63666e17038afc05a60d79` / `n1-baseline-20260924-rc5` |
| Common source commit/tag | `2a8a2183c0050b6abf76ef27bbd803adad632a87` / `n1-common-ui-20260924-v1` |
| Common UI source SHA-256 | `54c0283b8058978eca87dc9b0461a15addf804200856e41d2c83b55bff590456` |
| Whole frontend/runtime SHA-256 | `c704856684409dbb1d5d1a708009623f03f45de40967d6f8c881307d8f87611b` |
| Baseline backend ID | `sha256:1a6be7490786a81d971c19ad35572b8c13c30993f7b8a7c1903f4b0617b6b1b5` |
| 48-scene screen SHA-256 | `289fbf1e216762dd1b56c1d53b650cc0f176fb9410282cc8b579687183fdbd94` |
| Source release ZIP SHA-256 | `92ace449cc60c5967e00d038a966ddb4c12fd68d51121b88417dcff848bcb42d` |

The 1,074,526-byte standard source release has 240 verified files and is staged
at `G:\Just_Peachy_N1\20260924_campaign\local\Installed Baseline`. Imports,
model asset validation and actual idle startup passed. `Start-N1.cmd` and
`Start-N1.ps1` launch it later with an isolated data root. The README contains
PowerShell and CMD/Anaconda commands, inputs, outputs, source-freeze and package
commands. Rollback selects the original untouched checkout or preserved
baseline archive; no original/installed Pi pointer was changed.

GitHub backup uses the existing public repository with visibility unchanged,
one campaign branch, no force push and no merge to main. The final Git receipt
records the remote refs actually verified. Private voices/profiles, full
transcripts, model binaries and raw corpora remain local.

## Supervision and next stage

Three real Windows scheduled tasks are registered: `JustPeachy-N1-20260924-setup`,
`-inference` and `-replay`, with 10/15/30-minute phase-gated intervals. Trigger,
overlap, failure, checkpoint resume and reserved-task cleanup were exercised.
Numerical workers continue independently; OS locks prevent simultaneous owners,
and disk reserve checks protect at least 50 GiB on C: and 75 GiB on G:. G: is the
Kingston 2 TB NVMe SSD. Two below-normal CPU workers are a research-throughput
setting, not a 2 GB target resource measurement.

Unchanged healthy probes invoke no LLM. Changed/error/completion states write
small requests for this exact Codex task. **Automatic Codex resume is unavailable**
because no atomic competing-turn/queue guard was verified. Manual continuation
in this existing task is required; `RESUME.md` supplies the exact instruction.
No second stage dispatcher or ambiguous last-session resume was installed.

One 96-hour ledger starts 2026-09-24T14:48:19.949192+00:00 and targets
2026-09-28T14:48:19.949192+00:00, reserving 12 hours for packaging. Finish sooner
when done. Baseline and Nemotron hybrid have priority, compact ASR/enrollment
next, 600M alternatives next, optional multitalker/standalone PnC last. The
throughput forecast is in `CAMPAIGN_FORECAST.json`; it does not turn source-paced
Windows timing into Pi performance.

N2 readiness is gated by `N1_METRICS.json`. N1 ends after its completed handoff;
no unqueued N2/model comparison or hardware session starts automatically.
See `LIMITATIONS.md` for evidence boundaries and `WORKBOOK_UPDATE.md` for the
proposed workbook insertion. The master workbook is unchanged.
