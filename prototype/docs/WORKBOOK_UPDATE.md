# Workbook insertion notes — UIITER2 task 01

The master Word workbook was not edited. Add these notes to its prototype
iteration results section:

- On 20 September 2026, task 01 replaced the first-callback/latency-estimate hard
  bound with immutable stream-start plus counted native-frame timing, preserving
  explicit gap/rate/epoch and resampler checks. Historical false-bound behavior
  is reproduced deterministically; the precise old callback sequence was not logged.
- Failed-source Stop now continues finalization and safe cleanup; fresh Start
  clears the previous display error after releasing old ownership. Original
  failure records, people and model/configuration hashes remain unchanged.
- 156 software checks passed. Short real O0/O1 transition, immediate Stop and
  failure/restart checks passed with zero input drops and unchanged Windows
  render defaults. Native existing speech produced final text and its partial tail.
- Five-case lifecycle check: 29.65 s wall, 5.80 s CPU, observed 437.75 MiB process
  RSS; one load per ASR/speaker model. These are desktop measurements.
- Human scripted speech: AWAITING_USER. CM5 hardware, sustained drift and acoustic
  latency: NOT_TESTED. No new research/optimization/training or later task was run.
- Authoritative compact handoff: `prototype/docs/UIITER2_01_HANDOFF.md`; hash-bound
  receipt: `prototype/docs/UIITER2_01_CHECKS.json`. Changes are local, with original
  source backup; no automatic commit/push or replacement export.

## Task 02 — Calm captions and touch UI (20 September 2026)

- Compact 21px captions default; existing larger presets and saved preferences
  preserved. Stable S7 segment marks survive ownership replacement. Same-turn
  supported grouping, history scrolling and Back to live remain available.
- Immediate text default; optional fixed 150/300ms GUI batching. Final short
  fixture maxima were 1.70/157.17/310.01ms from first GUI-received change to widget
  application, excluding the separate 80ms poll. No WER improvement claim.
- Pending identity bounded to 1.2s, stable name display 200ms; explicit unavailable
  versus collecting. Generic Unknown default, numbered variants under Advanced.
  Raw decisions/scores and backend transcript remain intact.
- Conditional top-bar Show all replaces the permanent banner. Active tabs,
  compact settings controls, consistent Back, long-name handling, and a collapsible
  145px beam panel with fresh/stale shape/colour legend were verified.
- 166 software checks passed. Real-controller, existing-model six-second O0
  speech fixture passed in 10.68s wall with one ASR/speaker load and clean close;
  actual app screenshots at 480×800 and 600×1000 reviewed separately from mocks.
- No task 02 microphone capture, enrollment mutation, new model/library, dataset
  sweep, commit/push or export build. Human usability and CM5 remain NOT_TESTED.
  See `UIITER2_02_HANDOFF.md` and its hash-bound checks.

## Task 03 — Linked sessions, exact audio and resources (20 September 2026)

- Developer Sessions adds text-only/explicit consented audio drafts, Stop,
  Save/pin/reopen, rename, notes, separate corrections, privacy-confirmed export,
  confirmed delete and explicit-output caption listening with capture isolated.
- Actual model-input master: post-XVF mono16k float32, same source for current
  ASR/identity. No second O0 gain; no claim of raw microphones/all beams. Actual
  embedding/segmentation window indices and padding support on-demand exports.
- Raw ASR/revisions, provisional/final formatting, identity events, mode/roster,
  source clocks, model/code hashes, gaps and ~1Hz CPU/RSS/queue data are linked.
  Coarse caption intervals are not phonetic alignment; no watts or SNR estimates.
- Bounded async archive, source-backed index, atomic recovery and pinned-data
  retention. 2GiB target, 10 unpinned drafts, 256MiB audio/64MiB metadata per epoch,
  2GiB free floor; partial recording is visible and not silently padded.
- 185 software checks passed; short real-model fixture passed in 10.24s wall:
  96,073 exact float samples, 16 model windows, 17 formatting records, 8 resource
  samples, restart/reopen and isolated fake-output matching caption playback.
  Maximum sampled process RSS 445.98MiB; no CM5/overhead/power claim.
