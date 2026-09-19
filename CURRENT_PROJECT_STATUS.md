# Current project — PROTO1

The current opt-in portrait application is in [`prototype`](prototype).
Double-click `prototype\Start-Prototype.cmd` on the configured Windows desktop,
or follow [`prototype/START_PROTOTYPE.md`](prototype/START_PROTOTYPE.md).
It opens idle; microphone use requires consent. Personal live enrollment and
CM5 hardware checks remain pending. The final prepared release is **0.1.2**.

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
