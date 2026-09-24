# Task12 — optional audio-grounded transcript review

Implemented in the existing Windows prototype. **Experimental, default Off;
explicit review/adoption only.** No LLM was installed and no accuracy gain was
demonstrated. The bounded software, native-audio and portrait UI checks passed.
Ordinary live speech, identity, enrollment, spatial modes and prior task11
reference behavior remain intact. This finishes task12 only.

## Launch and controls

PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy'
& .\prototype\Start-Prototype.ps1
```

CMD / Anaconda Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy"
prototype\Start-Prototype.cmd
```

Uses the existing `.edge-speech-env`; no installation or microphone start on
launch. **Settings → Advanced → Audio transcript review → On**, then
**Sessions → Reopen → Review this utterance**. Confirm review of the selected
stored ASR audio (complete utterance ≤20 seconds). Choose a listening output
explicitly and press Listen; review itself never plays audio. Source must have
valid completed audio, original decoder settings and matching model hashes.

Read original and alternate words separately. Removed/added tokens use `−` and
accented `+`; meaning-sensitive changes have warnings. **Adopt as separate user
correction** requires another explicit confirmation that you checked the audio.
Existing **Sessions → Undo correction** reverses it. Cancel or switching Off
retains original words; On resets to Off on restart. A request during capture or
enrollment is deferred. New capture/session/edit cancels pending review.

No Pi toggle is available: Windows AMD64 is the only enabled platform. The
existing task08 export remains usable for its previously qualified scope and
does not contain tasks09–12. No automatic export rebuild, commit or push occurred.

## Finite-candidate contract and implementation

- Original ASR is always retained. The only possible additional candidate is
  a different nonempty output from one unbiased re-decode of the exact archived
  ASR stream, using the recorded effective profile and unchanged pinned assets.
  Installed Sherpa1.13.4 exposes one hypothesis, not N-best; task09 installed no
  CTC worker. A repeated result is correlated agreement, not corroboration.
- At most two candidates. User-authored unlinked task07 vocabulary affects
  display ordering only; it adds no words, model bias, speaker IDs or profiles.
  Original remains first. A disagreement defaults to abstention. Empty/no-support
  output retains the original/uncertainty instead of inventing missing words.
- Candidate selection accepts a bounded JSON object containing only a supplied
  candidate ID or abstain. Extra/duplicate keys, arbitrary words and instructions
  fail validation. Transcript strings are data, with no command/tool execution.
- A saved proposal records original/raw alternative, source samples/audio hash,
  decoder/model binding, caption/revision ID, warnings and resource observations.
  Adoption records a separate correction with review/candidate provenance.
  Raw event journals, final punctuation, speaker labels and profiles are not
  overwritten. Changing source, revision, annotations or capture epoch blocks
  stale adoption. Text export includes audio_reviews.json; full export retains
  linked audio under the existing explicit export-consent workflow.
- One low-priority optional thread, shared recognizer and separate ASR stream;
  no additional capture or USB owner. No new gain, mixing or enhancement. The
  existing .66s decoder flush is explicit, outside the source excerpt/hash and
  never repairs gaps. A currently executing native call may finish after Cancel;
  generation checks discard its result. Limits:20s audio,4000 text characters,
  8s cooperative processing deadline,512MiB available-memory floor,20 retained
  reviews/256KiB per conversation. The model cache intentionally remains loaded;
  copied excerpt and per-review stream are released.

New implementation: app/transcript_review.py (finite candidates/worker),
app/transcript_review_controller.py (source/provenance/commands), and
app/transcript_review_ui.py (separate scrollable review screen). Small integration
changes affect Controller lifecycle, session UI/actions, annotation/export and
the capability manifest. The exact changed files and protected unchanged runtime
hashes are in UIITER2_12_CHECKS.json. Existing recipe/model/capture code was not
replaced. See ../app/README_TRANSCRIPT_REVIEW.md for complete inputs/outputs.

## Actual evidence and limits

| Check | Result and scope |
|---|---|
| Full software suite | **321 pass**,0 failures/errors/skips;35.09s. Includes15 task12 checks for candidate/protection boundaries, timeout/memory failures, cancellation, stale source, provenance, explicit adoption/Undo/export and portrait UI. Synthetic inputs/doubles are disclosed. |
| Native Windows | **7 cases**, five source-paced speech clips plus native silence/three-tone controls; an additional source-paced epoch verifies cancellation by new Start. Public local CMU Arctic awb; no microphone or audible playback. |
| Live priority | Requests during actual source-paced captioning were deferred without stopping it; new Start discarded pending review and completed its source. This is prerecorded/file evidence, not XVF live latency qualification. |
| Actual portrait workflow | **480×800 client pixels**; Off/On, explicit request, protected differences, separate confirmation/adoption and Undo passed. Controller is real; differing words use an explicitly synthetic decoder. Screenshots visually inspected. |
| Lifecycle/failure | Stream released; one shared ASR load, zero speaker/enhancer loads. Software tests cover pressure, timeout, malformed choice, storage failure and stale work. LLM parsing/inference/unload not applicable: none installed. |

The five native speech outputs were identical before and after review:

