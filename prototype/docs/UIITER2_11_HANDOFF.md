# Task11 — reversible session references

Implemented in the current Windows/CM5 prototype source. **Default Off;
experimental, ready for supervised field testing.** Existing modes, recipes,
original clean enrollment anchors and all neural checkpoints are retained.
No accuracy improvement is claimed. Task12 is unstarted.

## Use and launch

Settings → Advanced → **Session references / Undo**:

- **Collect candidate references**: consented, disjoint mature windows already
  produced by ReDimNet; progress is usable speech seconds. No extra inference.
- **Review**: personally confirm the actual speaker, without other speech/music.
  Original full-roster voice evidence must also agree. Leave uncertain windows
  pending. Seats, forced names and revised words cannot certify them.
- **Use approved bank**: independent opt-in, at most 10% weight. Original base
  winner and C088 voice gate must survive. Off gives original scores for future
  decisions; fresh Start resets identity history and discards unsaved candidates.
- **Promote selected to personal profile**: select confirmed windows for one
  person, approve, stop/drain capture and save a separate atomic bank transaction.
- **Discard session candidates** clears temporary references and turns controls
  Off. **Undo latest** removes that person's latest saved addition after restart.

PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy'
& .\prototype\Start-Prototype.ps1
```

Command Prompt / Anaconda Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy"
prototype\Start-Prototype.cmd
```

No new package installation. GUI launch does not start capture. Your actual
personal store was not used for testing; the checks used isolated local fixtures.

## Verified behavior and limits

The final native run used eight short controller epochs with existing CMU Arctic
audio. Enrollment, candidates and held-out utterances were distinct. Confirmation
in this harness was explicitly a **corpus-labelled test operator**, not a claim
of participating-human approval. Exact aggregates are in
[RESULTS](UIITER2_11_RESULTS.json); source hashes/scopes in
[CHECKS](UIITER2_11_CHECKS.json).

| Check | Result |
|---|---|
| Genuine candidate collection | Two disjoint windows, 2.711s usable speech; original voice agreement |
| Replaying promoted source | Zero new windows, including shifted overlapping windows |
| Fresh held-out speaker, Off / On / after Undo | Correct name in each final caption segment; no wrong name |
| Outsider with bank enabled | Unknown; zero named segments |
| Wrong speaker with assigned-seat/forced/text provenance | Two pending proposals, zero confirmations; base conflict freezes bank |
| Two-speaker mixture | No candidates; observed overlap freezes bank |
| Restart / rename / import / export / delete / Undo | Contract checks preserve UUIDs and original vectors; invalid import rejected before publication |
| Portrait touch workflow | Actual controller, synthetic profiles, consent → review → select → promote → matching → Undo; 480×800 client |

The short collection clips remained Unknown under ordinary temporal naming; that
does not make their pending candidate suggestion a confirmed name. Accepted
coverage is final caption segments (one in each fixture), **not** word-aligned
DER or a statistically useful accuracy estimate. Full original/On/Undo text is
retained in local evidence; earlier captions are not revised by the feature.

Native suite: **53.20s wall, 29.77s process CPU, 480.7MiB sampled peak RSS** on this
Windows desktop. The known-query bank performed 28 score calls in 12.39ms total
(0.44ms/call); genuine collection cost 3.79ms total. These small timers exclude
archive I/O and one-time prepared-file hashing. No new model/helper thread.
Desktop values do not qualify CM5's 2GB total RAM or latency/thermals.

All **306 software checks pass**, with exact bindings in CHECKS. They cover
intentional contamination, explicit consent, duplicate/shifted source support,
caps, base score comparison, motion/music/overlap/clock/domain freezes, failed
atomic writes, invalid imports, feature guards, data mutations and touch UI.
Earlier failed attempts remain private: one harness used float WAV instead of
the required PCM16; the replay test then exposed shifted-window recounting,
fixed by file-content hash and absolute file sample ranges. Final accepted
evidence was rerun after those fixes.

## Design and data

