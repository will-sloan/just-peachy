# Backend availability and interpretation

Current checkpoint: 2026-09-27. N2 and N3 have accepted offline component
handoffs. Independent numerical N4 reviews cover all 7,680 main and 1,536 modes
cases. The timed application panel, continuity/restart confirmation, deployment
tiers and N4 release selection remain open. No new N5 backend is accepted yet.
Read the newest section of ../n4/N4_HANDOFF.md for the active run.

| Composition | Purpose | Available evidence and remaining release work |
|---|---|---|
| A0/D0/E0 baseline | Sherpa Giga ASR, Pyannote diarization, ReDimNet embeddings and final-only punctuation | Preserved N1 Windows baseline and offline CM5 bundle; included in N4 numerical review and proposed timed panel. Actual ARM64 model/GUI and CM5 checks remain pending. |
| A1/D0/E0 | Parakeet realtime EOU 120M ASR | Accepted N3 offline component scope and reviewed N4 numerical cases; proposed timed panel. Portable release and per-build checks remain pending. |
| A0/D1/E0 | Nemotron diarization with baseline ASR/embedding | Accepted N2 offline component scope and reviewed N4 numerical cases; proposed timed panel. Application/resource and portable release checks remain pending. |
| A0/D1/E1 | TitaNet embeddings in their own model namespace | Accepted N2 offline component scope and reviewed N4 numerical cases; proposed timed panel. Encoder-specific galleries and release checks remain required. |
| A2/D1/E0 and A3/D1/E0 | Native stateful 600M ASR alternatives | Accepted N3 offline component scope and reviewed N4 numerical cases; proposed timed panel. ARM64 native binaries are built; model/GUI functional checks remain pending. |
| Other matrix compositions | Comparators used to interpret the full numerical bank | Numerical coverage does not make a composition a selected or packaged release. |
| X1 multitalker | Optional high-compute overlap comparison | Deferred; not a release. |

The six proposed timed configurations are candidates. Numerical scores alone do
not prove the application's visible latency, sustained operation, restart
behavior or fit within the CM5's 2 GB RAM. None has a measured CM5 tier. Use
MAIN_MODELED_SCORING_ACCEPTANCE_V1.json and MODES_MODELED_SCORING_ACCEPTANCE_V1.json
in ../n4 for the exact reviewed scope; use ../n2/FINAL_REVIEW.json and
../n3/N3_ACCEPTANCE.json for component limitations. A smooth UI or clean exit
does not establish accuracy.

## Later Pi installation and GUI choices

START_HERE.md describes the current baseline package and the later verification,
staging, health check, activation and rollback sequence. The Pi remains powered
off; no files have been installed or checked on it during this campaign.

The intended delivery uses the shared GUI/backend picker and clearly named
launchers for each validated, installed composition. Keep the baseline available.
Install additional model assets only after their ARM64 software route and actual
storage budget are verified. Shared content-addressed assets should be reused;
loading one selected backend must not load all installed models into RAM.

Missing, unsupported and desktop-only choices must be labelled explicitly. A
load failure must report the selected backend's error rather than silently choose
a different backend. Personal data stays outside releases, and galleries from a
different embedding model must be rejected as incompatible. The current baseline
ZIP does not contain every alternative in this table.

The target has 32 GB nominal eMMC; actual free space is unknown. The existing
baseline preflight estimates 2.80 GiB additional free space, including its reserve
and unmeasured overhead budget. That estimate does not cover optional models or
working RAM. See PI_RECONNECTION_REQUIREMENTS.md and
README_PI_STORAGE_PREFLIGHT_V1.md for the exact storage and later device checks.
