# Current project — PROTO1

The current opt-in portrait application is in [`prototype`](prototype).
Double-click `prototype\Start-Prototype.cmd` on the configured Windows desktop,
or follow [`prototype/START_PROTOTYPE.md`](prototype/START_PROTOTYPE.md).
It opens idle; microphone use requires consent. Personal live enrollment and
CM5 hardware checks remain pending. The latest prepared release is **0.1.4**.

Version 0.1.4 adds selectable experimental Spatial-assisted (C079) and Strongly
spatial-assisted (C060) modes, evidence badges, and an optional compact live
beam/estimated-speaker display. It reuses existing S6/S7 tracking and naming;
no dataset sweep or threshold fitting was performed. Strong voice disagreement,
freshness gates and position decay remain active. Saved people stay separate.
See the [mode guide](prototype/MODE_GUIDE.md) and
[bounded update verification](prototype/docs/SPATIAL_FIELD_UPDATE.md).

All 146 software checks passed. Both modes passed short native speech checks
with synthetic direction fixtures. A separate real XVF check delivered 20.02
seconds with zero dropped frames and clean restoration. Telemetry arrived but
the room sample contained no qualifying speech cue; human voice/location
accuracy is still a field-test question. The source archive passed relocated
hash/import/configuration/model checks; CM5 hardware remains untested.

The automated evidence includes 96 focused software checks, a six-scene native
panel, the corrected C105 regression, a 30.7-minute GUI run with 20 mode/recipe
transitions, and relocated release/launcher/rollback checks. Evidence remains
bound to its actual source revision; see the PROTO1 handoff for the precise
0.1.0 soak, 0.1.1 runtime validation and documentation-only 0.1.2 relationship.

[`project_handoffs`](project_handoffs) contains the compact stage handoffs through
PROTO1 and the source-release ZIP, with hashes and explicit data omissions.
The earlier Evaluation Tool extensions, recorder, simulation scripts, configuration,
RIR metadata and accepted S7 source/runner code are also preserved in this branch.

Large/raw data remain at the existing local `XVF 3800 Testing` folders and
`G:\Just_Peachy_*` locations recorded by the manifests. Model weights are shared at
`C:\Users\amiri\JustPeachy\shared\models`; personal data live separately at
`C:\Users\amiri\JustPeachy\data`. A fresh clone needs these separately provisioned
dependencies/data; it is not a full desktop image.

Git maintenance on 19 September 2026 preserved the measurement directory's
uncommitted, no-remote nested Git metadata at `.git-local-backup-20260919` and
`G:\Just_Peachy_Backups\Git_metadata_20260919` before exposing its source to the
parent repository. No measurement, RIR, model, historical result or workbook was
deleted or regenerated. The local metadata backups are excluded from publication.
