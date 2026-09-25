"""Bound research galleries and actual mode routing. See README_MODE_GALLERIES.md."""
from copy import deepcopy
from pathlib import Path
import re

from common import bind, fingerprint, freeze, load, verify

CONDITIONS = {'anonymous_conversation': 'none', 'enrolled_names': 'open',
              'open_with_names': 'open', 'selected_focus': 'selected_open', 'selected_closed': 'closed'}
ROW_FIELDS = {'gallery_id','roster_id','mode','domain','position','stream','tier_seconds',
              'matched_duration_diagnostic','intended_size','available_size','unavailable_count','gallery'}
REJECT_GATE = 'UNCALIBRATED_REJECT_ALL'
QUERY_SCOPE = 'processed mono XVF; predicted D0/D1 windows; no qualified C naming gate'


def verified_primary(index_binding, receipt_binding, encoder):
    """Rejoin safe index to the accepted extraction and original gallery bytes.

    The evaluator's Q scores are never returned to a predictor. No choice is
    made from scores: this is the already declared clean-source 15-second tier.
    """
    verify(index_binding); verify(receipt_binding)
    index, receipt = load(index_binding['path']), load(receipt_binding['path'])
    if (index.get('schema') != 'n2-runtime-safe-gallery-index-v1' or index.get('encoder') != encoder
            or receipt.get('status') != 'COMPLETE' or receipt.get('encoder') != encoder):
        raise ValueError('Require matching completed encoder gallery publication')
    verify(receipt['private_result']); result = load(receipt['private_result']['path'])
    if result['status'] != 'COMPLETE' or result['encoder'] != encoder:
        raise ValueError('Incomplete or foreign gallery extraction')
    selected = {}
    for row in index['conditions']:
        if set(row) != ROW_FIELDS:
            raise ValueError('Safe gallery condition firewall failed')
        if not (row['domain'] == 'clean_source' and row['tier_seconds'] == 15
                and row['matched_duration_diagnostic'] is False):
            continue
        mode = row['mode']
        if mode not in CONDITIONS.values() or mode in selected:
            raise ValueError('Unexpected or duplicate primary gallery condition')
        verify(row['gallery']); document = load(row['gallery']['path'])
        provenance = document['publication_provenance']
        if provenance['component_result'] != receipt['private_result'] or provenance['vectors_changed'] is not False:
            raise ValueError('Unbound or changed gallery publication')
        verify(provenance['source_gallery']); original = load(provenance['source_gallery']['path'])
        originals = [r for r in result['galleries'] if r['gallery'] == provenance['source_gallery']]
        if len(originals) != 1 or {k: originals[0][k] for k in ROW_FIELDS-{'gallery'}} != {k: row[k] for k in ROW_FIELDS-{'gallery'}}:
            raise ValueError('Runtime roster differs from accepted extraction')
        expected_namespace = deepcopy(original['namespace'])
        if encoder == 'E0':
            if expected_namespace['preprocessing'] != 'original_redimnet2_b2_fp32_graph_waveform_mono16k_gain1':
                raise ValueError('Unrecognized baseline preprocessing alias')
            expected_namespace['preprocessing'] = 'mono-float32-16k-redimnet2-native-l2-v1'
        if (encoder not in ('E0','E1') or expected_namespace != index['namespace']
                or document['namespace'] != expected_namespace or provenance['source_namespace'] != original['namespace']
                or provenance['metadata_alias_only'] is not (encoder == 'E0')
                or document['profiles'] != original['profiles'] or document.get('research_only') is not True):
            raise ValueError('Gallery vector/namespace/provenance mismatch')
        # Reproduce exactly the admitted publisher's gate metadata transformation.
        gate = deepcopy(original['calibration'])
        gate['namespace'] = deepcopy(expected_namespace); gate['namespace_sha256'] = fingerprint(expected_namespace)
        gate['source_evaluator_profiles_sha256'] = gate.pop('gallery_profiles_sha256')
        gate['gallery_profiles_sha256'] = fingerprint(document['profiles'])
        gate.pop('gate_sha256', None); gate['gate_sha256'] = fingerprint(gate)
        if document['calibration'] != gate or gate.get('status') != REJECT_GATE:
            raise ValueError('Require unchanged processed-query reject-all gate; no promotion or fitting')
        for key in ('domain','duration_sec','roster_id','mode','position','stream','intended_size',
                    'available_size','unavailable_count','matched_duration_diagnostic'):
            if document.get(key) != original.get(key):
                raise ValueError('Published gallery condition changed: '+key)
        count = len(document['profiles'])
        if (row['available_size'] != count or row['intended_size'] != count+row['unavailable_count']
                or any(type(row[k]) is not int or row[k] < 0 for k in ('available_size','intended_size','unavailable_count'))
                or len({p['profile_id'] for p in document['profiles']}) != count
                or len({p['name'] for p in document['profiles']}) != count):
            raise ValueError('Gallery denominator or unique ID/name mismatch')
        selected[mode] = dict(condition=deepcopy(row), namespace=expected_namespace,
            source_gallery=provenance['source_gallery'], document=document)
    if set(selected) != set(CONDITIONS.values()):
        raise ValueError('All four predeclared primary gallery conditions required')
    return selected


