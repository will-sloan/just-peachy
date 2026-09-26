"""Explicit V3 caption, timing, heading and reference joins. See README_APPLICATION_SEMANTICS_V3.md."""
from copy import deepcopy
from pathlib import Path

from common import audio_only, bind, fingerprint, load, verify
from metric_process import exact_process
from naming_reference import MAX_INPUT_BYTES, build_context, support
from paced_panel_plan_v3 import application_qualification
from review_application_cell_v3 import review_cell as review_evidence
from review_application_content import fixed_roster
from review_application_labels import MAX_STATES, MAX_MEMBERSHIPS, interpret_row
from review_application_timing import project as project_timing
from review_application_transport_v3 import record
from review_native_captions import review as review_captions
from review_native_widget import review as review_widget
from review_scoring_bank import require
from score_observed_names import project as project_names
from viewport_ledger_v2 import read_row

HERE=Path(__file__).resolve().parent
OWN=('review_application_semantics_v3.py','test_application_semantics_v3.py',
     'probe_application_semantics_v3.py','README_APPLICATION_SEMANTICS_V3.md')


def code_bindings():
    entries=[bind(HERE/name) for name in OWN]
    prerequisites=(('APPLICATION_CELL_REVIEW_CHECK_V3.json','PASS_V3_APPLICATION_CELL_REVIEW_DEVELOPMENT_ONLY'),
        ('APPLICATION_LABEL_CHECK_V1.json','PASS_APPLICATION_RECORDED_HEADING_DEVELOPMENT_ONLY'),
        ('OBSERVED_NAME_SCORING_CHECK_V1.json','PASS_OBSERVED_NAME_DIAGNOSTIC_DEVELOPMENT_ONLY'))
    for name,status in prerequisites:
        q=load(HERE/name);require(q['status']==status,'Semantic prerequisite differs: '+name)
        verify(q['private_receipt']);proof=load(q['private_receipt']['path']);verify(proof['admission'])
        require(exact_process(load(proof['admission']['path'])['owner']) is None,'Prerequisite helper remains active')
        entries.extend([bind(HERE/name),*q['code']])
    result={}
    for b in entries:
        require(b['path'] not in result or result[b['path']]==b,'Conflicting semantic dependency');result[b['path']]=b
    return list(result.values())


def review_content(folder, *, checkpoint=None, **expected):
    """Caller must independently admit the full qualified V3 plan and population."""
    if checkpoint: checkpoint()
    qb, qualification, context = application_qualification()
    payload = expected['payload']
    for key in ('source_receipt','catalog','gallery_preparation','runtimes'):
        require(payload[key] == context[key], 'Payload differs from qualified application context: '+key)
    evidence_review = review_evidence(folder, checkpoint=checkpoint, **expected)
    require(evidence_review['status']=='PASS_V3_APPLICATION_CELL_EVIDENCE_JOINS_ONLY'
        and evidence_review['joins']['delivery_samples']==payload['job']['frames']
        and evidence_review['joins']['delivery_deadlines_accepted'] is False, 'V3 delivery cell join required')
    folder = Path(folder).resolve(strict=True)
    checked = {}
    viewport = evidence_review['observations']['viewport_review']
    for b in evidence_review['joins']['evidence']+[viewport['input'], viewport['evidence']]:
        require(b['path'] not in checked or checked[b['path']] == b, 'Evidence changed between cell readers')
        checked[b['path']] = b
    def read(relative):
        b, value = record(folder/relative, folder)
        require(checked.get(b['path']) == b, 'Semantic input was not checked by the cell reader')
        return value
    prepared = read('application/PREPARED.json'); snapshot = read('application/FINAL_SNAPSHOT.json')
    closure = read('application/ENGINE_CLOSURE.json')
    people, roster = fixed_roster(payload, prepared, snapshot, checkpoint=checkpoint)
    widget = review_widget(Path(closure['session']), job=payload['job'],
        expected_envelope=evidence_review['transport']['native_envelope_review'],
        viewport_summary=viewport['input'], source_receipt=payload['source_receipt'], people=people,
        mode=payload['contract']['mode'], checkpoint=checkpoint)
    for b in widget['evidence']:
        require(checked.get(b['path']) == b, 'Widget and cell evidence bindings differ')
    require(widget['people_sha256'] == roster['people_sha256'], 'Widget display roster changed')
    for b in list(checked.values())+roster['evidence']+[qb, qualification['application_context']]: verify(b)
    if checkpoint: checkpoint()
    return dict(status='PASS_V3_APPLICATION_CONTENT_AND_FIXED_ROSTER_JOINS_ONLY',
        cell=evidence_review, roster=roster, widget=widget, application_qualification=qb,
        source_context=qualification['application_context'],
        application_owner_and_primary_settings_joined=True, fixed_display_roster_independently_joined=True,
        primary_caption_text_consistency_reviewed=True, exact_consumed_event_attribution=False,
        complete_panel_reviewed=False, names_independently_scored=False, accuracy_qualified=False,
        source_to_widget_latency_qualified=False, controlled_resources_qualified=False,
        physical_scanout_measured=False, actual_continuity_test=False, stop_restart_qualified=False,
        deployment_tier='UNKNOWN', integrated_N4_cells=0, N4_accepted=False)


