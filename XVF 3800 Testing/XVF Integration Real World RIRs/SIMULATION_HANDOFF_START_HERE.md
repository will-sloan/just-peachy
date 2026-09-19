# XVF3800 simulation context after the measurement audit

The detailed current handoff is [CHATGPT_SIMULATION_HANDOFF.md](validation/SIMULATION_CONTEXT_AUDIT_20260908/CHATGPT_SIMULATION_HANDOFF.md). The complete upload package is [XVF3800_CHATGPT_HANDOFF_20260908.zip](validation/SIMULATION_CONTEXT_AUDIT_20260908/XVF3800_CHATGPT_HANDOFF_20260908.zip).

The audit identifies **127 formal REVIEW recordings eligible for RIR qualification**, excludes 52 early/failed recordings, and records two user-confirmed distance corrections from 100 m to 1.00 m. Effective distances are 0.46–4.07 m. No angle sign reversals were supported by the sweep delay check. **No final qualified RIRs were found.**

Use the curated `eligible_recordings.json` and `metadata_corrections.json` in that audit folder for later extraction. The original RECORDINGS_INDEX.csv and archived requests remain unchanged and still contain the two historical 100 m entries. Do not use that original index alone as the simulation selection.

The latest supplied Word guide is the unchanged DOC.docx copy in the audit folder. The older V4 document remains in reference_documents as historical evidence. The audit README contains reproducible run commands; START_WITH_CHATGPT.md contains a suggested planning request.
