"""Compose V2 cell, fixed roster and caption/widget review. See its README."""
from pathlib import Path

from common import bind, fingerprint, load, verify
from mode_galleries import REJECT_GATE
from paced_child_admission import assert_plain_path
from paced_panel_plan_v2 import application_qualification
from review_application_cell_v2 import review_cell as review_evidence
from review_application_transport_v2 import record
from review_native_widget import review as review_widget
from review_scoring_bank import require


def fixed_roster(payload, prepared, snapshot, *, checkpoint=None):
    """Read only the admitted research gallery; do not load a model or vectors.

    The production composition first proves this payload belongs to the fixed
    qualified application context. This helper alone cannot admit that context.
    """
    contract = payload['contract']
    require(contract['mode'] == 'open_with_names' and contract['gallery_condition'] == 'open'
        and contract['adaptation'] is False, 'Primary open fixed-roster contract required')
    evidence = []
    def read(binding, limit):
        require(type(binding['bytes']) is int and 0 < binding['bytes'] <= limit, 'Roster input exceeds bound')
        verify(binding); value = load(binding['path']); evidence.append(binding); return value
    galleries = read(payload['gallery_preparation'], 1024**2)
    require(galleries['status'] == 'PREPARED_VERIFIED_RESEARCH_GALLERIES_ONLY'
        and galleries['catalog'] == payload['catalog'], 'Fixed gallery catalog differs')
    row = galleries['encoders'][contract['encoder']]['conditions']['open']; condition = row['condition']
    require(prepared['gallery_condition'] == condition and prepared['selected_ids'] == []
        and condition['mode'] == 'open' and condition['domain'] == 'clean_source'
        and condition['tier_seconds'] == 15 and condition['matched_duration_diagnostic'] is False,
        'Prepared primary gallery condition differs')
    document = read(condition['gallery'], 8*1024**2)
    require(document['namespace'] == row['namespace'] and document['calibration']['status'] == REJECT_GATE
        and document['research_only'] is True, 'Gallery namespace or unqualified gate changed')
    profiles = document['profiles']
    require(type(profiles) is list and len(profiles) <= 256, 'Bounded roster required')
    people = [dict(id=p['profile_id'], name=p['name']) for p in profiles]
    require(all(type(p[k]) is str and 0 < len(p[k]) <= 128 for p in people for k in ('id','name'))
        and len({p['id'] for p in people}) == len(people) and len({p['name'] for p in people}) == len(people),
        'Roster IDs and names must be unique bounded strings')
    require(all(type(condition[k]) is int and condition[k] >= 0
        for k in ('available_size','intended_size','unavailable_count'))
        and condition['available_size'] == len(people)
        and condition['intended_size'] == len(people)+condition['unavailable_count'], 'Roster denominators differ')
    if not contract['uses_n2']:
        require(contract['encoder'] == 'E0', 'Baseline roster must retain its original encoder')
        manifest = read(row['baseline_manifest'], 1024**2)
        require(manifest['schema_version'] == 'edge-research-gallery.v1'
            and manifest['backend_sha256'] == row['namespace']['model_sha256']
            and manifest['provenance_binding'] == condition['gallery'], 'Baseline roster provenance differs')
        declared = manifest['profiles']; root = Path(row['baseline_manifest']['path']).parent
        profile_root = assert_plain_path(manifest['profile_root'], root)
        require(profile_root == root/'profiles' and type(declared) is list and len(declared) == len(people),
            'Baseline roster root or population differs')
        actual = [dict(id=p['profile_id'], name=p['display_name']) for p in declared]
        require(sorted(actual, key=lambda p:p['id']) == sorted(people, key=lambda p:p['id']),
            'Baseline and published display rosters differ')
        metadata_paths = set()
        for p in declared:
            if checkpoint: checkpoint()
            mp = assert_plain_path(p['metadata']['path'], profile_root)
            vp = assert_plain_path(p['vector']['path'], profile_root)
            require(mp.parent == profile_root and mp.name == p['profile_id']+'.json'
                and vp == mp.with_suffix('.npy'), 'Baseline profile paths differ')
            metadata = read(p['metadata'], 64*1024)
            require(metadata['profile_id'] == p['profile_id'] and metadata['display_name'] == p['display_name']
                and metadata['backend_id'] == 'redimnet2_b2_fp32'
                and metadata['backend_sha256'] == manifest['backend_sha256'], 'Baseline display metadata differs')
            require(type(p['vector']['bytes']) is int and 0 < p['vector']['bytes'] <= 64*1024,
                'Baseline vector binding exceeds bound')
            verify(p['vector']); evidence.append(p['vector']); metadata_paths.add(mp)
        require({p.resolve() for p in profile_root.glob('*.json')} == metadata_paths,
            'Baseline profile metadata population changed')
        # The unchanged ResearchGallery sorts by name; N2Gallery preserves rows.
        people = sorted(people, key=lambda p:p['name'])
    require(fingerprint(snapshot['people']) == fingerprint(people)
        and fingerprint(snapshot['roster_compatibility']) == fingerprint(people),
        'Observed display roster differs from its prepared gallery')
    require(snapshot['mode'] == 'open_with_names' and snapshot['selected_ids'] == [] and snapshot['strict'] is False
        and snapshot['text_assistance']['enabled'] is False
        and not snapshot['settings'].get('text_assistance', False)
        and not snapshot['settings'].get('text_aware_references', False)
        and snapshot['reference_comparison'] is None, 'Observed primary display settings differ')
    require(all(r.get('manual_edit') is None and r.get('show_corrected_text') is False
        for r in snapshot['rows']), 'Primary final rows contain manual or optional corrections')
    for b in evidence: verify(b)
    return people, dict(people_sha256=fingerprint(people), available_size=len(people),
        intended_size=condition['intended_size'], unavailable_count=condition['unavailable_count'],
        ordering='document_profile_order' if contract['uses_n2'] else 'baseline_sorted_display_name',
        evidence=evidence, vectors_loaded=False, names_are_evaluator_truth=False,
        scope='Prepared fixed display roster joined to the stopped Controller snapshot; no recognition accuracy claim')


def review_cell(folder, *, checkpoint=None, **expected):
    """Caller must independently admit the full qualified V2 plan and population."""
    if checkpoint: checkpoint()
    qb, qualification, context = application_qualification()
    payload = expected['payload']
    for key in ('source_receipt','catalog','gallery_preparation','runtimes'):
        require(payload[key] == context[key], 'Payload differs from qualified application context: '+key)
    evidence_review = review_evidence(folder, checkpoint=checkpoint, **expected)
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
    return dict(status='PASS_V2_APPLICATION_CONTENT_AND_FIXED_ROSTER_JOINS_ONLY',
        cell=evidence_review, roster=roster, widget=widget, application_qualification=qb,
        source_context=qualification['application_context'],
        application_owner_and_primary_settings_joined=True, fixed_display_roster_independently_joined=True,
        primary_caption_text_consistency_reviewed=True, exact_consumed_event_attribution=False,
        complete_panel_reviewed=False, names_independently_scored=False, accuracy_qualified=False,
        source_to_widget_latency_qualified=False, controlled_resources_qualified=False,
        physical_scanout_measured=False, actual_continuity_test=False, stop_restart_qualified=False,
        deployment_tier='UNKNOWN', integrated_N4_cells=0, N4_accepted=False)
