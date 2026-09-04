# Eight-Day, C:-Only Scope Amendment for Prompts 4–8

## Authority and effect

- Amendment ID: `full_pipeline_prompts_4_8_eight_day_c_only.v1`
- Program: `just_peachy_full_pipeline_program_v1`
- Authorized by the user on: `2026-08-24`
- Machine-readable authority: `runs/full_pipeline_program/EIGHT_DAY_SCOPE_AMENDMENT.json`
- Execution-policy addendum: `runs/full_pipeline_program/EIGHT_DAY_EXECUTION_POLICY_ADDENDUM.json`
- Program wall-time target: **192 hours total** for Prompts 4–8 (advisory)
- Storage boundary: **C: only**

On `2026-08-24`, the user explicitly changed the execution semantics without
changing the bounded scientific scope: the 192-hour total and per-stage values
are ETA/planning targets only. A healthy run must continue beyond them when
needed. They are not kill switches and may not deny admission to a later stage.
The execution-policy addendum supersedes only the elapsed-time termination and
admission clauses below; panel membership, frozen policies, firewalls, scope
labels, C:-only storage, and evidence-integrity rules remain unchanged.

This amendment supersedes the original Prompt 4–8 campaign breadth and runtime
assumptions. It authorizes deterministic, scientifically balanced bounded panels
so the remaining program can target completion inside eight days. It does not
supersede the program matrix, frozen scientific configurations, model assets,
thresholds, decision policies, evaluation firewall, or evidence-integrity rules.

The bounded program is a distinct protocol realization. Its outputs must never
be described as the complete original full-scope campaign. Original full-scope
runs that were stopped are preserved and marked `SUPERSEDED_PARTIAL_FULL_SCOPE`;
they are not silently merged with bounded results or promoted to complete.

## Advisory wall-time plan

The controller schedules and reports ETA against this 192-hour target:

| Stage | Maximum planned wall time |
|---|---:|
| Prompt 4 — bounded development, qualification, and freeze | 48 h |
| Prompt 5 — bounded untouched held-out core evaluation | 60 h |
| Prompt 6 — bounded extended/streaming/native/reliability evaluation | 30 h |
| Prompt 7 — bounded selection, hardening, packaging, and demos | 12 h |
| Prompt 8 — evidence consolidation and final package | 4 h |
| Shared contingency | 38 h |
| **Total** | **192 h** |

The shared contingency is planning capacity for measured variance, recovery,
validation, or atomic report finalization; it does not authorize widening a
panel. The orchestrator records start/end timestamps, elapsed time, nominal
target consumed, and target overrun for every stage. It recomputes ETA at each
boundary, but insufficient remaining target time does not block admission and
elapsed time does not stop a healthy stage or program.

Prompts 5, 6, 7, and 8 may start automatically only after the preceding amended
completion marker, hashes, and required firewall checks pass. A stage failure,
invalid evidence, free-space failure, or unmet prerequisite stops the transition.
Each successful transition must write a durable milestone notification/status
record before starting the next prompt.

## Scientific invariants that remain locked

The bounded design must preserve all of the following:

- all 18 matrix pipelines in Prompt 4 development and Prompt 5 held-out core;
- the six frozen anchors `AO-H2`, `AG-H2`, `AO-H4`, `AG-H4`, `AO-H5`, and
  `AG-H5`;
- exact assets, hashes, ASR settings, segmentation, clustering, enrollment,
  identity thresholds, Top-1/Top-2 margins, evidence gates, overlap behavior,
  hysteresis, expiry, alignment, buffering, and label policies once frozen;
- the development/evaluation firewall and untouched held-out evaluation;
- development-only derivation and freezing of challenger policies before any
  held-out predictions are opened;
- identical selected panels for every compared pipeline;
- at most two concurrent accuracy jobs;
- one pipeline at a time for standardized resource measurements;
- speaker-level bootstrap intervals that keep each speaker's probes together;
- explicit failed, partial, unsupported, and missing cases in inventories and
  denominators;
