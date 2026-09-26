"""Evaluator-only observed-name diagnostics; see README_OBSERVED_NAME_SCORING.md."""
from collections import Counter

from common import fingerprint
from naming_reference import join_observed
from review_scoring_bank import require

STAGES = ('first_visible','first_final_visible','latest')
PANES = ('active','history')
KINDS = {'ROSTER_NAME','FORCED_ROSTER_ASSUMPTION','UNKNOWN','PENDING','ANONYMOUS',
         'TRANSCRIPTION','SUPPRESSED','ABSENT','UNRECOGNIZED','AMBIGUOUS_RESERVED_ROSTER_NAME'}
SUPPORTS = {'SINGLE_INTERSECTING_ESTIMATED_IDENTITY','MULTIPLE_INTERSECTING_REFERENCE_IDENTITIES',
    'TARGET_ONLY_INCOMPLETE_REFERENCE','NO_ESTIMATED_REFERENCE_ACTIVITY',
    'UNAVAILABLE_SOURCE_WINDOW_OUTSIDE_FILE','UNAVAILABLE_ZERO_WIDTH_SOURCE_WINDOW','NOT_A_LEXICAL_WORD'}
MAX_SPANS = 8192


def classify(reference, pane, mapping, *, control=None, constant_profile=None):
    """One native-span/pane opportunity; no permutation or inferred heading."""
    status = reference['status']; require(status in SUPPORTS, 'Unknown reference support')
    person = reference.get('single_intersecting_identity')
    single = status == 'SINGLE_INTERSECTING_ESTIMATED_IDENTITY'
    require((single and type(person) is str and reference['reference_identities'] == [person])
        or (not single and person is None), 'Reference support identity is inconsistent')
    category = ('AVAILABLE_PROFILE_REFERENCE' if person in mapping.values() else 'OUTSIDE_AVAILABLE_PROFILE_REFERENCE') if single else 'UNRESOLVED_REFERENCE'
    if pane is None: kind = 'MISSING_STAGE'; profile = None; visible = False
    else:
        kind = pane['kind']; profile = pane['roster_profile_id']
        visible = pane['heading_and_caption_glyphs_visible_in_same_pane']
        require(kind in KINDS and type(visible) is bool, 'Invalid recorded pane category/visibility')
        require((kind in ('ROSTER_NAME','FORCED_ROSTER_ASSUMPTION') and profile in mapping)
            or (kind not in ('ROSTER_NAME','FORCED_ROSTER_ASSUMPTION') and profile is None), 'Unmapped or unexpected displayed profile')
        require(kind not in ('ABSENT','SUPPRESSED') or not visible, 'Absent/suppressed label claims visibility')
    require(control in (None,'all_unknown','constant_name'), 'Unadmitted naming control')
    if control == 'constant_name': require(constant_profile in mapping, 'Constant name must be an available fixed profile')
    # Hold the observed opportunity fixed; do not invent control-rendered geometry.
    if visible and control == 'all_unknown': kind,profile = 'UNKNOWN',None
    if visible and control == 'constant_name': kind,profile = 'ROSTER_NAME',constant_profile
    if kind == 'MISSING_STAGE': outcome = 'MISSING_STAGE'
    elif not visible: outcome = 'NO_SAME_PANE_VISIBLE_HEADING_AND_CAPTION'
    elif kind != 'ROSTER_NAME': outcome = 'VISIBLE_'+kind
    elif not single: outcome = 'VISIBLE_NAME_UNRESOLVED_REFERENCE'
    elif category == 'OUTSIDE_AVAILABLE_PROFILE_REFERENCE': outcome = 'KNOWN_NAME_ON_OUTSIDE_AVAILABLE_REFERENCE'
    elif mapping[profile] == person: outcome = 'ESTIMATED_SUPPORT_CORRECT_AVAILABLE_NAME'
    else: outcome = 'ESTIMATED_SUPPORT_WRONG_AVAILABLE_NAME'
    return dict(reference_support=status,reference_category=category,heading_kind=kind,
        joint_visible=visible,outcome=outcome)


def summarize(rows):
    """Counts first; empty denominators have null rates, never perfect scores."""
    refs = Counter(r['reference_category'] for r in rows); outcomes = Counter(r['outcome'] for r in rows)
    visible = sum(r['joint_visible'] for r in rows); known = refs['AVAILABLE_PROFILE_REFERENCE']
    outside = refs['OUTSIDE_AVAILABLE_PROFILE_REFERENCE']; unknown = outcomes['VISIBLE_UNKNOWN']
    ratio = lambda a,b: a/b if b else None
    return dict(native_lexical_spans=len(rows),joint_visible_spans=visible,
        reference_category_counts=dict(refs),reference_support_counts=dict(Counter(r['reference_support'] for r in rows)),
        heading_kind_counts=dict(Counter(r['heading_kind'] for r in rows)),outcome_counts=dict(outcomes),
        single_available_reference_spans=known,single_outside_available_reference_spans=outside,
        unresolved_reference_spans=refs['UNRESOLVED_REFERENCE'],
        missing_stage=outcomes['MISSING_STAGE'],not_jointly_visible=outcomes['NO_SAME_PANE_VISIBLE_HEADING_AND_CAPTION'],
        rates=dict(estimated_correct_name_per_single_available_reference_span=ratio(outcomes['ESTIMATED_SUPPORT_CORRECT_AVAILABLE_NAME'],known),
            estimated_wrong_name_per_single_available_reference_span=ratio(outcomes['ESTIMATED_SUPPORT_WRONG_AVAILABLE_NAME'],known),
            known_name_per_single_outside_available_reference_span=ratio(outcomes['KNOWN_NAME_ON_OUTSIDE_AVAILABLE_REFERENCE'],outside),
            visible_Unknown_per_native_lexical_span=ratio(unknown,len(rows)),
            visible_Unknown_per_joint_visible_span=ratio(unknown,visible)))


