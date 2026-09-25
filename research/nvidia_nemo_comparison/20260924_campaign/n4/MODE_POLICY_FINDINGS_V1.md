# Actual baseline and N2 naming-policy differences

Source-inspection and method-test finding, 2026-09-25. This records an explicit
correction to the broad reject-all expectation in SCORING_PLAN.md, before any
N4 named accuracy or first-visible metric has been accepted. It changes no
model, threshold, gallery, query, original source or baseline behavior.

The immutable n4-catalog-v3 source receipt is SHA-256
`8050c8bee52a6ec83c95f3514cb81219c3664dd43e172a477d35a54888e610d5`.
Its catalog admits all 16 tuples. Actual Controller source selection chooses
PrototypeEngine for A0/D0/E0 baseline; every other entry has a nonempty `n2`
composition and chooses N2Engine or N3IdentityEngine. This includes A1, A2 and
A3 with D0/E0. That distinction applies even when the neural identity components
are identical. Comparing only A/D/E model names would miss the resolver change.

`PrototypeEngine.begin()` installs PrototypeIdentityResolver for named modes
and its diagnostic tracker wrapper. `N2Engine.begin()` then installs N2NameMap
for D0, or exposes that map to the native activity/history path for D1. Anonymous
baseline retains ResearchIdentityResolver(None); anonymous N2 uses N2NameMap(None),
with different disabled/unknown metadata. Earlier narrowly scoped anonymous
helpers remain historical method evidence; they are not proof that all catalog
routes had identical policy. The new adapter follows actual catalog routing.

Both E0 and E1 fixed primary galleries preserve 24 available of 34 intended open
references and 3 available of 4 selected references. Their published processed-Q
gates are UNCALIBRATED_REJECT_ALL. Twelve integrity/mode tests and 160 actual
begin-method checks passed; MODE_GALLERIES_CHECK_V1.json binds them. Original
source, accepted extraction, source galleries, unchanged vectors, namespace
aliases and missing-reference denominators were verified. No new fitting or
comparison against Q truth took place.

N2NameMap honors these gates and rejects open names. Its selected-closed mode
can choose a cosine winner after at least 0.5 seconds of unique clean support;
that is a `closed_assumption` with `verified=false`, independent of calibration.
The baseline resolver instead retains its original C088 thresholds and does not
consult N2's calibrated-gate schema. A synthetic exact-vector test demonstrates
that it can reach `confirmed` under those nominal thresholds. That application
field does not prove recognition on processed XVF audio. Preserve any resulting
baseline outputs and report their empirical errors and calibration limitation;
do not silently force them to Unknown or label them operationally calibrated.
The old general statement that all operational open outputs reject to Unknown
therefore applies to N2 here, not to the unchanged original baseline resolver.

There is also a product-mode gap. The shared selected-closed description says
every caption gets an assumed selected name, using recent/same-utterance history
or the first roster entry when voice is missing. Actual baseline annotation
implements that explicit unverified fallback. N2 annotation only supplies
`closed_display_assignment` when a part already has a known profile and
`closed_assumption` state; it does not implement the no-voice roster fallback.
Both behaviors were exercised with actual methods and untouched raw caption
rows. The comparison must retain this difference. A future product fix requires
a separate derivative and retests; no accepted release has been edited.

In every result keep acoustic decisions, post-policy presentation state,
published display annotation and actual Controller/widget delivery distinct.
Forced/closed labels are assumptions, never verified identity or adaptation
evidence. Modeled display publication cannot populate first-visible naming
metrics. The new mode checks qualify method wiring only; full Controller parity,
integrated bank scoring and paced GUI/resource confirmation remain necessary.
