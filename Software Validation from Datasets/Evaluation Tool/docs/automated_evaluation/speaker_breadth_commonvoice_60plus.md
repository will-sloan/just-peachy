# Common Voice English 60+ speaker-breadth confirmation

## Scientific question

Do the speaker-embedding finalists selected by the original six-model Stage 10 comparison continue to verify, identify, and reject Unknown speakers reliably across a substantially broader population of Common Voice contributors whose self-reported age category is 60 or above?

This is a breadth/generalization confirmation. It is not an enrollment-duration, probe-duration, ASR, diarization, or fine-tuning study.

## Source and 60+ definition

The only source is the locally materialized English portion of Common Voice `cv-corpus-26.0-2026-06-12`, resolved from `JP_DATA_ROOT/Raw Datasets (Not formatted)/Common Voice`. The canonical source table is `validated.tsv`; the existing selective materialization supplies original MP3 files without conversion.

The observed metadata mapping is frozen explicitly in `speaker_breadth_commonvoice_60plus.v1.yaml`. `sixties`, `seventies`, `eighties`, and `nineties` are included; `unspecified`, `teens`, `twenties`, `thirties`, `fourties`, and `fifties` are excluded. These labels remain categorical and must not be presented as independently verified exact ages.

Raw Common Voice `client_id` values are used only inside preparation. Published speakers receive deterministic `spk_cv60p_...` pseudonyms; no reverse mapping is emitted.

## Eligibility and fixed Stage 10 design

Stage 10 Large uses five clean enrollment sources, ten calibration sources, and fifteen evaluation sources per Known speaker: 30 independent clips total. Its Unknown speakers provide 25 sources each. Breadth v1 preserves those minima and the 0.75-second Stage 10 embedding floor.

Every selected contributor supplies a fixed cap equal to the role minimum. This prioritizes independent speaker breadth and prevents prolific contributors from dominating. Within a speaker, selected clips also have unique normalized transcripts. Known speakers are assigned disjoint enrollment, calibration, and evaluation clips. Unknown speakers are never enrolled, and calibration Unknown identities are disjoint from evaluation Unknown identities.

The primary cohort uses every eligible contributor. It does not discard the large `sixties` group to force equal age-category counts. Actual age labels remain joinable by `item_id` in `source_selection.tsv`, supporting all-60+, `sixties`, `seventies`, and—when scientifically defensible—pooled `eighties+` diagnostics.

## Unchanged evaluation methodology

The frozen Parquet files use the existing Stage 10 manifest schema. Finalists use the same source identities, clips, roles, and splits. Each backend performs its own extraction and enrollment in its qualified environment. Existing Stage 10 code performs normalized-mean enrollment, cosine scoring, calibration-only EER threshold selection, verification, closed/open-set identification, Unknown rejection, fixed-FAR diagnostics, failure accounting, and seeded bootstrap intervals.

No evaluation probes influence threshold selection. No embeddings or thresholds are shared between backends.

## Preparation, validation, and execution

`Prepare` audits the pinned local release, deterministically selects the cohort with seed 3800, decodes and hashes every selected source file, writes the protocol to a staging directory, validates it, and atomically freezes it. An existing complete freeze is validated and reused; it is never silently regenerated. A result-affecting change requires a new protocol version.

`Plan` prints cohort and workload counts without loading a model. `Validate` checks frozen checksums, Stage 10 compatibility, path resolution, pseudonym consistency, clip and speaker separation, and transcript-overlap diagnostics. `Run` accepts finalist IDs at runtime, resolves their current Stage 10 environment profiles, runs sequentially, and reuses valid extraction/results. `Status` summarizes progress. `Collect` copies compact analysis evidence and references—rather than duplicates—large observation bundles.

See `app/speaker_breadth/README.md` for complete Anaconda Prompt and PowerShell commands, inputs, and outputs.

## Leakage contract

Preparation fails unless source audio is unique across roles, item IDs are unique, Known and Unknown speakers are disjoint, Unknown speakers are absent from enrollment, calibration/evaluation Unknown identities are disjoint, published speaker-to-age mappings are consistent, and all selected paths exist. Same-speaker transcript overlap across splits is zero by construction. Global sentence reuse by different contributors is reported as a diagnostic and is not identity leakage.

## Metadata and duration diagnostics

Age, gender, accent, variant, and locale are retained as diagnostic covariates. Coverage and missingness are reported at clip and speaker levels. They are self-reported and are not selection claims about representativeness. Original clip durations, per-split durations, per-speaker speech totals, unusually long clips, and below-minimum counts are frozen alongside the manifests.

## Limitations

1. Common Voice age categories are self-reported and are not verified chronological ages.
2. Recording conditions, microphones, acoustics, and speech style vary substantially.
3. Contributors are not necessarily representative of the intended production population.
4. Gender, accent, and variant metadata may be missing, sparse, or inconsistently categorical.
5. This confirmation does not replace later target-device or XVF3800 testing.
6. It measures speaker recognition, not diarization.
7. It neither optimizes nor compares enrollment amount, aggregation, probe duration, or speech type.
8. Tiny age groups cannot support strong inferential subgroup claims; they remain visible for descriptive diagnostics.