- No physical playback/new mic test, training/sweep, new model/library, public
  data dump, commit/push or release rebuild. CM5/human usability remain pending.
  Handoff: `UIITER2_03_HANDOFF.md`; compact hash receipt: `UIITER2_03_CHECKS.json`.

## Task 04 — Explicit roster modes, Unknown and scores (20 September 2026)

- Just Transcription replaces Captions. Ordinary named modes use one generic
  Unknown; all/selected galleries are explicit. Selected matching genuinely
  loads only chosen compatible UUID references. Draft picker cancellation is
  inert; Apply validates and changes at a safe epoch. Duplicate names use UUIDs.
- Selected Closed group is an experimental assumption: eligible fresh clean
  voice chooses a selected profile even below open rejection, with forced names
  visibly marked assumed. Silence/overlap/stale/missing voice does not force.
  One selected person is user-assumed. No personal reference adaptation occurs.
- C079/C060 spatial modes remain selectable with all/selected roster variants.
  Advanced retains numbered no-gallery/all-enrolled comparisons. Highlight/hide
  uses an independent display roster and does not restart or change matching.
- Advanced raw-score panel shows candidates/margin, actual decision status,
  thresholds, voice support, spatial term/age and decision recipe. Scores are not
  probabilities. Only bounded existing threshold/margin/spatial weight controls
  are exposed with exact Reset and epoch logging; defaults were not tuned.
- 209 software checks passed. Six actual 12s CMU native cases passed in 80.69s:
  selected A recognized, B Unknown with only A selected, B recognized with the
  all gallery, B explicitly assumed as A in closed mode, and both spatial
  selected variants executed. One ASR/speaker load across all six streams.
- Final 17.50s native check confirmed that changing display roster/hiding keeps
  the gallery and stream intact; assumed captions and score provenance passed.
  Six-case maximum sampled Windows RSS 502.96MiB / process CPU counter 43.344s;
  no CM5 or power/overhead/general accuracy claim.
- Export: `MODE_MATRIX.json` (10 modes / 46 actual default configurations), plus
  per-session effective profile/UUID/gallery/override records. Native private
  logs/vectors stay local. Live users/groups/outsiders, physical touch and CM5
  remain NOT_TESTED. No sweep/training, new dependency/model, commit/push,
  master Word change or release rebuild. See `UIITER2_04_HANDOFF.md` and checks.

## Task 05 insertion notes — 20 September 2026

Add two experimental prototype modes: Assigned seats - Direction only (closed seating), and Assigned seats - Voice + direction + Unknown. A session-only UUID map uses the native folded 0–180° bearing, default ±25° tolerance, explicit collision outcomes and manual re-anchor. Reusable templates never authorize a physical anchor. Direction names are seat assumptions; hybrid retains C088 voice evidence and Unknown with existing C079/C060 soft/strong priors. Manual/stub motion invalidates seat state while captions/voice memory continue. No person is learned from a direction.

229 software checks and three real saved-model/file cases with explicitly synthetic telemetry passed; actual assumed labels reached the Tk caption widget. Native cases totalled 41.016s, max sampled RSS 516.99 MiB, one ASR and one speaker load. No compute saving or field accuracy gain is claimed. Fresh live/person/XVF, physical touch and CM5 tests remain NOT_TESTED / awaiting participation. No new sweep, training, models or firmware changes. See UIITER2_05_HANDOFF.md for timing-clock repair, parameter export and rollback. These are insertion notes; the master Word workbook was not edited.
## Task 06 insertion — paragraph enrollment and progress

Add under prototype enrollment: four choices now include Read paragraph → Done,
with no arbitrary timed quota/verbatim rule. 15/30/60 retain unique usable speech
targets. Done keeps the existing 0.5s admitted model-input minimum and quality
gate, labels under-15s references limited evidence, and requires drained READY
before Save. Progress separates captured/level activity, pending quality and
verified unique time; the UI only animates toward real verified support.

