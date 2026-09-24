# Optional audio-grounded transcript review — task12

Purpose: inspect a bounded, explicitly selected recorded utterance with the
existing ASR, compare its original words with one unbiased re-decode, and adopt
only a consciously approved correction. This is a Windows desktop developer
feature. Default Off. No LLM, cloud, new model, N-best list, phonetic scoring,
speaker inference, free reconstruction or vocabulary-generated candidate words.

## Launch and use

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

Uses the existing pinned `.edge-speech-env`; no pip/conda install needed.

1. Settings → Advanced → Audio transcript review → On. This does not capture or
   analyze anything automatically. On/Off is reset to Off after app restart.
2. Sessions → open/reopen an existing conversation with consented stored audio.
   Choose **Review this utterance**, then **Review selected recorded utterance**.
   Explicitly confirm local review. Complete utterance must be ≤20s; longer,
   text-only, partial/gapped, missing-profile or mismatched-model data abstains.
3. Read original and alternative separately. Removed tokens have a `−` marker;
   inserted/replacement tokens have an accented `+` marker. Names, pronouns,
   negation, amounts/times and unusual/unknown words get explicit warnings.
4. Choose a listening output explicitly, then press Listen. Output selection
   never changes default Windows speakers. Return via Advanced or the same
   utterance after output selection. Playback is always an explicit action.
5. **Adopt as separate user correction** requires an additional confirmation
   that you checked the changes against audio. Original raw/final ASR is retained.
   Undo is the existing Sessions → Undo correction. Cancel keeps original words.

Live capture/enrollment has priority: a review request while live is deferred
without stopping captions. New capture/enrollment or changing/opening/deleting
the session/correction cancels pending review. A different source, ASR revision,
audio hash, annotation state or capture epoch blocks stale adoption. No result
is published into ordinary captions automatically. Existing task07 explicit text
assistance remains separate, as do task11 reference banks and all speaker labels.

## Inputs, outputs and finite-candidate contract

`transcript_review.py`: maximum two candidates—immutable original ASR plus a
different nonempty fresh greedy output from the exact archived **ASR** stream.
The installed Sherpa1.13.4 API exports one result; this is not N-best. Task09
added no CTC worker. Neither forced alignment nor language plausibility proves
speech. No missing words are filled when the decoder supplies none.

Original model/tokenizer hashes and the archived effective decoder profile must
match. Review reuses `ResidentModels` and creates one separate stream. No new
recognizer per utterance and no second microphone/USB owner. It applies no new
gain, denoising or channel mix. The existing decoder's .66s final flush is marked
as decoder padding, outside the source excerpt/hash; it never repairs real gaps.

Only explicitly authored, **unlinked** task07 vocabulary text/kind enters the
display ranking. It never biases decoding, generates a replacement or receives
speaker-profile UUIDs/vectors. Original ranks first; a changed alternative is
offered with abstention, never an automatic winner. Matching strings mean only
that this same model agreed with itself, not independent acoustic confirmation.
`validate_choice` accepts exactly one JSON key, `candidate_id`, with a supplied
ID or `abstain`; duplicate keys, extra instructions, text and unknown IDs fail.
Spoken prompt-like content is plain text; no tools or commands are exposed.

`transcript_review_controller.py`: validates selected source and archive, owns
commands, receives generation-fenced results, stores them separately and uses
the existing user-correction/Undo path after explicit approval. `transcript_review_ui.py`
adds a scrollable touch-only review page; ordinary portrait captions retain their
space. No third-party grammar/frequency dictionary or similarity library added.

## Resources, cancellation and privacy

One optional background worker; Windows below-normal thread priority, 20s source
cap, 8s processing deadline and 512MiB available-memory floor. It checks between
native decoder calls. Cancel/new Start does not wait for the result; a currently
executing native call completes, then the worker discards stale work and releases
its stream. This is cooperative cancellation, not hard preemption of a broken
native library. No optional result can gate raw caption publication. Requests
are rejected while a previous worker is still releasing its stream.

The existing recognizer remains in the shared model cache, intentionally; an
LLM is not loaded. No language-model unload claim is applicable. Worker streams
and copied excerpt buffers are released after a job. Memory/CPU/UI measurements
and actual reuse counts are in ../docs/UIITER2_12_RESULTS.json. Incremental RSS
is process-wide, allocator-sensitive and not a CM5 qualification. ARM64/CM5 is
explicitly disabled until native combined-memory/latency measurements succeed.

Inputs are private local recorded speech and original ASR, plus the small
explicit vocabulary above. Results are `audio_reviews` inside conversation.json,
bounded at 20 reviews and 256KiB total. They retain raw alternatives, exact source
link/hash, decoder binding, decision, warnings and measured costs. Audio is not
duplicated; its original archive is retained. Adoption adds a separate correction
linked to review/candidate IDs; raw events, punctuation and enrollment do not
change. Text export includes audio_reviews.json; full export includes ordinary
audio/evidence. Both require existing explicit privacy confirmation. Delete the
conversation to delete its review evidence. No unattended recording mining.

Schema remains an additive conversation-v1 extension. Existing readers preserve
unknown conversation fields and can display separate corrections. No personal
profile schema migration. Source rollback leaves reviews/corrections as history;
Off or Undo is the ordinary rollback. See the task12 handoff for hash-guarded
source rollback, retained licences and pending real-person checks.

Qwen3-0.6B/llama.cpp was considered as the prompt's conditional helper, but no
useful selection role was demonstrated and no derivative was qualified,
downloaded, installed or packaged. A future helper would require the exact
official revision, converter/quantization/runtime hashes and licences, bounded
ID-only output, isolation/unload and target measurements. Do not imply that a
nominal four-bit parameter size is total runtime RAM.