def materialize_baseline(row, output):
    """Lossless float32 storage bridge to the actual baseline ProfileStore loader.

    Reuses accepted E vectors. It does not enroll, fit, adapt, or reinterpret the
    original baseline C088 thresholds as a processed-audio calibration.
    """
    import numpy as np
    from edge_speech_pipeline.research_identity_v3 import ResearchGallery
    output = Path(output)
    if output.exists(): raise ValueError('Preserve prior baseline bridge; use a fresh directory')
    namespace = row['namespace']
    if namespace['preprocessing'] != 'mono-float32-16k-redimnet2-native-l2-v1':
        raise ValueError('Baseline bridge accepts only original E0 vectors')
    profiles = row['document']['profiles']
    for p in profiles:
        if not isinstance(p['profile_id'], str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',p['profile_id']):
            raise ValueError('Unsafe research profile filename')
        v = np.asarray(p['vector'], dtype=np.float32)
        if v.shape != (192,) or not np.isfinite(v).all() or np.linalg.norm(v) < 1e-8:
            raise ValueError('Invalid research vector')
    root = output/'profiles'; root.mkdir(parents=True, exist_ok=False)
    manifest_rows = []
    for p in profiles:
        metadata = root/(p['profile_id']+'.json'); vector = metadata.with_suffix('.npy')
        freeze(metadata, dict(profile_id=p['profile_id'],display_name=p['name'],backend_id='redimnet2_b2_fp32',
            backend_sha256=namespace['model_sha256'],research_only=True,source_gallery=row['condition']['gallery'],
            transformation='existing accepted E centroid stored as exact float32; no enrollment or adaptation'))
        with vector.open('xb') as stream: np.save(stream,np.asarray(p['vector'],dtype=np.float32),allow_pickle=False)
        manifest_rows.append(dict(profile_id=p['profile_id'],display_name=p['name'],metadata=bind(metadata),vector=bind(vector)))
    path = output/'GALLERY.json'
    freeze(path,dict(schema_version='edge-research-gallery.v1',gallery_id='n4-baseline:'+row['condition']['gallery_id'],
        profile_root=str(root.resolve()),backend_sha256=namespace['model_sha256'],profiles=manifest_rows,
        provenance_binding=row['condition']['gallery']))
    gallery = ResearchGallery(path,namespace['model_sha256'])
    expected = {p['profile_id']: np.asarray(p['vector'],dtype=np.float32) for p in profiles}
    for profile_id, vector in zip(gallery.ids,gallery.matrix):
        v = expected[profile_id]; v = v/np.linalg.norm(v)
        if not np.array_equal(vector,v): raise ValueError('Actual ProfileStore bridge changed template bytes')
    return bind(path)


def backend_contract(catalog, key, mode):
    if mode not in CONDITIONS: raise ValueError('Only explicit nonspatial comparison modes are admitted')
    rows = [r for r in catalog['backends'] if r['key'] == key]
    if len(rows) != 1 or rows[0].get('implemented') is not True: raise ValueError('Backend unavailable or ambiguous')
    row = rows[0]; c = row['composition']; n2 = c.get('n2'); n3 = c.get('n3')
    if n2 is None and (key != 'baseline' or n3 is not None):
        raise ValueError('Unexpected non-N2 catalog route')
    a = n3['variant'] if n3 else 'A0'; d = n2['diarization'] if n2 else 'D0'; e = n2['embedding'] if n2 else 'E0'
    if a not in ('A0','A1','A2','A3') or d not in ('D0','D1') or e not in ('E0','E1'):
        raise ValueError('Unexpected comparison tuple')
    if n2 and n2.get('streaming_profile') != 'low_latency': raise ValueError('Changed D1 streaming context')
    return dict(backend_key=key,catalog_row_sha256=fingerprint(row),variant=a,diarization=d,encoder=e,
        engine='N3IdentityEngine' if n3 and n2 else 'N2Engine' if n2 else 'PrototypeEngine',
        uses_n2=n2 is not None,mode=mode,gallery_condition=CONDITIONS[mode],
        presentation_mode='M1' if mode=='anonymous_conversation' else 'M2',
        resolver='N2NameMap' if n2 else 'ResearchIdentityResolver' if mode=='anonymous_conversation' else 'PrototypeIdentityResolver',
        adaptation=False,calibration_scope=QUERY_SCOPE if n2 else 'original nominal C088; processed-query recognition unqualified')


def load_prepared_gallery(preparation_binding, contract):
    """Create independent gallery/query state per run; never borrow E0 for E1."""
    from app.n2_identity import N2Gallery
    from edge_speech_pipeline.research_identity_v3 import ResearchGallery
    verify(preparation_binding); prepared = load(preparation_binding['path'])
    if prepared['status'] != 'PREPARED_VERIFIED_RESEARCH_GALLERIES_ONLY': raise ValueError('Unreviewed gallery preparation')
    verify(prepared['catalog']); actual = backend_contract(load(prepared['catalog']['path']),contract['backend_key'],contract['mode'])
    if actual != contract: raise ValueError('Foreign or altered catalog mode contract')
    row = prepared['encoders'][contract['encoder']]['conditions'][contract['gallery_condition']]
    verify(row['condition']['gallery'])
    document = load(row['condition']['gallery']['path'])
    if document['calibration']['status'] != REJECT_GATE: raise ValueError('Operational calibration changed')
    if contract['mode']=='anonymous_conversation':
        if document['profiles']: raise ValueError('Gallery-absent control has hidden profiles')
        return None, deepcopy(row['condition'])
    if contract['uses_n2']:
        gallery = N2Gallery(document,row['namespace'],expected_query_domain='XVF_processed_predicted_windows')
    else:
        verify(row['baseline_manifest'])
        gallery = ResearchGallery(row['baseline_manifest']['path'],row['namespace']['model_sha256'])
    if len(gallery.ids) != row['condition']['available_size']: raise ValueError('Loaded gallery count changed')
    return gallery, deepcopy(row['condition'])


def configure_actual_mode(dispatcher, observed, profile, gallery, contract):
    """Invoke unchanged begin() routing at the existing scheduler seam.

    This is a method harness, not a full Controller/session/model start. The
    real begin() implementations choose resolver, tracker wrapper and display
    annotator. No independently reimplemented resolver-selection policy runs.
    """
    from app.pipeline import PrototypeEngine, effective_profile
    from app.n2_pipeline import N2Engine
    from app.n3_pipeline import N3IdentityEngine
    from app.n2_identity import N2NameMap
    tap = profile.input.identity_tap
    if profile.to_dict() != effective_profile('balanced',contract['mode'],tap).to_dict():
        raise ValueError('Require unchanged Balanced mode profile')
    if contract['adaptation'] or (contract['mode']=='anonymous_conversation') != (gallery is None):
        raise ValueError('Unexpected mode gallery/adaptation state')
    base = {'PrototypeEngine':PrototypeEngine,'N2Engine':N2Engine,'N3IdentityEngine':N3IdentityEngine}[contract['engine']]

    class Harness(base):
        def __init__(self):
            self._scheduler=dispatcher; self._s7_observed_clock=observed; self._research_profile=profile
            self._research_gallery=gallery; self.mode=contract['mode']; self.recipe='balanced'; self.live_spatial=None
            self.mode_configuration={}; self._journal=None; self.enhancement_route='bypass'; self.prototype_identity=None
            self.n2_diarization=contract['diarization']; self.n2_observer_factory=None; self.n2_observer=None
            if contract['uses_n2']: self.n2_name_map=N2NameMap(gallery,closed=self.mode=='selected_closed')
            self.start_events=[]
        def _begin_session(self, kind):
            if kind!='prototype': raise ValueError('Unexpected session kind')
        def _emit(self, kind, source, payload):
            self.start_events.append(dict(event_type=kind,source_time_sec=source,payload=deepcopy(payload)))

    harness=Harness(); harness.begin()
    actual = harness.n2_name_map if contract['uses_n2'] else dispatcher.scheduler.identity_resolver.target
    if type(actual).__name__ != contract['resolver']: raise ValueError('Actual application resolver changed')
    return harness