def project(joined, observed, *, checkpoint=None):
    """Internal pure seam. score_cell performs the admitted reference join first."""
    require(joined['status'] == 'JOINED_OBSERVED_HEADINGS_TO_EVALUATOR_REFERENCE_ONLY'
        and joined['observed_review_sha256'] == fingerprint(observed), 'Name/reference observation binding differs')
    labels = observed['labels']; spans = observed['observed']['timing']['spans']
    support = joined['native_span_reference_support']; mapping = joined['profile_to_identity']
    require(len(spans) <= MAX_SPANS and set(spans) == set(labels['spans']) == set(support), 'Exact bounded naming span population required')
    require(type(mapping) is dict and len(mapping) <= 256 and len(set(mapping.values())) == len(mapping)
        and all(type(k) is str and type(v) is str and k and v for k,v in mapping.items()), 'Unique bounded fixed identity mapping required')
    constant = sorted(mapping)[0] if mapping else None
    lexical = [s for s,v in spans.items() if v['kind'] == 'lexical_word']
    empty = [s for s,v in spans.items() if v['kind'] == 'empty_caption']
    require(len(lexical)+len(empty) == len(spans) and all(support[s]['status'] == 'NOT_A_LEXICAL_WORD' for s in empty)
        and all(support[s]['status'] != 'NOT_A_LEXICAL_WORD' for s in lexical), 'Lexical/empty reference population differs')
    scenarios = {name:{} for name in ('observed','all_unknown','constant_name') if name != 'constant_name' or constant is not None}
    conflicts = {}; revisions = {}
    for stage in STAGES:
        buckets = {name:{pane:[] for pane in PANES} for name in scenarios}
        conflict = differing = 0
        for sid in lexical:
            if checkpoint: checkpoint()
            key = labels['spans'][sid][stage]; state = labels['states'].get(key) if key is not None else None
            require(key is None or state is not None and sid in state['span_ids'], 'Missing or foreign observed name state')
            panes = {p:None for p in PANES} if state is None else state['labels']['panes']
            require(set(panes) == set(PANES), 'Exact pane population required')
            if state is not None:
                visible_names = {p['roster_profile_id'] for p in panes.values()
                    if p['kind'] == 'ROSTER_NAME' and p['heading_and_caption_glyphs_visible_in_same_pane']}
                conflict += len(visible_names) > 1
                differing += len({p['applied_text'] for p in panes.values() if p['kind'] != 'ABSENT'}) > 1
            for name in scenarios:
                for pane in PANES:
                    buckets[name][pane].append(classify(support[sid],panes[pane],mapping,
                        control=None if name == 'observed' else name,constant_profile=constant))
        for name in scenarios: scenarios[name][stage] = {p:summarize(rows) for p,rows in buckets[name].items()}
        conflicts[stage] = dict(native_lexical_spans=len(lexical),conflicting_visible_roster_names=conflict,
            differing_applied_pane_headings=differing,panes_combined_into_one_identity=False)
    for key in ('observed_heading_changes','observed_visible_heading_changes'):
        values = [labels['spans'][sid][key] for sid in lexical]
        require(all(v is None or type(v) is int and v >= 0 for v in values), 'Invalid recorded revision count')
        revisions[key] = dict(sum_over_native_spans=sum(v for v in values if v is not None),
            spans_with_recorded_count=sum(v is not None for v in values),spans_without_recorded_count=sum(v is None for v in values))
    return dict(status='SCORED_ESTIMATED_SUPPORT_NAME_DIAGNOSTICS_ONLY',job_id=joined['job_id'],
        reference_class=joined['reference_class'],observed_review_sha256=fingerprint(observed),
        reference_join_sha256=fingerprint(joined),native_spans=len(spans),native_lexical_spans=len(lexical),
        empty_caption_spans_excluded=len(empty),scenarios=scenarios,pane_conflicts=conflicts,
        revision_counts=revisions,constant_control_profile_id=constant,
        constant_control_status='CONDITIONAL_DIAGNOSTIC' if constant is not None else 'UNAVAILABLE_NO_AVAILABLE_PROFILE',
        constant_selection='Lexicographically first fixed available profile ID; never chosen using reference accuracy',
        control_opportunities='Replace only jointly visible observed pane opportunities; retain missing/offscreen/suppressed geometry; no actual control GUI run',
        counting_unit='Native lexical span at a requested stage in each pane, including retired hypotheses; not reference words or speech duration',
        roster=joined['roster'],outside_available_is_genuine_outsider=False,
        exact_word_identity_established=False,complete_heading_glyph_visibility_proven=False,
        individual_word_glyph_visibility_proven=False,naming_accuracy_qualified=False,
        acquisition_latency_qualified=False,continuous_wrong_name_exposure_measured=False,
        returning_person_consistency_qualified=False,known_track_fragmentation_qualified=False,
        complete_panel_reviewed=False,integrated_N4_cells=0,N4_accepted=False)


def score_cell(context, observed, payload, *, checkpoint=None):
    joined = join_observed(context,observed,payload,checkpoint=checkpoint)
    return project(joined,observed,checkpoint=checkpoint)
