# S5 text, overlap and final-label scoring

`s5_text_metrics.py` scores already completed development predictions. It never runs H2, opens audio, changes gains, controls hardware, or scores reserve scenes. `test_s5_text_metrics.py` exercises the actual pinned multi-talker backend and failure boundaries.

## Inputs and API

Use the frozen canonical S4.5 development scene dictionary and a verified native H2 metrics dictionary, native event list, or both. The main S5 scorer owns receipt/hash validation and calls its `DevelopmentGuard.require` before opening task inputs. The adapter independently checks the allowlist, `split == development`, and `task_scoring_allowed is True` before reading task structures. A failed/missing completion is an unavailable job, never an empty transcript.

```python
from s5_text_metrics import score_scene, score_scene_files

result = score_scene(
    scene, native_metrics=metrics, events=events,  # events optional
    development_ids=guard.allowed,
)
# Or let this wrapper guard BEFORE opening either task input:
result = score_scene_files(
    scene, development_ids=guard.allowed,
    metrics_path=verified_metrics_path, events_path=verified_events_path,
)
```

`native_metrics` requires `state: COMPLETED`, `final_transcripts`, and native `telemetry.source_duration_sec` (historical `text.duration_s` is a fallback). Each final row has `utterance_index`, raw `text`, and the actually emitted `speaker`. Duplicate final indices fail closed because no reconciliation export exists. If both metrics and events are supplied, the final rows must match exactly. Event-only calls require `duration_s` explicitly; do not substitute nominal scene duration. An explicit duration must agree with a supplied native duration.

Pure results use `schema: jp_s5_text_metrics_v1`, `case_id`, `population`, `text`, `overlap_mimo`, `attributed_cpwer`, reference/utterance counts, decoded duration, hypothesis-empty and reserve flags. Populations are `PRIMARY_NONOVERLAP`, `COMPLETE_OVERLAP`, `INCOMPLETE_REFERENCE`, `STRICT_EMPTY_REFERENCE`; the canonical metadata reconciles to 117/36/19/8. `text` preserves S4 fields and exact edit tie-breaking. Multi-talker results expose `word_counts` (S/D/I, errors, reference/hypothesis words), `wer`, assignment, implementation/version, status and scope; cpWER also exposes missing/extra/reference/hypothesis stream counts and actual labels. JSON serialization turns tuple assignments into arrays. Ratios must be pooled from summed errors and reference counts, not averaged as pooled WER.

## Frozen scientific definitions

Normalization reuses `s4_h2_analysis.normalize` and the unchanged H2 `app/scoring/wer.py`: lowercase; remove ASCII `string.punctuation`; collapse whitespace; no number or contraction expansion. CER removes spaces from that normalized text. ONLY raw final ASR `text` is scored. Punctuated `display_text` is ignored.

Reference utterances are the original `kind: utterance` segments, stably ordered by source start, grouped by pseudonymous `speaker_key`. Missing text/identity makes the reference incomplete. Repeated utterances remain repeated. Ordinary WER includes all speakers and is unavailable for scheduled or file-support overlap. Strict empty controls report inserted words and words per **native decoded minute**; WER/CER are undefined. Source documentation such as instrumental `vocals=N` is not new frame-level listening certification.

