"""Evaluator-only identity/reference joins. See README_NAMING_REFERENCE.md."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import uuid

from common import audio_only, fingerprint, load, verify
from review_scoring_bank import require
from viewport_ledger_v2 import finite

HERE = Path(__file__).resolve().parent
MAX_INPUT_BYTES = 8*1024**2
EXPECTED_CLASSES = {'complete_nonoverlap':312, 'complete_overlap':94,
                    'incomplete_ambient_reference':52, 'empty_control':22}


def profile_id(identity):
    require(type(identity) is str and 0 < len(identity) <= 256, 'Bounded reference identity required')
    return str(uuid.uuid5(uuid.NAMESPACE_URL, 'just-peachy:N2:research:'+identity))


def gallery_identities(document, windows, windows_binding):
    """Recover identity only from accepted E provenance, not display spelling."""
    require(document['research_only'] is True and document['domain'] == 'clean_source'
        and document['duration_sec'] == 15 and document['mode'] == 'open', 'Primary research gallery required')
    require(windows['schema'] == 'n2-identical-encoder-windows-v1', 'Unknown E-window manifest')
    by_id = {w['window_id']:w for w in windows['windows']}
    templates = {t['template_id']:t for t in windows['gallery_templates']}
    require(len(by_id) == len(windows['windows']) and len(templates) == len(windows['gallery_templates']),
        'Duplicate E window/template ID')
    require(len(document['profiles']) <= 256, 'Bounded research gallery required')
    result = {}; people = []
    for p in document['profiles']:
        prov = p['provenance']; ids = prov['window_ids']
        require(prov['window_manifest_sha256'] == windows_binding['sha256'] and type(ids) is list
            and 0 < len(ids) <= 256 and len(set(ids)) == len(ids) and all(i in by_id for i in ids),
            'Unbound or repeated E provenance windows')
        selected = [by_id[i] for i in ids]; identities = {w['identity'] for w in selected}
        require(len(identities) == 1 and all(w['role'] == 'E' and w['domain'] == 'clean_source' for w in selected),
            'Profile provenance contains non-E or mixed identities')
        identity = next(iter(identities)); template = templates.get(prov['template_id'])
        require(template is not None and template['status'] == 'AVAILABLE' and template['identity'] == identity
            and template['domain'] == 'clean_source' and template['requested_active_seconds'] == 15
            and template['window_ids'] == ids and template['source_ids'] == prov['source_ids']
            and prov['source_ids'] == [w['source_id'] for w in selected], 'E template/source provenance differs')
        require(p['profile_id'] == profile_id(identity) and p['name'] == 'Research '+p['profile_id'][:8]
            and p['profile_id'] not in result, 'Research UUID/display identity differs')
        result[p['profile_id']] = identity; people.append(dict(id=p['profile_id'], name=p['name']))
    require(len(result) == document['available_size']
        and document['intended_size'] == document['available_size']+document['unavailable_count'],
        'Research gallery denominators differ')
    return dict(profile_to_identity=result, people=people, available_size=document['available_size'],
        intended_size=document['intended_size'], unavailable_count=document['unavailable_count'],
        membership_scope='Actual available clean E roster; outside this roster includes intended members lacking usable E',
        vectors_numerically_used=False, calibration_fitted=False)


def validate_population(truth, manifest):
    require(manifest['schema'] == 'n4-audio-only-v1', 'Admitted N4 audio manifest required')
    require(truth['schema'] == 'n2-private-evaluator-only-v1' and truth['NEVER_PASS_TO_RUNTIME'] is True,
        'Evaluator-only reference contract required')
    jobs = {j['job_id']:audio_only(j) for j in manifest['jobs']}; cells = {c['job_id']:c for c in truth['cells']}
    require(len(jobs) == len(manifest['jobs']) == len(cells) == len(truth['cells']) == 480
        and set(jobs) == set(cells), 'Exact 480-job truth/audio population required')
    require(dict(Counter(c['reference_class'] for c in cells.values())) == EXPECTED_CLASSES,
        'Reference-class population differs')
    cases = {}; identities = set(); total_turns = 0
    for jid, cell in cells.items():
        job = jobs[jid]; turns = cell['turns']
        require(cell['frames'] == job['frames'] and cell['tap'] == job['tap']
            and jid == 'N2_'+cell['case_id']+'_'+cell['tap'] and cell['exact_word_timing'] == 'UNAVAILABLE'
            and type(cell['complete_reference']) is bool and cell['complete_reference'] is
                (cell['reference_class'] != 'incomplete_ambient_reference'), 'Reference/audio identity or authority differs')
        require(type(turns) is list and len(turns) <= 512 and len({t['turn_id'] for t in turns}) == len(turns),
            'Reference turn census differs')
        cases.setdefault(cell['case_id'], set()).add(cell['tap'])
        for t in turns:
            profile_id(t['identity']); identities.add(t['identity']); total_turns += 1
            require(t['word_times'] is None and type(t['transcript']) is str and len(t['transcript']) <= 65536,
                'Exact reference word timing or unbounded transcript is not admitted')
            intervals = t['activity_ranges_samples_estimated']
            require(type(intervals) is list and len(intervals) <= 4096 and all(type(r) is list and len(r) == 2
                and all(type(n) is int for n in r) and 0 <= r[0] < r[1] <= job['frames'] for r in intervals),
                'Invalid estimated reference activity; no clamping permitted')
            require(type(t['window_available']) is bool and (not t['window_available'] or (
                type(t['file_support_samples']) is list and len(t['file_support_samples']) == 2
                and all(type(n) is int for n in t['file_support_samples'])
                and 0 <= t['file_support_samples'][0] < t['file_support_samples'][1] <= job['frames'])),
                'Invalid whole-turn support availability')
    require(len(cases) == 240 and all(taps == {'O0','O1'} for taps in cases.values()), 'Reference pairs differ')
    return jobs, cells, dict(cells=480, scenes=240, turns=total_turns, identities=len(identities),
        reference_classes=EXPECTED_CLASSES, exact_reference_word_times_available=False)


def build_context(inputs, *, checkpoint=None):
    """Read only fixed bindings from a qualified caller/admission, never models."""
    required = {'accepted_n2','accepted_screen','scoring_qualification','scoring_admission',
        'preparation','manifest','truth','windows','gallery_preparation','application_context'}
    require(set(inputs) == required, 'Exact evaluator reference input set required')
    values = {}
    for key, b in inputs.items():
        if checkpoint: checkpoint()
        require(type(b['bytes']) is int and 0 < b['bytes'] <= MAX_INPUT_BYTES, 'Reference input exceeds bound')
        verify(b); values[key] = load(b['path'])
    accepted = values['accepted_n2']; screen = values['accepted_screen']; sq = values['scoring_qualification']
    require(accepted['status'] == 'ACCEPTED_FOR_NEXT_STAGE_WITH_DECLARED_LIMITATIONS'
        and {k:inputs['accepted_screen'][k] for k in ('sha256','bytes')} == accepted['evidence']['evaluation/SCREEN_SUMMARY.json']
        and screen['truth_sha256'] == inputs['truth']['sha256'], 'Accepted N2 reference binding differs')
    require(sq['status'] == 'PASS_SCORING_ADAPTER_DEVELOPMENT_ONLY' and sq['admission'] == inputs['scoring_admission']
        and values['scoring_admission']['truth'] == inputs['truth'], 'Established scorer reference differs')
    prep = values['preparation']; context = values['application_context']; gallery = values['gallery_preparation']
    require(prep['status'] == 'ACTUALLY_RUN_MODEL_FREE' and inputs['truth'] in prep['inputs']
        and inputs['manifest'] in prep['outputs'] and prep['waveform_files_verified'] == 480
        and prep['paired_physical_passes'] == 240, 'N4 preparation reference join differs')
    require(context['gallery_preparation'] == inputs['gallery_preparation'] and gallery['catalog'] == context['catalog']
        and gallery['status'] == 'PREPARED_VERIFIED_RESEARCH_GALLERIES_ONLY', 'Application gallery context differs')
    jobs, cells, counts = validate_population(values['truth'], values['manifest'])
    galleries = {}; evidence = list(inputs.values())
    for encoder in ('E0','E1'):
        if checkpoint: checkpoint()
        row = gallery['encoders'][encoder]['conditions']['open']; binding = row['condition']['gallery']
        require(0 < binding['bytes'] <= MAX_INPUT_BYTES, 'Gallery exceeds reference limit')
        verify(binding); document = load(binding['path'])
        info = gallery_identities(document, values['windows'], inputs['windows'])
        require(all(info[k] == row['condition'][k] for k in ('available_size','intended_size','unavailable_count')),
            'Runtime/evaluator roster population differs')
        galleries[encoder] = dict(**info, gallery=binding); evidence.append(binding)
    for b in evidence: verify(b)
    return dict(schema='n4-evaluator-naming-reference-v1', status='VERIFIED_REFERENCE_CONTEXT_ONLY',
        NEVER_PASS_TO_RUNTIME=True, inputs=deepcopy(inputs), jobs=jobs, truth_cells=cells, galleries=galleries,
        population=counts, evidence=evidence, models_loaded=0, audio_loaded=False,
        membership_from_accepted_E_provenance=True, exact_reference_word_times_available=False,
        naming_accuracy_qualified=False, integrated_N4_cells=0, N4_accepted=False)


def union_seconds(intervals):
    end = None; total = 0.
    for a, b in sorted(intervals):
        if end is None or a >= end: total += b-a; end = b
        elif b > end: total += b-end; end = b
    return total


def support(cell, start, end):
    """Describe positive intersections, never force a dominant-person label."""
    require(finite(start) and finite(end) and 0 <= start <= end, 'Finite ordered native source window required')
    result = dict(source_window_seconds=[start,end], reference_complete=cell['complete_reference'],
        exact_word_identity_established=False, eligible_as_exact_word_accuracy=False,
        reference_identities=[], estimated_activity_seconds_by_identity={}, any_estimated_activity_seconds=0.,
        single_intersecting_identity=None)
    if end > cell['frames']/16000:
        return dict(result, status='UNAVAILABLE_SOURCE_WINDOW_OUTSIDE_FILE')
    if end == start: return dict(result, status='UNAVAILABLE_ZERO_WIDTH_SOURCE_WINDOW')
    by_identity = {}
    for t in cell['turns']:
        for a, b in t['activity_ranges_samples_estimated']:
            x, y = max(start,a/16000), min(end,b/16000)
            if x < y: by_identity.setdefault(t['identity'], []).append([x,y])
    result.update(reference_identities=sorted(by_identity),
        estimated_activity_seconds_by_identity={i:union_seconds(rows) for i,rows in by_identity.items()},
        any_estimated_activity_seconds=union_seconds([r for rows in by_identity.values() for r in rows]))
    if not cell['complete_reference']: status = 'TARGET_ONLY_INCOMPLETE_REFERENCE'
    elif not by_identity: status = 'NO_ESTIMATED_REFERENCE_ACTIVITY'
    elif len(by_identity) > 1: status = 'MULTIPLE_INTERSECTING_REFERENCE_IDENTITIES'
    else:
        status = 'SINGLE_INTERSECTING_ESTIMATED_IDENTITY'; result['single_intersecting_identity'] = next(iter(by_identity))
    return dict(result, status=status)


def join_observed(context, observed, payload, *, checkpoint=None):
    require(context['status'] == 'VERIFIED_REFERENCE_CONTEXT_ONLY' and context['NEVER_PASS_TO_RUNTIME'] is True,
        'Admitted evaluator-only reference context required')
    require(observed['status'] == 'PASS_V2_APPLICATION_RECORDED_GUI_LABELS_ONLY'
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


def load_qualified_context(*, checkpoint=None):
    qualification = load(HERE/'NAMING_REFERENCE_CHECK_V1.json')
    require(qualification['status'] == 'PASS_EVALUATOR_NAMING_REFERENCE_DEVELOPMENT_ONLY', 'Reference helper not qualified')
    for b in qualification['code']: verify(b)
    return build_context(qualification['reference_inputs'], checkpoint=checkpoint)
