# Speaker enrollment and live-duration analysis

This report summarizes completed configurations only. It makes no automatic product decision and applies no unsupplied non-inferiority margin.

- Backends: synthetic_smoke_backend
- Completed configurations: 6
- Speaker-cluster bootstrap: 20 repetitions, seed family rooted at 3800, 95% intervals
- Completed phase counts: {'ProbeDuration': 6}
- Speech style: prompted/read Common Voice speech
- Duration label: available waveform audio, not exact voiced-speech time

## Interpretation boundary

Inspect the enrollment, duration, aggregation, reliability, subgroup, and quality-loss tables before authoring a decision gate. Short-probe false-known attribution and valid-output rate must be considered alongside top-1 identification. Tiny age/accent subgroups are descriptive only.

Joint-frontier results present: NO — an operator decision gate is still required after earlier phases.