| Case | Actual observation |
|---|---|
| Unusual proper name | Original/review both “PHILIP STEELES ET CETERA”; reference uses “PHILIP STEELS, ETC”. The simple word metric includes abbreviation/spelling differences. |
| Negation | Both retained “I CANNOT FOLLOW YOU SHE SAID” correctly. |
| Pronoun-containing sentence | Both retained “YOU”, but both produced “AND THE BOUGHS” where reference ends “IN THE BOW”. |
| Number | Both retained “MY AGE IN YEARS IS TWENTY TWO”. |
| Same negation clip at0dB white noise | Both produced “I CANNOT FOLLOW YOU HE SAID”; reference is “SHE”. **Agreement retained a harmful pronoun error.** |
| Silence / simple three-tone control | Empty outputs, abstention; no inserted words. These are labelled control archives, not fabricated ordinary empty captions. |

There were **6 edit errors/39 reference words,15.38% before and after**, zero
automatically adopted edits and no newly introduced errors. This is a tiny
same-speaker fixture set, including a repeated noisy sentence; it does not
estimate field accuracy. No helper suggestions exist to compare. Synthetic
alternatives “we can…15”→“you cannot…50” and “Emir…splork”→“Amir…spark” were
flagged and abstained; prompt-like strings remained plain text. The synthetic
UI test deliberately adopted and undid one candidate to verify the user-control
mechanism, not its truth. Spoken nonwords/confusable names/prompt-like content
and participating human/XVF review remain **AWAITING_USER / NOT_TESTED**.

Native test total:25.53s wall,11.09s process CPU,375.47MiB sampled peak process
RSS. Five speech review workers:0.189–0.289s wall,0.156–0.281s worker CPU,
0.078–0.098MiB sampled incremental RSS between decoder calls. Maximum sampled
UI tick gaps during those reviews:77–88ms, including event processing. The
two-second tone control had0.60MiB sampled incremental RSS. Small RSS differences
are allocator/process dependent; not precise isolated model memory. Original
model loading, startup and shared cache remain separate costs. A cold review or
different archived decoder configuration can load the recognizer. Native tests
used the caption-only fast recipe; they do not qualify combined speaker,
enhancement and helper memory on2GB CM5. Review remains disabled on ARM64.

Initial native attempt exposed unnecessary ASR reloads from default versus
recorded decoder thread settings. The fix reuses archived effective settings
and validates the four ASR model/tokenizer hashes. Accepted evidence verifies
one ASR load. The failed receipt is retained privately, not labelled PASS.

Native evidence binds the exact executable source. Its release-capability file
still had the prior descriptive task-status annotation; finalization verifies
the complete metadata-only change (task12/default-Off/ARM64 pending) against the
checkpoint. No executable/decoder/model/data-feature difference is waived. The
final321-test suite binds the updated manifest; CHECKS records both hashes.

## Dependencies and handoff files

No new package/model/dictionary/tokenizer/conversion. Exact retained model SHA256s,
runtime versions and inherited code/model/data obligations are in
**UIITER2_12_DEPENDENCIES.json**, linked to prior artifact ledgers and
../release_tools/THIRD_PARTY_NOTICES.md. Python3.11.16, Sherpa1.13.4,
ONNX Runtime1.29.0 and the existing frozen models remain in use. Existing licences
and distribution obligations still apply; this is not blanket legal clearance.

The conditional [Qwen3-0.6B](https://huggingface.co/Qwen/Qwen3-0.6B) model card
declares Apache-2.0 and [llama.cpp](https://raw.githubusercontent.com/ggml-org/llama.cpp/master/LICENSE)
declares MIT. No exact checkpoint, converted/quantized derivative or runtime build
was qualified, downloaded or packaged. Two correlated outputs supplied no
demonstrated useful selection role. A future helper requires its own provenance,
isolation/unload, finite-output checks and target resource evidence; parameter
bit size is not total runtime memory. This task does not require deploying it.

Public compact artifacts: UIITER2_12_RESULTS.json (cases/resources/limits),
UIITER2_12_CHECKS.json (exact source/evidence/rollback hashes), the dependency
ledger, updated MODE_GUIDE, ITERATION_PROGRESS and WORKBOOK_UPDATE insertion.
The master Word workbook was not edited. Private recordings/journals/screenshots
remain in `Resumes/.uiiter2_12`; no raw corpus dump is bundled. Test reproduction
commands and fixture inputs/outputs are in ../tools/README_TRANSCRIPT_REVIEW.md
and ../tests/README_TRANSCRIPT_REVIEW.md.

## Rollback

Ordinary rollback is review Off and, if needed, Sessions → Undo correction.
Source/configuration checkpoint before task12 contains287 files and retains
tasks01–11. Close the prototype, then inspect the hash-guarded dry-run:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy'
& .\.edge-speech-env\python.exe Resumes/.uiiter2_12/restore_before_12.py
# Only to perform the reviewed source rollback:
& .\.edge-speech-env\python.exe Resumes/.uiiter2_12/restore_before_12.py --apply
```

CMD / Anaconda Prompt: use the same commands without `&`, after
`cd /d "C:\Users\amiri\Documents\GitHub\just-peachy"`. Optional `--data-root`
selects the lock/schema root; set JUST_PEACHY_DATA consistently before launch.
The tool refuses later source edits, confines restoration/moves to verified
source/backup paths and leaves personal data/models untouched. Only dry-run
was executed. Additive conversation review/correction history remains readable
by task11; no new profile migration was performed. The immutable task08 ZIP at
`G:\Just_Peachy_PROTO1\releases\just-peachy-proto1-0.2.0.zip` retains SHA256
`f29db30c1f05d4ba32cf44f77cdff790fc51d04dc588020401f4c8f912875af4`.
