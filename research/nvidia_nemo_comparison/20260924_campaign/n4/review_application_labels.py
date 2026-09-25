"""Interpret recorded GUI headings; never infer identity truth. See its README."""
from copy import deepcopy
from pathlib import Path
import re

from common import fingerprint, load, verify
from review_application_timing import review_cell as review_timing
from review_scoring_bank import require
from viewport_ledger_v2 import read_row

MAX_STATES = 32768
MAX_MEMBERSHIPS = 262144
PENDING = '••• · collecting voice'
UNKNOWN = ('Unknown', 'Unknown · voice unavailable')


def label_kind(text, people):
    """Classify an exact applied string, retaining ambiguity and forced labels."""
    require(type(text) is str and len(text) <= 1024, 'Bounded recorded heading required')
    exact = [p['id'] for p in people if p['name'] == text]
    reserved = text == '' or text in UNKNOWN or text == PENDING or text == 'Transcription'
    anonymous = re.fullmatch(r'Speaker[ _-]*[0-9]+', text, flags=re.IGNORECASE) is not None
    forced = [p['id'] for p in people if p['name']+' · assumed' == text]
    require(len(exact) <= 1 and len(forced) <= 1, 'Ambiguous duplicate display roster')
    if exact and (reserved or anonymous or forced):
        kind = 'AMBIGUOUS_RESERVED_ROSTER_NAME'; person = None
    elif exact: kind = 'ROSTER_NAME'; person = exact[0]
    elif forced: kind = 'FORCED_ROSTER_ASSUMPTION'; person = forced[0]
    elif text == '': kind = 'SUPPRESSED'; person = None
    elif text in UNKNOWN: kind = 'UNKNOWN'; person = None
    elif text == PENDING: kind = 'PENDING'; person = None
    elif anonymous: kind = 'ANONYMOUS'; person = None
    elif text == 'Transcription': kind = 'TRANSCRIPTION'; person = None
    else: kind = 'UNRECOGNIZED'; person = None
    return dict(kind=kind, roster_profile_id=person, applied_text=text,
        identity_correctness_established=False, forced_choice=kind == 'FORCED_ROSTER_ASSUMPTION')


def interpret_row(row, people):
    """Keep panes independent. Suppression never inherits an unrecorded label."""
    require(set(row['panes']) == {'active', 'history'}, 'Exactly two observed panes required')
    panes = {}
    for name, pane in row['panes'].items():
        if not pane['present_in_widget']:
            require(not pane['caption_visible'] and not pane['heading_visible'], 'Absent pane claims visibility')
            panes[name] = dict(kind='ABSENT', roster_profile_id=None, applied_text=None,
                identity_correctness_established=False, forced_choice=False,
                any_heading_glyphs_visible=False, any_caption_glyphs_visible=False,
                heading_and_caption_glyphs_visible_in_same_pane=False, native_profile_agrees=None)
            continue
        interpreted = label_kind(pane['applied_heading_text'], people)
        heading = pane['heading_visible']; caption = pane['caption_visible']
        require(type(heading) is bool and type(caption) is bool, 'Boolean pane visibility required')
        require(interpreted['kind'] != 'SUPPRESSED' or heading is False, 'Suppressed heading claims glyph visibility')
        native = row['display_profile_id'] if interpreted['forced_choice'] else row['verified_profile_id']
        panes[name] = dict(**interpreted, any_heading_glyphs_visible=heading,
            any_caption_glyphs_visible=caption, heading_and_caption_glyphs_visible_in_same_pane=heading and caption,
            native_profile_agrees=(native == interpreted['roster_profile_id']
                if interpreted['kind'] in ('ROSTER_NAME', 'FORCED_ROSTER_ASSUMPTION') else None),
            heading_geometry=deepcopy(pane.get('heading_viewport')),
            individual_word_glyph_visibility_proven=False, complete_heading_glyph_visibility_proven=False)
    present = [p for p in panes.values() if p['kind'] != 'ABSENT']
    visible = [p for p in present if p['heading_and_caption_glyphs_visible_in_same_pane']]
    names = sorted({p['roster_profile_id'] for p in visible if p['kind'] == 'ROSTER_NAME'})
    return dict(panes=panes, native_verified_profile_id=row['verified_profile_id'],
        native_display_profile_id=row['display_profile_id'], native_naming_state=row['naming_state'],
        native_identity_assignment=deepcopy(row['identity_assignment']),
        same_pane_visible_roster_profile_ids=names, conflicting_visible_roster_names=len(names) > 1,
        applied_pane_headings_differ=len({p['applied_text'] for p in present}) > 1,
        any_same_pane_heading_and_caption_glyphs_visible=bool(visible),
        any_forced_assumption=any(p['forced_choice'] for p in present),
        any_unrecognized_or_ambiguous=any(p['kind'] in ('UNRECOGNIZED', 'AMBIGUOUS_RESERVED_ROSTER_NAME') for p in present),
        recorded_name_native_profile_disagreements=sum(p['native_profile_agrees'] is False for p in present),
        inherited_suppressed_heading_inferred=False, single_identity_selected=False,
        identity_correctness_established=False)