The [official MeetEval repository](https://github.com/fgnt/meeteval) distinguishes the metrics. The installed, hash-bound 0.4.3 source is authoritative for this run:

- `meeteval.wer.wer.mimo.mimo_word_error_rate({speaker: [utterance, ...]}, {'ONE_OUTPUT': raw_final_text}, reference_sort=False, hypothesis_sort=False)`. Each speaker's utterance order and boundaries remain fixed. Inter-speaker utterance serializations can change; words within an utterance cannot be arbitrarily shuffled. O0/O1 are scored separately, each as ONE hypothesis stream. [Official MIMO implementation](https://github.com/fgnt/meeteval/blob/main/meeteval/wer/wer/mimo.py). This untimed diagnostic is not exact overlap recall, source separation, or word latency. Whole-file utterance boundaries constrain permitted serialization; phonetic word times are absent.
- `meeteval.wer.wer.cp.cp_word_error_rate({speaker: concatenated_reference}, {actual_final_label: concatenated_raw_finals}, reference_sort=False, hypothesis_sort=False)`. One global Hungarian assignment is used per scene, with unmatched streams retained. Actual emitted labels are grouped without truth-based renaming or reconciliation. [Official cpWER implementation](https://github.com/fgnt/meeteval/blob/main/meeteval/wer/wer/cp.py). This measures final-snapshot attributed transcript quality; values above 100% are possible. No DER, enrolled identity or post-merge lineage claim follows.

Incomplete ambient references leave all-speaker text, MIMO and cpWER unavailable. When annotated targets exist, `target_only_text` is explicitly `LIMITED_TARGET_REFERENCE_ONLY`: the whole mixed-output transcript is compared with targets, so unknown ambient speech can contribute insertions. It is not excerpt-aligned, not proven false speech, and never enters primary WER. Missing actual emitted labels limit cpWER while preserving ordinary text. A missing MeetEval installation yields explicit LIMITED diagnostics; an unexpected installed version fails closed.

## Environment and setup

Use this analysis interpreter, **not** the working H2 environment:

`C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\staging\s5_text_metrics\analysis_env\Scripts\python.exe`

This isolated venv inherits Anaconda's existing NumPy 1.26.4, SciPy 1.13.1 and packaging 24.1 through `--system-site-packages`; it does not modify them. Only MeetEval 0.4.3, Cython 3.0.12 and kaldialign 0.12.0 were added locally. MeetEval's official 843,558-byte sdist is saved and SHA-verified against PyPI. No audio/model downloads occurred. Initial build failed because an included time-constrained extension needs C++20 on MSVC. A command-local compiler flag fixed the build without changing upstream source. Both installation logs remain local. Initial package resolution also found that guessed kaldialign 0.11.2 does not exist; nothing installed on that failed resolution, and the actual pinned installation is 0.12.0.

To recreate only if needed, in **Anaconda Prompt / CMD**:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\staging\s5_text_metrics"
"C:\Users\amiri\anaconda3\python.exe" -m venv --system-site-packages analysis_env
analysis_env\Scripts\python.exe -m pip install Cython==3.0.12 kaldialign==0.12.0
set "CL=/std:c++20"
analysis_env\Scripts\python.exe -m pip install --no-build-isolation meeteval-0.4.3.tar.gz
set "CL="
```

In **PowerShell**, from the same directory, use `$env:CL='/std:c++20'` before the last installation and `Remove-Item Env:CL` afterward. The downloaded source, installed module identities, versions and build logs are recorded in `staging/s5_text_metrics/DEPENDENCY_RECEIPT.json`; no runtime backend code was patched. This local analysis build requires the already installed Visual Studio C++ toolchain.

## Run tests and historical regression

In **PowerShell**:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
$env:PYTHONDONTWRITEBYTECODE='1'
& '..\staging\s5_text_metrics\analysis_env\Scripts\python.exe' -m unittest -v test_s5_text_metrics
& '..\staging\s5_text_metrics\analysis_env\Scripts\python.exe' s5_text_metrics.py --regression-s45 --output '..\reports\S5\20260909T130308Z\S45_TEXT_REGRESSION.json'
```

In **Anaconda Prompt / CMD**:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
set PYTHONDONTWRITEBYTECODE=1
..\staging\s5_text_metrics\analysis_env\Scripts\python.exe -m unittest -v test_s5_text_metrics
..\staging\s5_text_metrics\analysis_env\Scripts\python.exe s5_text_metrics.py --regression-s45 --output ..\reports\S5\20260909T130308Z\S45_TEXT_REGRESSION.json
```

The regression reads only the 24 previously inspected development sentinels, binds their 48 COMPLETE receipts and metrics, and requires exact equality of saved WER/CER, S/D/I, both denominators, empty-control and LIMITED dispositions. It does **not** compute new overlap/cpWER comparisons (`include_multitalker=False`). Observed PASS: O0 47/480 word errors (38S/5D/4I), O1 41/480 (30S/7D/4I); character errors 100/2137 and 89/2137. These are historical sentinel counts, not the 180-scene S5 outcome.

Twenty deterministic fixtures passed against the real backend: perfect raw text, normalization, edits, empty output/control, missing references, ambient limitations, either overlap order, missing/duplicated talkers, no word shuffle, preserved within-speaker order and repeated references, global label assignment, changed returning label, >100% cpWER, missing labels, duplicate finals, failed models, reserve-before-open refusal, native mismatch, unavailable backend and decoded-duration handling. `TEST_OUTPUT.txt` and `TEST_RECEIPT.json` preserve exact output and code/test/README bindings. Full S5 comparison is run only by the root coordinator after protocol freeze; this module has no full-panel CLI.
