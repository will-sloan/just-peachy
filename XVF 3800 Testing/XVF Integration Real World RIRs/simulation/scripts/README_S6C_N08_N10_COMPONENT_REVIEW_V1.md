# Independent actual N08/N10 completed-table review

`s6c_n08_n10_component_review_v1.py` independently reconciles the completed960-cell N08/N10 core, the completed C065 parent, the18 fixed comparisons and the source owner's compact summary. It uses exact SHA-bound original core CSV buffers and the completed comparison's selected CSV. It never imports the scorer, reads predictions/native events/audio/vectors or executes a model/policy.

Inputs are the three source receipts pinned in the helper, their declared SCENE/PROFILE/SHORT/TURN/LIFECYCLE tables, the canonical input metadata, and declared comparison/uncertainty buffers. The historical comparison rows are accepted from the previously reviewed completed comparison authority; its53MB original historical source table is not reopened. Every selected C065/C072/C074 field is compared with its actual original core table row. Numeric reconciliation is a review of inherited scores, not new scoring.

Checks cover all240 scenes per route; the nonuniform source durations; complete203/6016 words/693 turns/292 returns; incomplete26/84 turns/32 returns; all11 empty controls; primary156 versus overlap47; short-turn support, mapping and observed/censored waits; full-text equality/change; nested cost observed/missing cells; lifecycle; and all252 metric rows from18 comparisons. Primary-word uncertainty's point/blocks/rooms are checked without resampling.

The output is one no-overwrite independent JSON receipt with source hashes, exact scalar results, all32 owner-selected metric extremes, scored-final-text witnesses and turn support/return excerpts. Empty-control changed text has its own witnesses. These are post-result examples, not typical performance or causal diagnoses. Zero-delta 'largest harm/benefit' selections are explicitly labeled `observed_direction: equal`. Decoder changes preclude attributing cp differences solely to speaker assignment. Empty insertions have no WER denominator. Incomplete and short/missing support remain separate; nested timing sections do not add to CPU/wall time or establish paced performance.

An active shared paced quiet lease refuses the review before table reading. Sources, owner summary, prior reviews and held scorers remain unchanged. The output may be moderately sized because exact example turn rows and provenance are retained. A later prose review can bind this completed numeric receipt without rereading tables.

## PowerShell

Use the existing EDGE interpreter, standard-library only. This command performs the authorized table review once; do not rerun during a paced quiet interval.

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B "$sim\scripts\s6c_n08_n10_component_review_v1.py" --output "$sim\reports\S6C\20260910T123540Z\independent_review\full_n08_n10_component_v1\REVIEW_RECEIPT.json"
```

## Anaconda Prompt / CMD

No environment installation or activation is needed; the existing interpreter is explicit.

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%PY%" -B "%SIM%\scripts\s6c_n08_n10_component_review_v1.py" --output "%SIM%\reports\S6C\20260910T123540Z\independent_review\full_n08_n10_component_v1\REVIEW_RECEIPT.json"
```

`--output` must name a fresh file. Never delete/overwrite earlier receipts. An explicitly authorized recheck uses a new output namespace; changed helper inputs or semantics require a separately bound new source version. This helper does not implement the still-pending full token-boundary diagnostic and does not approve final study completion or candidate selection.