def project(content, *, people, log, checkpoint=None):
    """Internal projection. Production review reconstructs roster and cell first."""
    require(content['status'] == 'PASS_V2_APPLICATION_CONTENT_AND_FIXED_ROSTER_JOINS_ONLY'
        and content['fixed_display_roster_independently_joined'] is True
        and fingerprint(people) == content['roster']['people_sha256'] == content['widget']['people_sha256'],
        'Independently joined display roster required')
    require(type(people) is list and len(people) <= 256 and all(type(p) is dict and set(p) == {'id','name'}
        and all(type(p[k]) is str and 0 < len(p[k]) <= 128 for k in ('id','name')) for p in people)
        and len({p['id'] for p in people}) == len(people) and len({p['name'] for p in people}) == len(people),
        'Bounded unique display roster required')
    viewport = content['cell']['observations']['viewport_review']; widget = content['widget']
    require(log == viewport['evidence'], 'Unjoined heading log')
    verify(log); cache = {}; states = {}; memberships = 0
    def observe(joined):
        nonlocal memberships
        if checkpoint: checkpoint()
        key = fingerprint(joined)
        if key in states: return key
        require(len(states) < MAX_STATES, 'Heading state count exceeds bound')
        ref = joined['row_ref']; rk = fingerprint(ref)
        if rk not in cache: cache[rk] = read_row(log['path'], ref)
        row = cache[rk]; memberships += len(row['span_ids'])
        require(memberships <= MAX_MEMBERSHIPS, 'Heading membership budget exceeded')
        require(row['row_id'] == joined['row_id'] and row['caption_visible'] == joined['caption_visible']
            and row['heading_visible'] == joined['heading_visible']
            and row.get('removed_from_controller', False) == joined['retired']
            and {k:p.get('applied_heading_text') for k,p in row['panes'].items()} == joined['recorded_headings'],
            'Recorded heading state changed between readers')
        states[key] = dict(row_ref=deepcopy(ref), row_id=row['row_id'], span_ids=list(row['span_ids']),
            observed_monotonic_sec=joined['observed_monotonic_sec'], retired=joined['retired'],
            caption_final=row['final'], native_candidates=joined['compatible_publications'],
            exact_consumed_event_attribution=False, labels=interpret_row(row, people))
        return key
    changes = [observe(change) for change in widget['changed_rows']]
    spans = {}
    for sid, original in widget['spans'].items():
        result = {}
        for kind in ('first_visible', 'first_final_visible', 'latest'):
            key = original[kind]
            if key is None: result[kind] = None; continue
            state = observe(widget['states'][key])
            require(sid in states[state]['span_ids'], 'Heading state no longer contains span')
            result[kind] = state
        result.update(observed_heading_changes=original['observed_heading_changes'],
            observed_visible_heading_changes=original['observed_visible_heading_changes'])
        spans[sid] = result
    for sid in widget['native_spans_not_observed']:
        require(sid not in spans, 'Heading missing population overlaps observed spans')
        spans[sid] = dict(first_visible=None, first_final_visible=None, latest=None,
            observed_heading_changes=None, observed_visible_heading_changes=None)
    require(len(spans) == widget['native_span_population'], 'Heading population changed')
    counts = {}
    for kind in ('first_visible', 'first_final_visible', 'latest'):
        chosen = [states[s[kind]]['labels'] for s in spans.values() if s[kind] is not None]
        counts[kind] = dict(native_spans=len(spans), sampled_spans=len(chosen), missing_stage=len(spans)-len(chosen),
            no_same_pane_heading_and_caption_visibility=sum(not r['any_same_pane_heading_and_caption_glyphs_visible'] for r in chosen),
            conflicting_visible_roster_names=sum(r['conflicting_visible_roster_names'] for r in chosen),
            unrecognized_or_ambiguous_heading=sum(r['any_unrecognized_or_ambiguous'] for r in chosen),
            forced_assumption=sum(r['any_forced_assumption'] for r in chosen),
            name_native_profile_disagreement=sum(r['recorded_name_native_profile_disagreements'] > 0 for r in chosen))
    verify(log)
    return dict(status='PASS_RECORDED_GUI_HEADING_INTERPRETATION_ONLY', people_sha256=fingerprint(people),
        widget_review_sha256=fingerprint(widget), changed_row_states=changes, states=states, spans=spans, counts=counts,
        counting_unit='native span per requested observation stage, including retired revisions and empty-caption IDs; not reference words or speech duration',
        evaluator_truth_loaded=False, inherited_suppressed_heading_inferred=False,
        exact_gui_identity_hysteresis_replayed=False, exact_consumed_event_attribution=False,
        complete_heading_glyph_visibility_proven=False, individual_word_glyph_visibility_proven=False,
        naming_accuracy_qualified=False, continuous_wrong_name_exposure_measured=False,
        acquisition_latency_qualified=False, source_to_widget_latency_qualified=False,
        complete_panel_reviewed=False, integrated_N4_cells=0, N4_accepted=False)


