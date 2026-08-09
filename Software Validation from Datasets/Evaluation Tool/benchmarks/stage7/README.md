# Stage 7 Core Screening Plan

This directory is generated from the frozen small benchmark manifest. It contains no inference results.

- Plan ID: `screening_plan_64a77a1c7e4e`
- Benchmark items: `165`
- Scenario count: `84`
- Reference ASR: `whisper_base`

## Sequence

- **A — Availability and contract qualification**: ready
- **B — ASR screen**: ready
- **C — VAD and segmentation screen**: ready
- **D — Targeted cross-check**: pending_selection
- **E — ECAPA fixed-segment extraction qualification**: ready
- **FINAL — Repeated finalist validation**: pending_selection

Use `evaluation-tool screening qualify` for Stages A/E, then run only the scenario IDs listed for B/C. Rebuild this plan with the declared Stage C shortlist before D, and with declared finalists before repeated validation.
