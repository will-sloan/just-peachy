# D0/TitaNet scale proposal rejected; nominal remains experimental

The protected calibration collection completed 734/734 encoder/clip jobs.
Strict review verified 367 clips per encoder, 3,409 exact matched waveform
windows (1,985 short and 1,424 mature), and 2,290 segmentation calls per encoder.
Every clip produced at least one admitted window. Original clips, clean support,
models, source and vectors were bound; E/Q truth never entered inference.
`D0_COLLECTION_REVIEW_V1.json` records this collection acceptance only.

The single predeclared affine scale proposal failed its fixed validation rule.
It is **UNQUALIFIED_C_SCALE**, retained without parameter retuning, an altered
partition or threshold search. See `D0_SCALE_FIT_V1.json` and the unchanged
`D0_C_SCALE_PROTOCOL_V1.json`. The fit used 25 positive identity groups and 351
different-identity pairs; validation used 8 positive groups and 36 different
identity pairs. These are weighted correlated engineering groups, not counts
of independent trials or a deployment confidence interval.

| C-validation condition | Same-speaker rejection | Different-speaker acceptance | Balanced mean |
| --- | ---: | ---: | ---: |
| E0 frozen nominal | 29.402% | 0.259% | 14.831% |
| E1 inherited nominal | 22.905% | 0.149% | 11.527% |
| E1 proposed affine scale | 28.174% | 0.046% | 14.110% |

The proposal moved the association threshold from 0.35 to 0.379544 and score
scale from 0.15 to 0.182663, together with the declared related cosine fields.
Its balanced validation error rose 2.583 percentage points versus nominal E1,
exceeding the predeclared 2-point allowance despite fewer false associations.
The application accepted the proposed parameter ranges, but that does not
override the scientific validation failure. The profile is not integrated.

The lower nominal E1 pair error is a clean-C diagnostic. It does not establish
better online tracks or calibrated names on processed XVF queries. D0/E1 keeps
its frozen inherited nominal settings as an explicitly unqualified engineering
comparison condition; do not present that as its own accepted calibrated profile.
Its calibration limitation stays visible in matrix/release decisions. No new
default or winning family is selected. Operational processed-query naming stays
Unknown; closed-roster labels remain assumptions.

The next actual run is `local/n4/d0-bank-v1`, 480 accepted query files for E0
then the same 480 for E1, one encoder process at a time. Collection does not
adopt the failed scale because fixed-cadence query selection consumes neither
tracker output nor names. It preserves full segmentation frames, exact query
slices and rejected windows, and earns zero integrated-cell credit until the
ASR/association/display comparison executes. Full anonymous activity output,
integrated cache replay, paced/GUI/continuity and resource checks still remain.

This is a decision receipt, not executable code. Collection, fitting, review
and launch commands are in README_D0_CALIBRATION.md, README_D0_REVIEW.md,
README_FIT_D0_SCALE.md and README_D0_BANK.md, with PowerShell and CMD/Anaconda
examples. No Pi operation, capture, playback, training or personal data change
was involved. Detailed C vectors and source identity partitions remain private.
