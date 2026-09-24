# Optional reversible session references (task11)

Purpose: review a few existing ReDimNet mature speech windows, explicitly confirm
the actual speaker, optionally compare a small environment bank, and promote or
undo selected additions. This is reference data, not neural training. No new
model/library, microphone owner, playback, USB polling or inference worker.

N2 backends do not admit this adaptation workflow. Their session-reference page
shows an unavailable explanation; collection, matching, confirmation, promotion
and Undo actions cannot attach or modify a session bank. Changing backends
discards pending candidates and sets both toggles Off. The baseline workflow
below remains available after selecting baseline again.

The N2 guards and roster round trip have model-free tests. From the campaign
worktree, PowerShell:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B -m unittest discover -s prototype\tests -p test_n2_integration.py -v
```

CMD / Anaconda Prompt:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -m unittest discover -s prototype\tests -p test_n2_integration.py -v
```

These tests use fake compatible stores and inert model-path fixtures, with no
microphone or neural model calls. They print pass/fail results and remove their
temporary application roots. Do not set `N2_TEST_E1=1` for this model-free run.

## Run the prototype

PowerShell, from any folder:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy'
& .\prototype\Start-Prototype.ps1
```

Command Prompt / Anaconda Prompt (no environment activation needed):

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy"
prototype\Start-Prototype.cmd
```

The launcher uses the existing pinned environment. Do not install globally.
Settings → Advanced → Session references / Undo. Choose a voice-name mode and
compatible original enrollments first. Both collection and matching default Off
at application launch; enabling either does not start capture. Start requires
the ordinary microphone consent. Modes, recipes, text processing and O0/O1 keep
their existing meanings. Captions, anonymous-only and direction-only modes do
not provide usable voice evidence for this feature.

1. **Collect candidate references** requires participant consent. Speak one at a
   time. The page counts usable clean speech, not elapsed wall time.
2. **Review** shows source seconds, clean fraction, clipping, original voice
   cosine/margin and exact domain. Confirm only a speaker you personally heard,
   without music or competing speech. If unsure, leave the proposal pending.
3. **Use approved bank** separately enables experimental matching. Confirmed
   session candidates and compatible promoted entries can contribute. Off
   immediately restores original scores for future decisions; existing identity
   history and earlier captions are not retrospectively rewritten. Use a fresh
   Start for an entirely fresh baseline identity epoch.
4. Select confirmed windows for **one person** and **Promote selected to personal
   profile**. Explicit approval stops/drains capture and writes one atomic
   person.json transaction. Original enrollment NPY files are never modified.
5. **Discard session candidates** erases pending RAM candidates and turns both
   controls Off. Saved additions remain. **Undo latest** removes the most recent
   active promotion for the chosen person, including after restart; it stops
   capture, clears session candidates and switches matching Off.

Normal Stop retains candidates for review. New Start clears unpromoted candidates
and takes a new immutable base snapshot. Closing loses RAM candidates. Freeze is
latched until fresh Start; toggling/discarding cannot silently unfreeze it.
This page stores no new waveform files. Existing consented Sessions audio and
diagnostic policies still apply; candidate metadata/score audit may be in private
session logs, so Discard is not a promise to erase already archived diagnostics.

## Inputs, outputs and bounded policy

`reference_adaptation.py`: immutable full-compatible-roster base matrix and
version; existing native embedding event; exact identity-journal float32 audio
window; domain and decision/seat/noise provenance. Outputs pending proposals,
original-versus-bank scores, effective weights, candidate IDs, freeze reasons,
usable durations and small compute counters. No text/seat name is an authority.

Only admitted **mature** 1–4s windows with ≥80% clean support, actual RMS≥.002,
clipping≤.005 and no observed overlap qualify. These are existing C065/enrollment
quality values, not tuned here. Windows are disjoint over their entire source
span; exact float32 waveform hashes also prevent repeated audio counting twice.
Prepared-file replays additionally bind the file SHA256 and absolute file sample
offsets, so shifted windows cannot recount an earlier promoted source span.
This optional check hashes the bounded file once per bank setup, outside capture.
Different live epochs are distinct acquisitions; this is not acoustic replay
attack detection or a guarantee that two recordings contain different words.
Finite sample-grid timestamps and ≤2s publication/consumer and source-cursor ages
are mandatory. Modeled model-availability time is never substituted for a clock.

Up to 16 session proposals, four confirmed per person, six permanent references
per person; retained permanent transaction history ≤32. No window is inserted
at every overlapping embedding hop. A user confirmation must additionally agree
with the immutable **full** roster's C088 cosine ≥.5128856897354127 and competitor
margin ≥.03. In a one-person gallery the competitor margin is explicitly absent
(comparison uses -1), so this is not independent outsider validation.

The bank uses at most **10%** score weight; at least 90% remains original voice.
It cannot change the original winner or rescue a query lacking the full-roster
base gate. Same-winner scores/margins can rise or fall, so even a correct bank can
reduce coverage. A forced closed-group decision remains an explicit assumption
of that existing mode; it does not certify a reference. Base agreement and user
confirmation are correlated, fallible evidence, not guaranteed identity.

Conflict, overlap/music signals, motion, source/clock failure and domain changes
freeze enrichment. No independent music/noise classifier was added; music
requires the user's Freeze control/quality attestation when existing evidence
does not detect it. Enhancement can disguise overlap; do not confirm mixtures.
Freeze stops bank influence and collection, while ordinary captions continue.

## Storage and compatibility

`adaptation_store.py` extends PersonalStore with `environment_bank` and
`enrichment_history` **inline in person.json**, under the existing 128KiB bound.
Entries include normalized 192D vector/hash, waveform/window hashes, disjoint
support/usable duration, quality, explicit confirmation, base/gallery versions,
domain, clocks and decision/seat provenance. They are private biometric features.
Base `references` and their files are unchanged. Promotion is a single atomic
replace; disk failure leaves the previous person intact. No multi-file partial
bank. Undo removes only entries in its transaction, preserving unrelated data.
Rename retains UUID/version; delete removes the profile and inline bank. Export
includes it; import validates the whole archive before publication, never
overwrites existing UUIDs, and preserves Undo history.

Domain equality includes O0/O1, sample rate, gain, preprocessing, source domain,
beam stream, enhancement model hash AND configuration. Legacy tap references
canonically mean `xvf_O0` / `xvf_O1`. Task10's fixed helper configuration maps to
`dpdfnet-stateful-16k-hop160-v1`; bypass maps to `bypass`. Another beam/config is
not pooled. Full base-gallery version changes disable old bank entries; adding a
new original enrollment or competitor requires fresh collection. Old bank entries
remain visible via saved counts and Undo, rather than silently becoming anchors.

First promotion/import writes required feature `session-reference-enrichment-v1`
to DATA_SCHEMA.json before publishing. Old releases must reject that data. Undo
leaves this conservative reader guard in place. Do not remove it manually to run
an older release. Use current code with matching Off for a safe baseline, or an
isolated/pre-promotion data directory with an older release.

`adaptation_controller.py` keeps commands on the existing owner and consumes
events outside the callback. `adaptation_ui.py` is a touch-only scrollable page
within the existing 480×800 client; no extra live inference. Native CM5 RAM,
ARM64, real-person/XVF performance and participant confirmation remain pending.
See ../docs/UIITER2_11_HANDOFF.md for evidence and source rollback.