def review_cell(folder, *, checkpoint=None, **expected):
    checked = review_timing(folder, checkpoint=checkpoint, **expected); content = checked['content']
    bindings = {b['path']:b for b in checked['evidence']}
    snapshot_path = str((Path(folder)/'application/FINAL_SNAPSHOT.json').resolve(strict=True))
    require(snapshot_path in bindings, 'Heading roster snapshot was not joined')
    verify(bindings[snapshot_path]); people = load(snapshot_path)['people']
    log = content['cell']['observations']['viewport_review']['evidence']
    projected = project(content, people=people, log=log, checkpoint=checkpoint)
    # Source-bound parser context: no re-execution of the stateful GUI labeler.
    source_binding = content['widget']['source_receipt']; verify(source_binding); source = load(source_binding['path'])
    source_files = [dict(path=str(Path(source['prototype'])/name), **source['files'][name])
        for name in ('app/caption_display.py', 'app/ui.py')]
    for b in list(bindings.values())+source_files: verify(b)
    return dict(status='PASS_V2_APPLICATION_RECORDED_GUI_LABELS_ONLY', observed=checked,
        labels=projected, timing_review_sha256=fingerprint(checked), display_policy_source=source_files,
        evidence=list(bindings.values()), evaluator_truth_loaded=False,
        inherited_suppressed_heading_inferred=False, naming_accuracy_qualified=False,
        complete_panel_reviewed=False, controlled_resources_qualified=False,
        actual_continuity_test=False, stop_restart_qualified=False, deployment_tier='UNKNOWN',
        integrated_N4_cells=0, N4_accepted=False)
