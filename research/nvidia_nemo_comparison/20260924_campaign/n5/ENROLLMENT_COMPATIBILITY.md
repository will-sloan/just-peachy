# Personal data and embedding compatibility

The original store `C:\Users\amiri\JustPeachy\data` is unchanged. Release code,
runtime wheels and hash-addressed model assets are replaceable; UUIDs, references,
photographs and preferences live outside those directories. The shipped baseline
contains no personal profiles, research participants, voiceprints or saved audio.

ReDimNet and TitaNet both produce 192-dimensional vectors, but their values are
not interchangeable. A compatible reference binds encoder hash, preprocessing,
normalization, dimension and audio domain. TitaNet uses a separate
`embedding_spaces/<namespace hash>/people` store. Preserve UUIDs only when
explicitly re-extracting permitted original E audio; otherwise re-enroll later.
Do not relabel existing vectors or use closed-roster/seat assumptions as truth.

The updater currently supports schema 1 and checks paragraph-enrollment reader
compatibility. There is no new N5 migration or automatic conversion. Incompatible
future schemas and rollback to a reader lacking required features are refused.
An older updater must not be used to bypass that check. Save/import/export/delete
fixture tests are not a new human enrollment study. Final per-candidate actual
GUI persistence and rollback checks remain pending N4 acceptance.

The processed XVF open-name gate is uncalibrated and remains reject-all/Unknown.
Noisy naming could fail because usable voice evidence is absent, because
embedding scores overlap, because gates reject it, or because tracks associate
incorrectly. Current aggregate evidence does not distinguish these causes well
enough to claim one fix. N4 must examine availability, discriminability, gating
and tracking separately using the admitted disjoint E/C/Q protocol.