New modules: `reference_adaptation.py`, `adaptation_store.py`,
`adaptation_controller.py`, `adaptation_ui.py`. Existing controller/gallery,
motion invalidation and Advanced UI connect them. Frozen S6/S7 profiles, vendor
runtime, capture timing, ASR, ReDimNet network and enhancement processing are
unchanged. Limits: 16 pending windows; four confirmed per person per session;
six saved per person; ≤10% score weight. Existing quality and C088 values were
reused without a search. The full compatible roster supplies immutable base
scores even when the active mode uses a selected/closed roster.

Domain tags include tap/gain/preprocessing, beam stream and enhancement
model/hash/configuration. Candidate/source hashes, unique support, clocks,
quality flags, base versions, user confirmation and decision/seat provenance are
stored. Original `references`/NPY files stay separate. A changed original base
or roster disables old entries; Undo remains possible. Changed domains, strong
confirmation conflict, observed overlap/music, motion or clock failure freeze
the bank until fresh Start. Unknown noise/music stays explicitly unknown.

Permanent promotion is one bounded person.json atomic replacement with inline
bank and Undo history. Delete/rename/export/import validate this layout.
DATA_SCHEMA requires `session-reference-enrichment-v1`; older readers must
refuse it. Undo retains this conservative guard. Private exports include the
new voice features. Discard does not erase diagnostics already retained under
existing session policy. See [exact schema/controls](../app/README_ADAPTATION.md)
and [deployment notes](PI_DEPLOYMENT_WORKFLOW.md).

No new libraries, weights, conversion, tokenizer or dictionary. Existing asset
hashes were reverified; [dependency ledger](UIITER2_11_DEPENDENCIES.json) links
inherited licence obligations. No broad sweep, training, private recording
mining, microphone capture, playback, firmware/default-device change, Word edit
or automatic commit/push.

## Release and rollback

Current **local source variant: proto1-0.2.0 + tasks09–11**. Task08's existing ZIP
at `G:\Just_Peachy_PROTO1\releases\just-peachy-proto1-0.2.0.zip` is unchanged and
contains01–08 only. A future export must package current source; no misleading
replacement ZIP was produced here. Pre-task11 source/config/docs (272 files)
are preserved at `Resumes/.uiiter2_11/prototype_before_11.zip`.

Operational rollback: turn collection/matching Off; Undo approved additions if
desired; Start a fresh epoch for an original-only comparison. Full source
rollback, with the app closed, from repository root:

```powershell
& .\.edge-speech-env\python.exe Resumes/.uiiter2_11/restore_before_11.py
# Inspect the read-only plan, then apply only if desired:
& .\.edge-speech-env\python.exe Resumes/.uiiter2_11/restore_before_11.py --apply
```

CMD/Anaconda uses the same commands without `&`. The script checks hashes,
refuses later edits, preserves01–10, moves only added Python files to a private
backup and leaves personal data/models untouched. A data root carrying task11's
feature guard cannot be opened by the old source, even after Undo. Prefer current
code with matching Off; otherwise use a separate compatible `--data-root` and
the same `JUST_PEACHY_DATA` environment setting. Never remove the schema guard.

Reproduce the small checks using [test commands](../tests/README_ADAPTATION.md)
and [native/UI commands](../tools/README_ADAPTATION.md). Full local evidence:
`Resumes/.uiiter2_11/{native_accepted,unit_accepted,ui_accepted}`.

## Pending field checklist

**AWAITING_USER:** consenting real people/XVF, correct and deliberately wrong
confirmation, a different person taking a seat, movement/room change, music or
overlap missed by the existing detector, and separate O0/O1/enhanced references.
Compare fresh sessions with matching Off/On; record wrong names and accepted
coverage, not just convincing examples. Do not attest to unseen speech.

**NOT_TESTED:** native ARM64/CM5 execution, physical touch, target memory/thermals
and long-session behavior. Saved source support prevents repeated file-window
counts; it is not acoustic replay-attack detection. This intentionally cautious
bank may provide little benefit or lower coverage. No automatic permanent
learning is enabled. Workbook insertion notes are in WORKBOOK_UPDATE.md.