- conditional and end-to-end metrics as separate quantities;
- exact hashes for protocols, configurations, code, panel manifests, results,
  reports, and packages.

Panel reduction must be performed from metadata or references before inspecting
the corresponding evaluation predictions. Selection must be deterministic and
record its seed, inclusion/stratification rules, case inventory, excluded-case
inventory, case-manifest hash, reference hash, and achieved scenario/speaker
coverage. No result-dependent sampling, post-hoc pipeline membership change, or
threshold retuning is permitted. Prompt 6 must keep native metrics within the
support of the available references and must not fabricate known-speaker claims.

## C:-only storage contract

All program-controlled inputs, copied datasets, manifests, caches, temporary
files, checkpoints, workspaces, logs, results, reports, compact packages, and
ZIP files for Prompts 4–8 must be read from and written to drive `C:`. Canonical
outputs remain under the Evaluation Tool root:

```text
C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool
```

The program must not use another drive for spill, staging, cache relocation,
junctions, symbolic links, mapped paths, temporary files, results, or ZIPs. Each
stage must resolve and record every material input/output/cache path and verify
that its drive root is `C:\` before work starts.

The required free-space reserve is **35 GiB**. Admission and periodic monitoring
must use drive-C free bytes, not a volume estimate from another path. A stage may
not start, and a running stage must pause safely, if continuing would breach the
reserve. Space pressure is not permission to delete scientific evidence.

Authoritative inputs, frozen configurations, enrollment profiles, source
manifests, unique inference caches needed downstream, logs, partial/final
results, reports, checksums, and packages must not be deleted. Cleanup is allowed
only for checksum-verified, reproducible staging material after all of these
conditions are met:

1. the exact absolute target is resolved beneath an approved C:-only staging
   directory and recorded without a wildcard or unresolved variable;
2. the target is classified as regenerable and is not authoritative evidence;
3. its authoritative upstream inputs and their checksums have been verified;
4. no active or downstream stage requires that staging material;
5. a deletion inventory, reason, byte count, and recovery/regeneration command
   are written before deletion.

If those conditions do not recover sufficient space, the controller must stop
restartably with an explicit storage marker. It must not relocate data off C: or
silently discard evidence.

## Required scope and completion labels

Every artifact, table, report, ZIP, and user-facing status produced under this
amendment must include:

```text
scope_id: full_pipeline_prompts_4_8_eight_day_c_only.v1
scope_class: BOUNDED_REDUCED
original_full_scope_complete: false
```

Use these amended terminal markers:

| Prompt | Amended completion marker |
|---|---|
| 4 | `COMPLETE_ALL18_DEVELOPMENT_AND_FREEZE_REDUCED_8DAY_V1` |
| 5 | `COMPLETE_ALL18_CORE_EVALUATION_REDUCED_8DAY_V1` |
| 6 | `COMPLETE_EXTENDED_PIPELINE_EVALUATION_REDUCED_8DAY_V1` |
| 7 | `COMPLETE_PRODUCTION_CANDIDATE_HARDENING_REDUCED_8DAY_V1` |
| 8 | `COMPLETE_FULL_PIPELINE_PROGRAM_REDUCED_8DAY_V1` |

The corresponding original unqualified completion strings are reserved for the
original full scopes and must not be emitted by bounded runs. Reports must state
the achieved case, speaker, duration, scenario, repetition, native-dataset, UX,
reliability, and resource coverage beside the original requested coverage.

## Final interpretation boundary

The amended program can support comparisons and recommendations within its
predeclared bounded panels. It cannot claim exhaustive execution of every case,
long-stream repetition, native recording, stress condition, or reliability
trial from the original prompts. The final reproducibility package must retain
the stopped original-run inventory, the bounded manifests, all failures, and
this amendment so a reviewer can distinguish measured evidence from deferred
original scope without relying on chat history.
