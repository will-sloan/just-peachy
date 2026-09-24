# N2 final review

N2 offline integration acceptance is complete. All 384 screen, 32 regression and six actual GUI cells finished; final checks passed with zero failures. The 46-module suite passed 434 tests with two explicit skips. N3 may proceed. This acceptance does not mean every candidate has good accuracy or safe personal naming.

| Composition | Tap | Cells | Latest cpWER | Reference words | Maximum sampled process RSS (MiB) |
|---|---|---:|---:|---:|---:|
| D0_E0 | O0 | 48 | 96.42% | 1173 | 513.1 |
| D0_E0 | O1 | 48 | 100.26% | 1173 | 511.0 |
| D0_E1 | O0 | 48 | 105.46% | 1173 | 567.2 |
| D0_E1 | O1 | 48 | 104.60% | 1173 | 567.4 |
| D1_E0 | O0 | 48 | 35.98% | 1173 | 1082.5 |
| D1_E0 | O1 | 48 | 35.98% | 1173 | 1082.5 |
| D1_E1 | O0 | 48 | 35.98% | 1173 | 1159.5 |
| D1_E1 | O1 | 48 | 35.98% | 1173 | 1159.7 |

cpWER measures attributed lexical streams on complete references and retains Unknown. It is not ASR lexical WER. The same words pass exact ASR invariance across all compositions and both main/regression populations. Caption conditions pass the observed-only checks.

- D1 approximate zero-collar DER is 23.80% O0 and 32.32% O1; D0 activity DER is unavailable, so this is not a D0-versus-D1 DER comparison.
- D1/E0 and D1/E1 actual latest cpWER is 35.98% on each tap versus 96.42/100.26% for D0/E0 and 105.46/104.60% for D0/E1. These are attributed lexical errors over 1173 reference words per tap, retaining Unknown; not lexical WER or verified personal naming.
- All main combinations preserve identical raw ASR words. Each tap/composition retains one empty-control inserted word.
- The actual primary captions contain zero verified named words. Shadow open/closed gallery diagnostics remain separate; closed labels are assumptions.
- D1 O1 activity failure persists; the 250ms collar sensitivity is not uniformly better because false alarms and changed retained denominators matter.
- Resources are desktop process measurements with evaluator overhead and concurrent CPU/CUDA lanes; they do not establish isolated candidate speed, GPU memory or total-system 2GB suitability.

Retain the baseline and D1/E0 nominal 1.04-second hybrid. Keep E1 configurations as functioning controlled comparators, without claiming a measured naming improvement. N4 must perform full-bank comparison and candidate-isolated resources before deployment selection.

FINAL_REVIEW.json contains exact aggregates and source hashes. The larger SCREEN_SUMMARY.json and REGRESSION_SUMMARY.json remain separately versioned; they are referenced rather than included in the small handoff ZIP. Earlier smoke/preparation reports in the ZIP are historical and are superseded by this review for completion status.