def review_timing(folder, *, checkpoint=None, **expected):
    """Compose independently admitted V3 cell/content with recorded timing facts."""
    content = review_content(folder, checkpoint=checkpoint, **expected)
    cell = content['cell']; registry = {}
    viewport = cell['observations']['viewport_review']
    for b in cell['joins']['evidence']+[viewport['input'], viewport['evidence']]+content['roster']['evidence']:
        require(b['path'] not in registry or registry[b['path']] == b, 'Timing evidence binding conflicts')
        registry[b['path']] = b; verify(b)
    closure_path = str((Path(folder)/'application/ENGINE_CLOSURE.json').resolve(strict=True))
    require(closure_path in registry, 'Unjoined timing source closure')
    closure = load(closure_path); envelope = cell['transport']['native_envelope_review']
    native = review_captions(Path(closure['session']), job=expected['payload']['job'],
        expected_envelope=envelope, checkpoint=checkpoint)
    for b in native['evidence']:
        require(registry.get(b['path']) == b, 'Native timing bindings differ from cell')
    origin = envelope['source_start']['source_epoch_monotonic_sec']
    require(viewport['source_origin_monotonic_sec'] == origin, 'Source/viewport clock origin differs')
    result = project_timing(native, content['widget'], origin=origin, log=viewport['evidence'], checkpoint=checkpoint)
    for b in list(registry.values())+[content['application_qualification'], content['source_context']]: verify(b)
    return dict(status='PASS_V3_APPLICATION_RECORDED_ROW_TIMING_ONLY', content=content, timing=result,
        content_review_sha256=fingerprint(content), evidence=list(registry.values()),
        point_observation_arithmetic_reviewed=True, individual_word_glyph_visibility_proven=False,
        exact_consumed_event_attribution=False, source_to_widget_latency_qualified=False,
        continuous_exposure_measured=False, physical_scanout_measured=False, complete_panel_reviewed=False,
        names_independently_scored=False, controlled_resources_qualified=False,
        actual_continuity_test=False, stop_restart_qualified=False, deployment_tier='UNKNOWN',
        integrated_N4_cells=0, N4_accepted=False)


