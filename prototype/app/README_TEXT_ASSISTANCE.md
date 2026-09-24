# Conservative text assistance (task 07)

Purpose: `text_assistance.py` supplies bounded spelling suggestions and explicitly
approved contextual spelling rules. `text_assistance_ui.py` supplies touch entry
and review. Controller/UI/session adapters preserve distinct raw, provisional,
learned final, optional assisted and manual layers. This does not improve acoustic
recognition or use a speaker identity as evidence for spoken content.

## Launch / inputs / outputs

From the repository root in PowerShell:

```powershell
& .\prototype\Start-Prototype.ps1
```

CMD / Anaconda Prompt:

```bat
prototype\Start-Prototype.cmd
```

Open **Settings → Text assistance / vocabulary**. Both switches default Off:

- **Suggestions** enables possible spelling/contextual-name suggestions on
  future final text. Generic spelling is always review-only.
- **Approved automatic rules** additionally permits rules that you individually
  approved as automatic and whose independent context matches. ✎ marks assisted
  caption text. Either switch Off restores the original formatted display.
- **Add word / spelling preference** supports name, context-word or spelling
  entries. **Approve an enrolled name** explicitly links a preference to that
  UUID. No profile is added automatically to the correction vocabulary.
- Preferred spelling is required; alias and context are optional for review.
  Automatic rules require both alias and independent context. The approval
  screen is explicit; no automatic rule is shipped.
- **Review recent final text** shows the latest eight raw/final/assisted/manual
  layers, suggestions and source links. Stop/drain before manual editing. Edit
  opens the touch keyboard. **Sessions** contains the complete archive and
  separate manual correction/undo history (latest 20 annotations in its UI).
  Manual edits are displayed in review/session annotations, not resegmented into
  speaker-owned caption tokens. Exports retain the complete manual log.

Inputs are final punctuated text, user-approved preferences, and the list of
profiles solely for rename/deletion/collision checks. There is no current-speaker
input, audio processing, model call or return path into identity. Rules never
feed enrollment ASR. People, audio-tap, recipe and spatial settings are separate.

Outputs: private `text_assistance.json` under the existing data root; reversible
assistance records in append-only `prototype_formatted_text` journal events;
source caption/revision/epoch/sample bounds; and separate manual edits/undo in
conversation metadata. Raw `s6d_display` events remain unchanged. Text-only exports
include assistance and user annotations; exact audio remains opt-in under the
existing retention policy. These files can contain private names/text.

## Conservative behavior and bounds

- 24 original project vocabulary words; no imported dictionary/frequency corpus.
  Personal vocabulary: 64 approved entries, each 1–4 words / at most 80 characters.
  Mappings must preserve word count so speaker segment ranges remain meaningful.
- Simple spelling uses a single insertion, deletion or substitution against the
  small vocabulary, for 5–24-character words. Names are excluded from generic
  fuzzy candidates. It says **possible spelling**, not “definitely a nonword”;
  a legitimate uncommon word may get a suggestion. No string score is labelled
  acoustic or speaker confidence.
- Exact case-insensitive whole-word/phrase aliases preserve surrounding text
  and punctuation, using the approved target spelling. Substrings, possessives
  and hyphen compounds do not match a name alias. Independent contextual phrase
  matching is required for automatic edits; overlapping/conflicting rules remain
  review-only. An enrolled other person matching the alias blocks automatic use.
- Negation, pronouns, numeric digits/common number words, a conservative list of
  safety/medical/financial terms, email/URL/code markers block automatic edits
  for the utterance. Protected alias/target words also block auto. These lexical
  guards are not a general semantic safety detector. Defaults stay off; high-risk
  content belongs in human review, and explicit rules can still be mistaken.
- Amir/Emir has no built-in replacement. A title, different person, omitted
  context or a protected utterance stays unchanged. Linked profile rename/delete
  disables that entry until a new approval; it never silently retargets an alias.
- At most 4000 characters / 128 words and 16 suggestions per analyzed final;
  larger text stays unchanged. Cache: 512 text/config/profile-state entries. UI
  refresh does not rerun analysis. No dictionary work occurs in the audio callback.
- Raw text is published to the GUI before optional processing. Text-assistance
  failures are marked unavailable and cannot stop recognition. Computation uses
  existing standard-library functionality and bounded character comparisons.
- Assistance preference changes affect future finals, not old journal entries.
  Turning display assistance Off is reversible. Stored history still records
  exactly what was proposed/applied; removal of a rule hides its old automatic
  display, and source text is always retained.
- No missing words are generated, no noisy/silent classification is invented,
  and no calibrated token confidence is claimed. Task02 smoothing remains only
  presentation timing. No script aligner, transcript LLM or training is added.

## Experimental enrolled-name bias: unavailable

Installed Sherpa-ONNX **1.13.4** exposes `hotwords_file`, `hotwords_score`,
`modeling_unit`, `bpe_vocab` and per-stream hotwords. Its implementation and the
[official hotwords documentation](https://k2-fsa.github.io/sherpa/onnx/hotwords/index.html)
require modified beam search. The qualified Giga assets have BPE-style tokens
but no matching ASR BPE vocabulary/provenance binding; the existing `bpe.vocab`
belongs to punctuation. Substituting it would not be valid ASR tokenization.

The disabled UI explains this. No hotword file, boost, decoder switch, download
or acoustic A/B is claimed. The actual greedy baseline and exact assets stay
unchanged. A later separately validated tokenizer/beam change would need its own
small native name/context/no-name/silence/music A/B and latency/false-insertion
results before this feature could be enabled.

See `../docs/UIITER2_07_DEPENDENCIES.json` and existing third-party notices for
provenance. SymSpellPy and RapidFuzz MIT source licences were reviewed as
references; neither package, its transitives nor a dictionary was installed.
Original project source keeps existing rights; no new blanket distribution
licence is asserted. Native/check commands are in the tests/tools READMEs.