Only paragraph mode preserves offered text/hash as reference metadata and
ordinary unbiased ASR endpoint text/timing plus estimated coverage/agreement.
Skips/paraphrases never gate voice quality. ReDimNet remains audio-only; knowing
the script does not strengthen vectors or imply training/alignment. No dictionary,
aligner, extra model or study was added. ASR estimates can lag the existing 10s
chunk and are finalized at Done. Raw reference audio is not retained by default.

242 software checks passed. Native identical 12s input yielded bit-identical
pre/post vectors and support (delta 0), Done accepted while a 15s target did not,
and profile restart/export/import/tap isolation passed. Final bounded native
check: 4.633s wall, 6.375 CPU-seconds, 433.62 MiB peak Windows process working set,
one ASR and one speaker-model load. Fresh human/XVF, physical touch and CM5 remain
NOT_TESTED. See UIITER2_06_HANDOFF.md for limits/rollback; no master Word edit.
## Task 07 insertion — names/vocabulary/text assistance

Prototype Settings now exposes default-off spelling suggestions and explicitly
approved contextual rules. Original 24-word vocabulary plus up to64 user entries;
no third-party dictionary/package/model. Generic suggestions require review.
Amir/Emir is never universally replaced; exact user context and approval are
required for automatic rules. Another enrolled Emir, conflicts, substrings,
negation/numerals/pronouns and protected terms block automatic edits. Linked
profile rename/delete disables its preference until re-approved. Speaker identity
never supplies spoken words or receives corrected-text evidence.

Raw, provisional, final, assisted and manual layers remain separate with source
links. Assisted captions show a pencil marker; Off restores original formatting.
Manual correction and Undo remain separate from the original journal. 253
software tests passed, plus a small genuine native caption/archive run and nine
explicit text fixtures. Full real example remains private; no general ASR gain.
Human field use/physical touch/CM5 remain NOT_TESTED.

Enrolled-name acoustic bias is visibly unavailable: installed Sherpa1.13.4 has
the hotword API but no qualified matching Giga ASR BPE vocabulary is bound. The
punctuation BPE is not interchangeable. Greedy decoding/models remain unchanged;
no hotword boost or acoustic A/B is claimed. See UIITER2_07_HANDOFF.md and the
source/resource/dependency receipts. Master Word workbook was not edited.
# Task08 insertion — consolidated release and hardware preparation

20 September 2026: proto1-0.2.0 consolidates accepted implemented tasks01–07;
optional09–12 are not prerequisites. Task08 adds a timestamped mockable motion
safety contract, fill-in disabled/null hardware configuration and wiring/arrival
plan, paragraph-reader downgrade refusal, and a versioned hashed source export.
Existing S6/S7 methods, inference code and model assets are retained; no new
dependency/model, research sweep, device flash, remote deployment or push.

257 application checks and 22 packaging checks PASS. Existing WSL x86-64 also
passed the 22 stdlib packaging tests and rejected the ARM64-only installer on the
wrong architecture; it is not ARM64 qualification. Thirteen existing ARM64 wheels
rehashed without downloading. A genuine 12-second native anonymous portrait/file
session preserved exact input audio, switched modes without model reload, saved/
reopened cleanly and exercised mock movement. 480×800 UI, 398 updates, 0.475 s
largest update gap, about 488–490 MiB loaded desktop RSS; not a Pi/soak claim.

Final exported-code acceptance is recorded separately in
`Resumes/.uiiter2_08/export/FINAL_RELEASE_RESULTS.json` (relocation, native caption
file, actual Windows launchers, portable contracts, failed-startup/rollback with
fixture enrollment preservation). See `docs/UIITER2_08_HANDOFF.md` for scope.
Status: software-prepared / Windows-tested; ARM64-tested NO; hardware-pending.
Actual CM5 2 GB/32 GB/no-wireless assembly, display/touch, matched ARM64 XVF control,
IMU/camera/GPIO and consenting live participant tests remain. Local vendor rpi
host binaries are ARM32. BMI270 is not drift-free room position/absolute yaw.
No unknown wiring assignments were invented. Master Word file remains unchanged.

