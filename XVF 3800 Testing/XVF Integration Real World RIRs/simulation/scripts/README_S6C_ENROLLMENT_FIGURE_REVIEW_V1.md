# Enrollment-duration figure numerical review

Purpose: check the completed enrollment_duration_v1 figure's twelve points against all sixty compact name-aggregate rows, source-roster membership and estimated enrollment-tier durations. The review reads exact original CSV/JSON buffers and hashes them before using their contents. It does not import plotting code, open individual predictions, rerun scorers/policies/models, or edit any figure/data.

Inputs are FIGURE_RECEIPT, its PLOT_DATA/caption/source bindings, the existing full common-duration NAME_ANALYSIS_RECEIPT and PROFILE_NAME_RESULTS.csv, COMMON30_GALLERY_PLAN/COMPLETION, and the material preparation receipt's tier-coverage CSV. Outputs are one additive independent numeric review receipt. Count partitions, missing versus zero and enrolled/withheld denominators remain explicit. Estimated usable speech and whole-clip durations are reported separately; paired rosters remain separate.

Use the bundled Python runtime for this read-only CSV audit. No package install is needed.

PowerShell:

    $s6cSim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
    $reviewPy = 'C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    & $reviewPy -B "$s6cSim\scripts\test_s6c_enrollment_figure_review_v1.py" --output "$s6cSim\reports\S6C\20260910T123540Z\independent_review\ENROLLMENT_DURATION_FIGURE_REVIEW_V1.json"

Anaconda Prompt or Windows CMD:

    cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
    "C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -B scripts\test_s6c_enrollment_figure_review_v1.py --output reports\S6C\20260910T123540Z\independent_review\ENROLLMENT_DURATION_FIGURE_REVIEW_V1.json

Choose a fresh output filename for any later reproduction. Figure revisions require separate admission; the original figure receipt is pinned. The numeric review does not claim visual review, causal duration isolation, independent population validation or actual wall-clock/GUI name latency.