def project_labels(content, *, people, log, checkpoint=None):
    """Internal projection. Production review reconstructs roster and cell first."""
    require(content['status'] == 'PASS_V3_APPLICATION_CONTENT_AND_FIXED_ROSTER_JOINS_ONLY'
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


def review_labels(folder, *, checkpoint=None, **expected):
    checked = review_timing(folder, checkpoint=checkpoint, **expected); content = checked['content']
    bindings = {b['path']:b for b in checked['evidence']}
    snapshot_path = str((Path(folder)/'application/FINAL_SNAPSHOT.json').resolve(strict=True))
    require(snapshot_path in bindings, 'Heading roster snapshot was not joined')
    verify(bindings[snapshot_path]); people = load(snapshot_path)['people']
    log = content['cell']['observations']['viewport_review']['evidence']
    projected = project_labels(content, people=people, log=log, checkpoint=checkpoint)
    # Source-bound parser context: no re-execution of the stateful GUI labeler.
    source_binding = content['widget']['source_receipt']; verify(source_binding); source = load(source_binding['path'])
    source_files = [dict(path=str(Path(source['prototype'])/name), **source['files'][name])
        for name in ('app/caption_display.py', 'app/ui.py')]
    for b in list(bindings.values())+source_files: verify(b)
    return dict(status='PASS_V3_APPLICATION_RECORDED_GUI_LABELS_ONLY', observed=checked,
        labels=projected, timing_review_sha256=fingerprint(checked), display_policy_source=source_files,
        evidence=list(bindings.values()), evaluator_truth_loaded=False,
        inherited_suppressed_heading_inferred=False, naming_accuracy_qualified=False,
        complete_panel_reviewed=False, controlled_resources_qualified=False,
        actual_continuity_test=False, stop_restart_qualified=False, deployment_tier='UNKNOWN',
        integrated_N4_cells=0, N4_accepted=False)


def join_observed(context, observed, payload, *, checkpoint=None):
    require(context['status'] == 'VERIFIED_REFERENCE_CONTEXT_ONLY' and context['NEVER_PASS_TO_RUNTIME'] is True,
        'Admitted evaluator-only reference context required')
    require(observed['status'] == 'PASS_V3_APPLICATION_RECORDED_GUI_LABELS_ONLY'
        and observed['evaluator_truth_loaded'] is False and observed['N4_accepted'] is False,
        'Independent observed-heading review required')
    content = observed['observed']['content']; transport = content['cell']['transport']
    inputs = [b for b in transport['evidence'] if Path(b['path']).name == 'INPUT.json']
    require(len(inputs) == 1 and 0 < inputs[0]['bytes'] <= MAX_INPUT_BYTES, 'One bounded observed input required')
    verify(inputs[0]); actual_payload = load(inputs[0]['path'])
    require(fingerprint(actual_payload) == fingerprint(payload) and payload['cell_id'] == transport['cell_id'],
        'Reference payload differs from the independently observed cell input')
    job = payload['job']; contract = payload['contract']
    require(context['jobs'].get(job['job_id']) == audio_only(job)
        and payload['gallery_preparation'] == context['inputs']['gallery_preparation']
        and content['source_context'] == context['inputs']['application_context']
        and contract['mode'] == 'open_with_names' and contract['gallery_condition'] == 'open'
        and contract['adaptation'] is False, 'Observed job/gallery/context differs from reference')
    gallery = context['galleries'][contract['encoder']]
    people = gallery['people'] if contract['uses_n2'] else sorted(gallery['people'],key=lambda p:p['name'])
    require(content['roster']['people_sha256'] == fingerprint(people), 'Observed/reference roster ordering differs')
    cell = context['truth_cells'][job['job_id']]; present = set(gallery['profile_to_identity'].values())
    spans = observed['observed']['timing']['spans']; descriptions = {}
    require(set(spans) == set(observed['labels']['spans']), 'Observed naming/timing span census differs')
    for sid, span in spans.items():
        if checkpoint: checkpoint()
        descriptions[sid] = (support(cell,*span['source_window_seconds']) if span['kind'] == 'lexical_word'
            else dict(status='NOT_A_LEXICAL_WORD', exact_word_identity_established=False))
    for b in context['evidence']+observed['evidence']: verify(b)
    return dict(status='JOINED_OBSERVED_HEADINGS_TO_EVALUATOR_REFERENCE_ONLY', NEVER_PASS_TO_RUNTIME=True,
        job_id=job['job_id'], reference_class=cell['reference_class'], reference_complete=cell['complete_reference'],
        context_sha256=fingerprint(context), observed_review_sha256=fingerprint(observed),
        truth_cell_sha256=fingerprint(cell), profile_to_identity=deepcopy(gallery['profile_to_identity']),
        reference_turns=len(cell['turns']), available_roster_turns=sum(t['identity'] in present for t in cell['turns']),
        outside_available_roster_turns=sum(t['identity'] not in present for t in cell['turns']),
        roster={k:gallery[k] for k in ('available_size','intended_size','unavailable_count','membership_scope')},
        native_span_reference_support=descriptions, exact_reference_word_times_available=False,
        naming_accuracy_qualified=False, acquisition_latency_qualified=False,
        continuous_wrong_name_exposure_measured=False, complete_panel_reviewed=False,
        integrated_N4_cells=0, N4_accepted=False)


def migrate_reference_inputs(old_inputs, old, current, context_binding):
    """Allow an identical gallery manifest at its new qualified context path."""
    require(old_inputs['gallery_preparation']==old['gallery_preparation'], 'Prior reference gallery context differs')
    for key in ('source_receipt','catalog','runtimes'):
        require(old[key]==current[key],'Reference context migration changed '+key)
    previous=old['gallery_preparation'];next_binding=current['gallery_preparation']
    verify(previous);verify(next_binding)
    require(all(previous[k]==next_binding[k] for k in ('sha256','bytes')),
        'Reference context migration changed gallery content')
    return dict(old_inputs,application_context=context_binding,gallery_preparation=next_binding)


def load_reference_context(*, checkpoint=None):
    """Rebuild evaluator context with unchanged gallery bytes and model/source inputs."""
    q=load(HERE/'NAMING_REFERENCE_CHECK_V1.json')
    require(q['status']=='PASS_EVALUATOR_NAMING_REFERENCE_DEVELOPMENT_ONLY','Reference prerequisite differs')
    for b in q['code']:verify(b)
    old_inputs=deepcopy(q['reference_inputs']);verify(old_inputs['application_context'])
    old=load(old_inputs['application_context']['path'])
    qb,app,current=application_qualification()
    inputs=migrate_reference_inputs(old_inputs,old,current,app['application_context'])
    result=build_context(inputs,checkpoint=checkpoint)
    verify(old_inputs['application_context']);verify(qb);verify(app['application_context'])
    return result


def score_cell(context, observed, payload, *, checkpoint=None):
    """Evaluator only; no observed result becomes exact-word naming accuracy."""
    joined=join_observed(context,observed,payload,checkpoint=checkpoint)
    return project_names(joined,observed,checkpoint=checkpoint)
