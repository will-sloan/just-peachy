# Independent full N03 component review V1

Purpose: check completed N03 (C067) native-derived scoring and nine explicit comparisons against their exact compact CSV/JSON buffers. This source performs no scoring, replay, bootstrap regeneration, native-log read, audio/model read or inference. It never modifies held scorer, summary, runtime or prediction sources.

## Inputs

The script pins the full N03 core receipt, its nine-comparison receipt and the design owner's completed exact-table summary. It follows their byte/length/SHA-256 bindings to the N03 scene/turn/profile/short/lifecycle/cost tables, selected comparison scene/pair/uncertainty tables, C065 parent turn/profile/short/lifecycle tables, and original480-view input metadata. It parses the same buffers whose hashes it checks. It does not follow metadata paths to audio, model weights, native logs or predictions. The fixed source receipts are under `reports/S6C/20260910T123540Z`.

Checks independently reconcile the480 C067 outputs and all240 cases on each registered same-tap route; population-specific source lengths, word counts,693 complete versus84 incomplete turns and292 complete versus32 incomplete returns; all C065/C067 profile groups; short-turn evidence and mapping counts; observed-only wait quantiles and missing counts; all126 point rows for nine comparisons; room denominators and right-minus-left direction; and the admitted bootstrap's observed primary-word points and included population. Bootstrap percentile intervals are source-bound but not rerun.

The native cost table's480 distinct source keys and all four summary cost rows are checked, with observed/missing section counts kept separate. Model/API/full-dispatch costs overlap and must not be added to claim CPU or host wall. The source duration histogram has472 views at44.6954375 seconds,2 at46.6954375 and6 at99.6954375; original source lengths are used, including167 seconds beyond a uniform44.6954375-second primary-scene assumption per tap.

Eight examples reproduce the summary's post-result selection: two largest harms and two largest benefits per tap by exact rational latest-cp error-rate delta, then ascending case ID. Their exact scalar fields, unchanged words and bound per-turn evidence/Unknown/return/mapping excerpts are retained. These are descriptive extreme examples, not typical performance or a causal diagnosis; no event mechanism is inferred from them.

## Output and limits

The new JSON review receipt has all source/code/README hashes, check counts, exact denominator and duration rows, summary comparisons and eight source-bound examples. Existing output is refused. No source is overwritten. `PASS_INDEPENDENT_FULL_N03_TABLE_REVIEW` means the specified completed table review passed; it is not final S6C acceptance or an independent neural accuracy run. Incomplete-reference and strict-empty cases remain separately visible. The complete pooled lexical count combines primary serialized WER and complete-overlap MIMO counts and is not renamed as one ordinary WER.

The interpretation Markdown is reviewed separately by the reviewer; its source binding is added in a separate note, without mutating this receipt or the held interpretation.

## PowerShell

Use the existing EDGE Python and a fresh receipt path:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$edge = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $edge -B "$sim\scripts\s6c_n03_component_review_v1.py" --output "$sim\reports\S6C\20260910T123540Z\independent_review\N03_ACTUAL_COMPONENT_REVIEW_V1.json"
```

## Anaconda Prompt / Windows CMD

No environment installation or activation is required when invoking the absolute existing interpreter:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "EDGE=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%EDGE%" -B "%SIM%\scripts\s6c_n03_component_review_v1.py" --output "%SIM%\reports\S6C\20260910T123540Z\independent_review\N03_ACTUAL_COMPONENT_REVIEW_V1.json"
```

For a separately authorized reproduction, choose a new output filename. Run only while the parent has authorized bounded score-table analysis; do not overlap an unrelated quiet paced measurement.
