# Product Improvement Roadmap

## Safe improvements applied immediately

### Readable transcription and learned punctuation

Sherpa's raw uppercase hypothesis remains unchanged in `events.jsonl` and the `text` field. The GUI and readable transcript use a separate `display_text` field. Final utterances now pass through the Apache-2.0 Edge-Punct-Casing CNN-BiLSTM INT8 ONNX graph supplied by Sherpa. This provides learned casing, periods, and question marks without changing ASR decoding. A terminal period remains only as a visible fallback when a short endpoint receives no terminal punctuation.

### Honest overlap behavior

The Pyannote overlap result now propagates into transcript events. During detected overlap, the GUI displays `Overlap detected — attribution is uncertain`, and the transcript label names the prior speaker plus an unspecified overlapping speaker. It does not duplicate the same words under two names or claim to know which person said which word.

A true word-level split cannot be implemented honestly in the UI alone. The current system has one microphone mixture and one ASR stream. It would require source separation or multi-speaker ASR, followed by speaker attribution. XVF angle and energy can improve attribution and tracking, but they do not automatically unmix two simultaneous voices.

## Enrolled-name audit

The recent local session `edge_microphone_20260901T184033Z_cb0fafa8` proves that the transcript can display the enrolled name `AMIR Test`:

- 16 transcript events used the confirmed name;
- 2 transcript events used the tentative name;
- 13 transcript events used anonymous labels;
- 28 speaker decisions were confirmed, 2 tentative, and 27 anonymous;
- confirmed profile scores ranged from 0.5786 to 0.7256.

The anonymous switches are caused by anonymous-cluster fragmentation and short-window variation, not a missing GUI connection. Some 0.5-second windows matched the enrolled profile strongly while other clusters scored near 0.20. Lowering the identity threshold alone would not repair those clusters and could create stranger-to-known errors.

## Low-risk operational improvements available now

- Enroll from several clean samples covering normal speaking distance, volume, and head direction.
- Avoid enrollment clips containing another person, television, or overlap.
- Keep raw scores, margin, evidence, cluster identity, and overlap visible in research view while keeping the user view simple.
- Preserve every manual selection/correction as an audit event rather than silently rewriting model output.

## Useful features that require a controlled product mode

### Select who is at the table

An active-roster selector is technically straightforward and likely useful for long dinners. It would restrict name matching to selected profiles while retaining anonymous labels for everyone else. However, changing roster size changes the open-set search problem and Top-1/Top-2 margin behavior. It should therefore be a named, logged mode with roster-size calibration rather than an untracked UI filter.

### Correct the current speaker

A correction control could map an anonymous cluster to an enrolled person for the remainder of a session. The safe design is an explicit `manual_override` event with undo, timestamp, cluster ID, operator identity, and scope. Manual corrections should not automatically retrain the embedding model; saved corrections can later become reviewed training/evaluation data.

### Identity stability

Before fine-tuning a neural model, evaluate policy changes using preserved embeddings:

- 0.5, 1.0, and 1.5-second embedding windows;
- accumulated versus recent-window identity evidence;
- cluster-centroid smoothing and bounded cluster merging;
- confirmed-name hysteresis and short-gap reacquisition;
- roster-aware thresholds and margins;
- XVF energy/AoA-assisted association.

These are decision-layer experiments and can often be replayed much faster than model inference.

## ASR vocabulary and punctuation

The current Sherpa Giga model has a fixed 502-token subword inventory. New ordinary words are usually representable as combinations of existing subword pieces, so adding a restaurant name or person's name does not necessarily require changing the neural vocabulary.

The installed Sherpa ONNX 1.13.4 runtime exposes hotword biasing through `hotwords_file` and `hotwords_score`, but only with `modified_beam_search`. The current pipeline uses frozen `greedy_search`. A domain-vocabulary mode is feasible, but it requires:

1. deterministic tokenization of each phrase into the model's existing pieces;
2. a switch to modified beam search;
3. development tuning of hotword score and active paths;
4. held-out WER, false-insertion, latency, and Pi resource checks;
5. a frozen separate preset rather than silently changing the baseline.

This biases names and domain terms; it does not truly expand the neural output vocabulary. A genuinely new token inventory would require ASR model retraining/export and is not presently justified.

The small Sherpa online punctuation model is now integrated for final utterances and exported in the Pi bundle. It is intentionally excluded from unstable partials to avoid punctuation churn. Actual Raspberry Pi ARM64 latency and sustained resource cost remain qualification measurements rather than assumed results.

## Recommended sequencing

1. Keep the current audio-only pipeline as the reproducible baseline.
2. Collect real dinner/table sessions and annotate overlap, speaker changes, names, and corrections.
3. Add roster selection and manual correction as separately logged modes.
4. Run policy replay for embedding windows, evidence accumulation, hysteresis, and cluster merging.
5. Add XVF raw energy/AoA events and perform audio-only versus spatial ablations.
6. Add a hotword challenger preset if the product vocabulary requires it; retain the learned-punctuation stage as the default presentation path.
7. Fine-tune embeddings or ASR only when the frozen error analysis shows that policy and spatial evidence are insufficient.
