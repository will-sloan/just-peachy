# Speaker Enrollment and Recognition Contract

Stage 10 derives a new protocol layer from the frozen Stage 2 `speaker_protocol.parquet`; it does not change the Stage 2 schema or row selection.

## Split rules

- Enrollment is clean and source-disjoint from every probe.
- Known speakers are present in enrollment, calibration, and evaluation, but their source utterances are disjoint across those splits.
- Unknown speakers are never enrolled. Unknown calibration speakers and unknown evaluation speakers are also disjoint.
- Clean and degraded variants of one source utterance always remain in the same split.
- Speaker labels are deterministic `spk_<hash>` pseudonyms. Shared manifests contain no source speaker ID, display name, or real-name mapping.
- Only `gender` and `accent_group`, inherited from authorized normalized metadata, are available for subgroup reporting.

## Enrollment identity

An enrollment is valid only for the exact embedding backend, model identity and asset hash, component-config hash, vector dimension, L2 normalization, preprocessing policy, centroid aggregation method, and threshold-policy version recorded in its metadata. Any mismatch is terminal; vectors are never converted or borrowed from another backend.

## Calibration and scoring

Every calibration and evaluation embedding is scored against every available enrolled centroid using cosine similarity. The operating threshold is selected at the calibration equal-error operating point. Evaluation probes do not influence that threshold.

Evaluation produces pairwise verification decisions, top-k rankings, and open-set decisions. A best score below the threshold maps to the literal `Unknown`. A failed probe also emits `Unknown`, but its status remains `failed` and it does not receive credit as a correct unknown rejection.

Reported metrics include score distributions, EER, FAR/FRR, TAR at fixed FAR, ROC/DET points, top-1/top-k identification, unknown rejection, false-known assignment, extraction and enrollment failures, clean-to-degraded drift, per-speaker/per-condition/authorized-subgroup results, counts, and 95% confidence intervals. Closed-set and open-set metrics remain separate.

## Privacy and exchange

Vectors and score tables are biometric-sensitive. Exchange uses JSON, Parquet, and NPZ with `allow_pickle=False`. SHA-256 protects all result artifacts. Credential values, private identity mappings, null labels, empty labels, and reference-derived predictions are forbidden.
