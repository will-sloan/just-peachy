# Task 07 — Conservative names, vocabulary and text assistance

Implemented locally on 20 September 2026, preserving tasks 01–06. **253 software
checks PASS**, plus the bounded native caption/archive check. No new package,
model, dictionary, training, broad sweep, microphone recording, playback,
production-profile mutation, automatic commit/push or release rebuild. Task08
has not started. Human field use, physical touch and CM5 remain **NOT_TESTED**.

## Launch and controls

From `C:\Users\amiri\Documents\GitHub\just-peachy`, PowerShell:

```powershell
& .\prototype\Start-Prototype.ps1
```

CMD / Anaconda Prompt:

```bat
prototype\Start-Prototype.cmd
```

Open **Settings → Text assistance / vocabulary**. Suggestions and Approved
automatic rules both default Off. Generic spelling is review-only. Add a word,
spelling preference or explicitly approved enrolled name using the touch
keyboard. Automatic rules additionally require an exact alias, independent
context phrase and individual approval. Preferences are local, outside releases.

✎ marks assisted caption text; either switch Off restores original formatting.
**Review recent final text** shows raw/final/assisted/manual layers and source
links for eight recent finals. Stop/drain, then edit a caption with the keyboard.
Sessions retains the full journal and manual correction/Undo history. Manual
edits stay in labelled review/annotations, not new speaker-owned tokens. Export
retains every correction and undo; the UI lists the latest 20 annotations.

**Bias enrolled names is unavailable.** Installed Sherpa 1.13.4 exposes the API,
but qualified Giga ASR assets lack a matching bound BPE vocabulary. The available
BPE vocabulary belongs to punctuation. Upstream requires modified beam search
and correct tokenization; using that unrelated vocabulary or a file ignored by
greedy would not implement bias. No boost, decoder switch or name/silence/music
acoustic A/B is claimed. Greedy baseline and model hashes remain unchanged.

## Implementation and safeguards

- New `app/text_assistance.py` and touch `text_assistance_ui.py`; controller,
  caption UI and session adapters connect them to existing final text. Raw
  captions are published before optional assistance. Errors leave baseline
  captioning available. Corrupt preference files are preserved and disabled,
  with a visible repair message instead of blocking app startup.
- 24 original vocabulary words; no external dictionary. Up to 64 approved
  personal entries, 1–4 words / 80 characters each. Mappings keep word count.
  Generic candidates use one character edit and are never automatically applied.
  Up to 16 suggestions, 128 words / 4000 characters per final, 512 cached results.
- Exact contextual rules preserve punctuation and surrounding words. There is
  no universal Amir→Emir or Emir→Amir substitution. A different enrolled Emir,
  conflicting rules, substrings, possessives and hyphen compounds prevent an
  automatic mapping. Profile rename/delete disables linked entries until newly
  approved; old assisted display is hidden when its rule is removed/inactive.
- Negation, pronouns, numerals/common number words, listed safety/medical/
  financial terms and email/URL/code markers block automatic edits. These are
  conservative lexical guards, not a complete semantic safety model. Defaults
  stay Off; deliberate rules can still be wrong and should be reviewed in use.
- No current-speaker input enters this feature, and no text result returns to
  speaker identity/enrollment. S6/S7 recipes, O0/O1 routing, spatial modes, audio
  windows, live timing, models and task06 enrollment remain unchanged.
- Append-only formatted journal records preserve raw/final input, optional
  correction, before/after spans, rule/config revision and caption/epoch/sample
  links. Manual edits/undo are separate metadata. Original journals do not change
  after a manual edit or undo. Index recovery and export preserve the layers.
- No generated missing words, invented acoustic confidence or noisy/silence
  classification. Task02 smoothing still only affects display timing.

## Examples and verification

| Evidence | Before / proposed result | Actual behavior |
|---|---|---|
| Genuine 12s CMU audio, actual controller/decoder | Raw contains `CAPTAIN COOK`; learned final already has `Captain Cook` | Assistance leaves it unchanged. This existing casing is not a task07 accuracy gain. Full private example retained locally. |
| Original text fixture | `camptions` → suggestion `captions` | Display unchanged; review only. |
| Approved contextual text fixture | `Emir joined Peachy.` → `Amir joined Peachy.` | Only with exact approved alias, matching context, per-rule approval and both switches On. |
| Title / substring / another Emir | `The emir spoke.`, `Peachy emirates.`, enrolled Emir present | No automatic edit. |
| Protected text fixtures | `Emir did not join Peachy.`, `He called Emir at Peachy.`, numeric/insulin cases | No automatic edit. |

The 253-test complete regression passed in **26.568s**, including the previous
enrollment, timing, cleanup, people, seats, captions and session checks. Eleven
new tests cover text behavior, corrupt optional preferences, reversible journal
layers and actual Tk controls. Three explicit-stub screenshots were inspected
at 480×800; this does not validate physical touch or recognition accuracy.

Final native timing/resource values and exact source/API/model bindings are in
`UIITER2_07_CHECKS.json`. One real native 12s caption-only session exercises
ordinary greedy ASR, learned punctuation, assistance, source links, saved-session
reopening, manual correction/undo and original-journal preservation. A separate
nine-case original text set covers the positive/negative rules; it is not an
acoustic benchmark. No unwanted native edit or protected-fixture automatic edit
was observed. This small set does not estimate general false-correction rates.

Final native check: **14.070s wall, 2.922 CPU-seconds, 359.93 MiB peak process
working set** on this Windows desktop. Its final text-assistance call took
**0.717ms**, with one ASR model load and no speaker model needed in caption-only
mode. These process measurements include model loading, paced audio, archive and
hash checks; they are not additional assistance RAM or a CM5 throughput claim.

Private receipts/examples are `Resumes\.uiiter2_07\native_final_v3`,
`unit_final_v3` and `ui_final`. Small UI evidence is copied to
`docs/evidence/uiiter2_07`. Read `app/README_TEXT_ASSISTANCE.md` and the tests/tools
READMEs for complete bounds, inputs, outputs and exact rerun commands.

## Dependencies and rollback

No dependency or transitive dependency was added. SymSpellPy/RapidFuzz MIT code
licences were reviewed as references only; no associated dictionary rights were
assumed. The vocabulary is original project text. Exact bindings and references
are in `UIITER2_07_DEPENDENCIES.json`; existing obligations remain in
`release_tools/THIRD_PARTY_NOTICES.md`. No blanket model/data redistribution
clearance or new project licence is asserted.

Close the GUI. PowerShell from repo root:

```powershell
# Dry-run first; validates the baseline ZIP and current file hashes.
& .\.edge-speech-env\python.exe -B Resumes/.uiiter2_07/restore_before_07.py
# Only for a deliberate task07 rollback:
& .\.edge-speech-env\python.exe -B Resumes/.uiiter2_07/restore_before_07.py --apply
```

CMD / Anaconda Prompt uses the same commands without `&`, with
`.edge-speech-env\python.exe`. The bound `prototype_before_07.zip` preserves all
local tasks 01–06, not just Git HEAD. The helper refuses later edits, restores
changed baseline files, and moves only new task07 Python files to its private
rollback backup. New docs/evidence remain historical. People, settings, recordings,
models and the Git index are untouched. Older code ignores vocabulary/assistance
fields and does not understand the new manual-undo presentation; consult the
retained correction log with task07 code if needed.