# Task09 insertion — optional script-aware enrollment

20 September 2026: local source now has a default-off Text-aware reference
selection helper. Post-recording review compares intended paragraph with unbiased
ASR, reports approximate agreement/unknown timing/quality coverage and preserves
separate correction notes. Versioned hash-bound ScriptEvidence records selected
contiguous 2–4s contexts (maximum six), exact source support, frozen model/route
bindings and null phoneme boundaries. The original ReDimNet anchor is preserved.

Alternate reference cosines are advisory; the actual naming pipeline still uses
the original centroid and S6/S7 rules. No reliable matched-content/phonetic score
is available: calibrated query-content confidence and validated acoustic
boundaries are missing. No CTC model, dictionary, training or dependency was added.

269 software checks pass. Four existing CMU reference recordings retained 12s
original support and selected 12s unique alternate support. Disjoint fresh-query
tests preserve ordinary scores exactly; the extended known query confirms its
enrolled person and the outsider remains Unknown. The short known query remains
tentative under the unchanged temporal policy. Same-prompt outsider and wrong/
skipped/repeated script checks do not make text establish identity. The tiny
sample does not show a general accuracy gain. Resource measurements and exact
scopes are in UIITER2_09_HANDOFF.md; live human/XVF and CM5 remain untested.

The task08 archive is unchanged and does not include task09. New sidecars require
a compatible data reader; switching Off restores original-only behavior without
deleting references. Master Word workbook remains unchanged; tasks10–12 not begun.

## Task10 insertion — optional model coordination

Added experimental stateful DPDFNet post-XVF mono16k routing (bypass/ASR/identity/both), default bypass, existing-evidence coordinator, independent enhanced enrollment domains and exact consented stream/window archives. Small frozen native checks are mixed: quiet speech improved, stationary-noise errors increased, overlap looked falsely cleaner to the unchanged gate. No accuracy gain or CM5 qualification claim. See UIITER2_10_HANDOFF.md / UIITER2_10_RESULTS.json for measured values. Tasks11–12 remain unstarted. Master Word workbook unchanged.

## Task11 insertion — reversible references

Implemented optional default-off collection of disjoint mature voice windows,
explicit speaker confirmation, separate ≤10%-weight environment/session bank,
transactional promotion and persistent Undo. Original enrollment anchors and
neural checkpoints remain unchanged. Seat assumptions, forced names and edited
text never certify candidates. Tap, enhancement model/config and beam domains
are isolated; conflict, overlap, motion and timing failures freeze enrichment.
Small real-model checks retained the same held-out speaker with Off/On/Undo,
kept an outsider Unknown and rejected deliberate wrong-speaker confirmation.
No accuracy gain is claimed. Human confirmation/real rooms/CM5 remain pending;
see UIITER2_11_HANDOFF.md and RESULTS for measured details. Task12 unstarted.
This is an insertion note only; the master Word workbook was not edited.

## Task12 insertion — optional audio-grounded transcript review

Current Windows source provides default-off review of one consented, archived
ASR utterance (≤20s), using the pinned original model and decoder settings. It
retains original words, offers at most one different unbiased re-decode, and
requires explicit user adoption into a separate correction with Undo. Names,
pronouns, negation, amounts and unusual changes are highlighted. No LLM was
installed: the finite correlated candidates supplied no justified helper role.
321 software checks, seven small native cases and actual 480×800 UI checks pass.
Five speech outputs were unchanged, retaining six reference edit errors across
39 reference words (15.38% both before/after); this tiny correlated set is not
an accuracy benchmark. Noise still changed reference “she” into “he”; silence
and three-tone controls abstained. Synthetic harmful alternatives were flagged,
not automatically adopted. Human/nonword/name acoustic checks remain pending.
ASR loaded once; native check took 25.53s, peak process RSS 375.47MiB; speech
review workers took 0.19–0.29s. These are Windows caption-only measurements,
not combined full-stack CM5 qualification. CM5 review remains disabled. See
UIITER2_12_HANDOFF.md / RESULTS. Master Word and task08 ZIP remain unchanged.
