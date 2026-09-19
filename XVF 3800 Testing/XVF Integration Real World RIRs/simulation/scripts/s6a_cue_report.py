"""Compact analysis-first cue/reference handoff; README_S6A_CUES.md."""
from __future__ import annotations
import csv
from pathlib import Path
from s6a_cues import read,save,binding,DEFAULT_REPORT,now


def percent(value):return 'unavailable' if value is None else f'{value*100:.2f}%'


def build(report=DEFAULT_REPORT):
    report=Path(report);foundation=read(report/'CUE_FOUNDATION.json')
    features=read(report/'cues/FEATURE_INDEX.json')
    tests=read(report/'CUE_TEST_RECEIPT.json')
    parity=read(report/'CUE_FEATURE_B0_PARITY.json')
    provenance=read(report/'CUE_PROVENANCE_RECEIPT.json') if (report/'CUE_PROVENANCE_RECEIPT.json').exists() else None
    scores=read(report/'REFERENCE_PROFILE_RECEIPT.json') if (report/'REFERENCE_PROFILE_RECEIPT.json').exists() else None
    audit=read(report/'CUE_REFERENCE_COVERAGE_PARITY.json') if (report/'CUE_REFERENCE_COVERAGE_PARITY.json').exists() else None
    complete=bool(scores and scores['status']=='COMPLETE' and features['completed']==480 and parity['status']=='PASS')
    with (report/'CUE_RELIABILITY_BY_POPULATION.csv').open(encoding='utf-8') as handle: strata=list(csv.DictReader(handle))
    primary=next(r for r in strata if r['population']=='PRIMARY_NONOVERLAP' and r['stream']=='selected_processed')
    text=f'''# S6A physical cues and six reference trackers

Status: {'COMPLETE — all 240 scenes, both taps and six reference profiles analyzed.' if complete else 'PARTIAL — physical cue foundation complete; final 480-output reference analysis is pending.'}
Generated: {now()}

'''
    if complete:
        comparable={(r['profile'],r['stream']):r for r in scores['summary'] if r['population']=='ALL_COMPLETE_NONEMPTY'}
        changes=[100*(comparable[('R5_reliability_adaptive',s)]['cpwer']-comparable[('R1_voice_time',s)]['cpwer']) for s in ('O0','O1')]
        text+=f'''On all 203 complete-reference nonempty scenes, reliability-adaptive R5
changes final-label cpWER versus matched voice/time R1 by {changes[0]:+.2f}
percentage points on O0 and {changes[1]:+.2f} on O1. These are descriptive
bank results with unchanged ASR words. The new trackers still have more
unassigned support and generally worse final attribution than the exact
native B0. B0 and new methods also use different availability conventions,
so this is not an isolated tracker or live-latency comparison.

Angle association R2 leaves about 62% of complete-reference sole support
unknown. Its cpWER alone would conceal poor usable identity coverage.
One-person output has perfect return continuity but 30.93% mixed-identity
support; all-unknown output retains 100% unknown support. Neither control
can be described as a successful tracker. The cue variants remain candidates
for joint testing, not selected production settings.

'''
    text+='''
The selected processed direction is frequently available but its nominal
geometry agreement is weak in this bank. On the 545 complete-reference,
non-overlap utterances, it was usable for '''+f'''{float(primary['usable_fraction'])*100:.2f}%
of estimated source support and occupied the expected coarse sector for
{float(primary['matching_sector_fraction'])*100:.2f}%. Sustained acquisition was
never observed for {primary['sustained_never_acquired']}/545 utterances under
the inherited one-second/80%-occupancy physical metric. This supports soft,
qualified use of direction and a working no-metadata fallback. It does not
show that direction cannot help anonymous tracking: an offset or folded
observation can still carry relative change information.

The physical foundation contains exactly 240 shared traces, not 480
independent O0/O1 directional observations. It reuses 180 bound historical
spatial analyses and adds 60 analyses under the new all-bank authorization.
There are 777 utterance references and six directional streams. Summed
per-source support can include simultaneous sources; it is not unique
physical duration. The former 180/60 split is descriptive only.

## Physical cue evidence

| Stream | Usable support | Expected-sector support | Sustained never acquired |
|---|---:|---:|---:|
'''
    for row in foundation['summary']:
        text+=f"| {row['stream']} | {percent(row['usable_fraction'])} | {percent(row['matching_sector_fraction'])} | {row['sustained_never_acquired']}/{row['utterance_rows']} |\n"
    text+='''
`CUE_RELIABILITY_BY_POPULATION.csv` separates complete non-overlap, complete
overlap and known targets in incomplete environmental mixtures. The 15
examples in `CUE_ADVERSE_EXAMPLES.csv` are explicitly posthoc descriptions,
not a tuning panel or independent samples. “Held wrong” means the same
numeric angle persisted in a wrong coarse sector. It does not prove stale
DSP data. No historic DSP frame timestamp, AEC/AGC state, or RT60 has been
invented. Manual +/-5 degrees is geometry uncertainty, not a sensor-accuracy
specification. Native 0/180 endpoints are not adjacent, front/back can fold,
and a beam is not a person.

## Implemented reference profiles

| Profile | Actual mechanism |
|---|---|
| B0 | Exact saved native final words and speaker labels; immutable control. |
| R1 voice/time | New bounded anonymous tracker; unique evidence union, separate association/prototype thresholds, unknown state. |
| R2 angle diagnostic | Anonymous spatial association without voice cosine; shares baseline audio eligibility and qualified delivered-angle checks. It is not an independent speech detector. |
| R3 sustained angle | Sampled persistent direction-change proposals with bounded voice association support; no forced new identity or ASR reset. |
| R4 decaying memory | Position support decays with time; severe voice conflict cannot be overruled by location. |
| R5 reliability adaptive | Voice/location support is moderated by delivery age, positive energy when available and agreement of correlated directional fields. These are engineering confidence checks, not calibrated probabilities. |

All new modes execute `ResearchTracker` from the actual H2 app. The GUI
default remains the original pipeline. The reference study holds baseline
ASR words, segmentation eligibility and exact accepted 0.5-second embedding
spans fixed. A real ReDimNet2 call computes every cached vector; no reference
voice, transcript, room, seat, true speaker count or schedule is supplied to
the tracker. R2 still shares the upstream gate/cost and rejects nonpositive
raw-auto energy when present; “angle-only” describes association, not an
unfiltered sensor-only route. No compute saving is claimed merely from a
cheap policy replay. Separate S6A component probes change real neural and
recognition inputs/settings and must be evaluated separately.

Each track is bounded and carries actual provisional/committed IDs. New
voice evidence updates a prototype only above the separate update threshold.
Overlapping windows add only newly covered seconds; a long silence adds no
identity evidence. Defaults are 16 tracks, 0.35 cosine association, 0.45
prototype update, 0.03 ambiguity margin and 1.0-second anonymous commitment.
These values are not an enrolled-identity probability or naming threshold.

A qualified direction proposal plus voice conflict can split a provisional
branch. Fresh overlapping voice evidence can reconcile it to its established
parent at cosine >=0.65, while it remains provisional and within two seconds.
The uncertain branch vectors are not pooled. A merge emits a forward
`label_revision` referring to the immutable first-decision ID; it does not
rewrite earlier first output or reset ASR. The revision queue is capped at
64 records. Fixture success establishes capability, not real-bank correctness.
With a 1.0-second embedding and 1.0-second commitment threshold, a new branch
commits immediately and this provisional reconciliation cannot run. S6B must
test embedding duration × commitment evidence × revision horizon together.

## Causal availability and cache boundaries

The exact B0 embedding function and ORT session factory execute from the
archived baseline snapshot. Audio comes from the already-gained native PCM16
journal and is read at unity. O0's +3 dB is not applied again. Feature keys
bind audio bytes, accepted-event selection, checkpoint, ORT provider/version,
threads, numeric/frontend recipe, exact source and input spans. A policy
change invalidates tracking; a changed waveform/span/model recipe requires
actual new vectors. Provider/thread changes do not inherit performance.

The reference bridge reads only metadata already received by the historical
callback containing the last input sample. Extra modeled speaker computation
ages that observation; packets arriving during compute are conservatively
omitted. Serial availability is `max(previous_ready, input_end) + measured
call_cost`. Segmentation costs are inherited from exact native calls; new
embedding calls are measured. Accelerated inference wall time is never joined
to the historical capture QPC clock. These are modeled availability/costs,
not measured live end-to-end latency or CM5 RTF.

The actual app probes use separately bound sanitized JSONL: a selected-angle
receipt becomes available at the first containing-or-later copy-complete
audio callback. Only earlier delivered energy/direction is attached. The
unknown native observation span is omitted. Both taps share the same trace.
Callback quantization and the slightly different conservative reference
bridge are explicitly recorded; matched factorial cells use the same JSONL.

Candidate final text uses only the latest decision already available at the
native final source cursor. It preserves all raw final words. B0 preserves
its actual native attribution. This common replay is not a controlled
measurement of the old cross-thread race or true word-level speaker timing.
For B0, the recorded source cursor locates each unchanged native decision;
its historical live decision availability is unknown. R1-R5 use the serial
modeled availability with measured neural costs described above. Their
matched cue comparisons share this rule, but B0-versus-new unknown-support
differences combine tracker and availability policies and do not isolate
the effect of a single component.

## Scoring and current coverage

'''
    text+=f"Completed exact feature outputs: {features['completed']}/480. Archived B0 label parity: {parity['windows']:,} windows, {parity['mismatches']} mismatches over {parity['outputs']} outputs.\n\n"
    if audit:
        cost=audit['cost']
        text+=f"The shared cache contains {cost['unique_redim_vectors']:,} newly computed ReDim vectors, costing {cost['measured_embedding_compute_sec']:.2f} measured desktop seconds in total. It inherits {cost['inherited_native_segmentation_compute_sec']:.2f} seconds of native segmentation calls without recomputing them. Additional policy evaluation totals range from {min(v for k,v in cost['policy_wall_sec_by_profile'].items() if k!='B0'):.2f} to {max(v for k,v in cost['policy_wall_sec_by_profile'].items() if k!='B0'):.2f} seconds across 480 outputs per new method. These are separate shared neural and added policy costs, not full-pipeline RTF; ASR, capture, I/O and target-device overhead remain outside these totals. Modeled availability includes the recorded neural lane costs, not a calibrated end-to-end measurement.\n\n"
    if complete:
        text+='All 2,880 six-profile outputs and 960 diagnostic control outputs are present.\n\n'
        text+='| Profile | Tap | cpWER, complete nonempty | Unknown sole support | Mixed-identity fraction of known support | Return consistent / inconsistent / unknown |\n|---|---|---:|---:|---:|---|\n'
        for row in scores['summary']:
            if row['population']!='ALL_COMPLETE_NONEMPTY':continue
            text+=f"| {row['profile']} | {row['stream']} | {percent(row['cpwer'])} | {percent(row['unknown_fraction'])} | {percent(row['false_merge_fraction_of_known'])} | {row['return_consistent']} / {row['return_inconsistent']} / {row['return_unknown']} |\n"
        short_groups={}
        with (report/'REFERENCE_SHORT_TURN_RESULTS.csv').open(encoding='utf-8',newline='') as handle:
            for row in csv.DictReader(handle):
                if row['population'] not in ('PRIMARY_NONOVERLAP','COMPLETE_OVERLAP'):continue
                key=(row['profile'],row['stream'],row['duration_bin'])
                group=short_groups.setdefault(key,{'source_turns':0,'known':0})
                group['source_turns']+=int(row['source_turns']);group['known']+=int(row['turns_with_known_modal_label'])
        text+='\nComplete-reference short turns, using whole native clip duration bins:\n\n| Profile | Tap | <1 s: known modal / all turns | 1-<2 s: known modal / all turns |\n|---|---|---:|---:|\n'
        for profile in ('B0','R1_voice_time','R2_angle_diagnostic','R3_sustained_angle','R4_decaying_memory','R5_reliability_adaptive','CONTROL_ONE_PERSON','CONTROL_ALL_UNKNOWN'):
            for stream in ('O0','O1'):
                a=short_groups[(profile,stream,'<1s')];b=short_groups[(profile,stream,'1-<2s')]
                text+=f"| {profile} | {stream} | {a['known']} / {a['source_turns']} | {b['known']} / {b['source_turns']} |\n"
        text+='\nA known modal label is coverage, not correct identity. On O1 subsecond turns, R5 falls from R1’s 32/40 known modal labels to 30/40 despite its aggregate cpWER improvement. On O0 it rises from 27/40 to 28/40. Thus the modest aggregate gain does not establish short-reply benefit. All missing/unassigned turns remain in the denominator.\n'
        text+='\nActual operation counts across all reference scene/tap outputs:\n\n'
        for profile in ('R1_voice_time','R2_angle_diagnostic','R3_sustained_angle','R4_decaying_memory','R5_reliability_adaptive'):
            group=[r for r in scores['summary'] if r['profile']==profile and r['population']!='ALL_COMPLETE_NONEMPTY']
            text+=f"- {profile}: {sum(r['splits'] for r in group)} provisional splits, {sum(r['merges'] for r in group)} merges, {sum(r['revisions'] for r in group)} forward revisions.\n"
    else:text+='Final reference accuracy/attribution conclusions are withheld until all 480 baselines and all six profiles are complete.\n'
    text+='''

Tracking integrates actual first-decision states over integer sample
intervals and estimated source support. It removes other simultaneously
active source supports from sole-speaker diagnostics, expires old states
0.75 seconds after input end, and preserves unavailable alignment and every
short/unassigned turn. “Mixed identity” counts known support outside each
predicted label's dominant reference identity. Fragmentation and returns are
reported separately. This is not DER, named identity, or exact phonetic
timing. Incomplete environmental mixtures retain limited known-target
diagnostics and are excluded from complete-reference identity pooling.

cpWER groups actual final text by predicted label and uses one global
assignment. Empty references keep WER undefined. One-person and all-unknown
controls expose degenerate continuity/abstention: their combined unknown and
conflation fixture must fail. No opaque total score chooses a winner; use the
separate lexical, attribution, coverage, return, latency and cost columns.

## Verification and handoff files

'''
    text+=f"`CUE_TEST_RECEIPT.json` records {tests['fixture_tests']} fixture tests and {tests['actual_policy_trials']} actual-feature policy trials over {tests['actual_feature_outputs']} selected outputs. Empty-feature test cases remain explicit. The checks cover cache dependencies, different future suffixes, truth renaming, stale/missing/reordered metadata, two host chunk patterns, unique evidence, linear angles, bounded state, and real forward lineage.\n\n"
    if provenance:
        text+=f"`CUE_PROVENANCE_RECEIPT.json` records {provenance['status']} across {provenance['physical_traces']} physical captures and {provenance['telemetry_rows']:,} raw telemetry rows. It checks accepted-capture flags, continuous frame ranges, copy-completion chronology, per-field reply counts and sanitized-input hashes. `CUE_CODE_ARCHIVE.json` resolves the exact extraction source bytes recorded by the smoke and bulk feature receipts; their numerical feature functions are identical. A rejected Windows line-ending archive attempt is preserved but never used as executable or selected source.\n\n"
    if audit:
        text+=f"`CUE_REFERENCE_COVERAGE_PARITY.json` records {audit['status']}: all 777 inserted utterances remain in every method/tap, producing {audit['retained_turn_rows']:,} turn rows and identical summed short-bin coverage. All {audit['unchanged_final_word_sequences']:,} reference outputs preserve native final word sequences. All {audit['baseline_metric_parity_outputs']} B0 cpWER results exactly match the independent original-setting scorer. `CUE_OBSERVED_REVISIONS.json` preserves the one observed forward revision (R4, S45_11_12, O1), including its preceding immutable decision; revised identity correctness is not inferred.\n\n"
    text+='''
Compact tables: `REFERENCE_PROFILE_RESULTS.csv`, per-scene and per-turn
results, `REFERENCE_SHORT_TURN_RESULTS.csv`, `CUE_RELIABILITY_SUMMARY.csv`,
population strata and adverse examples. Receipts bind all local artifacts.
Full event traces and vectors remain local and are not handoff ZIP contents.
`README_S6A_CUES.md` gives exact PowerShell, Anaconda Prompt and Command Prompt
commands, inputs, outputs, cache/resume behavior, and rollback.

This sub-study does not select a production configuration, prove causal
population benefit, or qualify CM5. S6B should preserve the voice-only
fallback and test supported component interactions with matched cue-off
parents, including short/overlap evidence, commit/revision timing, direction
persistence and persistent wrong cues. The independent real-conversation
validation remains later work.
'''
    target=report/'CUE_REFERENCE_HANDOFF.md';target.write_text(text,encoding='utf-8')
    names=['CUE_REFERENCE_HANDOFF.md','CUE_FOUNDATION.json','CUE_DELIVERY_INDEX.json','CUE_RELIABILITY_SUMMARY.csv',
           'CUE_RELIABILITY_BY_POPULATION.csv','CUE_ADVERSE_EXAMPLES.csv','CUE_TEST_RECEIPT.json',
           'CUE_FIXTURE_TEST_RECEIPT.json','CUE_REAL_FEATURE_CAUSALITY.json','CUE_FEATURE_B0_PARITY.json']
    if provenance:names+=['CUE_PROVENANCE_RECEIPT.json','CUE_CODE_ARCHIVE.json','CUE_PHYSICAL_INTEGRITY.json']
    if complete:names+=['REFERENCE_PROFILE_RESULTS.csv','REFERENCE_PROFILE_SCENE_RESULTS.csv','REFERENCE_PROFILE_TURN_RESULTS.csv',
                        'REFERENCE_SHORT_TURN_RESULTS.csv','REFERENCE_PROFILE_RECEIPT.json']
    if (report/'CUE_PLOT_RECEIPT.json').exists():
        names+=['CUE_PLOT_RECEIPT.json','CUE_REFERENCE_DIAGNOSTIC_PLOT_DATA.csv','CUE_REFERENCE_DIAGNOSTIC.png']
    if (report/'CUE_REFERENCE_COVERAGE_PARITY.json').exists():
        names+=['CUE_REFERENCE_COVERAGE_PARITY.json','CUE_OBSERVED_REVISIONS.json']
    manifest=dict(schema='jp_s6a_cue_compact_handoff_v1',status='COMPLETE' if complete else 'PARTIAL',
                  files=[binding(report/name) for name in names],excluded=['full cue/profile traces','ReDim vectors','raw audio'],
                  created_utc=now(),code=binding(__file__))
    save(report/'CUE_HANDOFF_INDEX.json',manifest);return manifest


if __name__=='__main__':
    import argparse,json
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--report',type=Path,default=DEFAULT_REPORT)
    args=parser.parse_args();print(json.dumps(build(args.report),indent=2))
