"""Native S6C enrollment and C-only score calibration. README_S6C_ENROLLMENT.md."""
from __future__ import annotations

import argparse
import collections
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

for _name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[_name] = '1'
import numpy as np
import soundfile as sf

SIM = Path(__file__).resolve().parents[1]
REPO = SIM.parents[2]
RUN = '20260910T123540Z'
REPORT = SIM / 'reports/S6C' / RUN
STAGING = SIM / 'staging/s6c' / RUN
OUT = REPORT / 'enrollment'
PAYLOAD = Path('G:/Just_Peachy_S6C') / RUN / 'enrollment'
PLAN = OUT / 'ENROLLMENT_PLAN_V2.json'
RATE = 16000
TIERS = (5, 15, 30)
SEED = 'S6C_roster_seed_23:'
FIXED = ('FIXED_ROTATION_A', 'FIXED_ROTATION_B', 'LARGE_COHORT')
SETUP = ('ALL_EXPECTED_SETUP', 'SELECTED_PARTICIPANTS', 'WRONG_SELECTION_VISITORS')


def utc():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def bind(path):
    p = Path(path).resolve()
    before = p.stat()
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    after = p.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('File changed while hashing: ' + str(p))
    return dict(path=str(p), bytes=after.st_size, sha256=h.hexdigest())


def verify(binding):
    got = bind(binding['path'])
    if got['sha256'] != binding['sha256'] or got['bytes'] != binding['bytes']:
        raise ValueError('Bound bytes differ: ' + binding['path'])
    return got


def save(path, value, *, immutable=True):
    p = Path(path)
    raw = (json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + '\n').encode()
    p.parent.mkdir(parents=True, exist_ok=True)
    if immutable and p.exists():
        if p.read_bytes() != raw:
            raise ValueError('Refusing to overwrite existing evidence: ' + str(p))
        return bind(p)
    with tempfile.NamedTemporaryFile(dir=p.parent, suffix='.tmp', delete=False) as f:
        f.write(raw)
        tmp = Path(f.name)
    tmp.replace(p)
    return bind(p)


def named_people(coverage):
    rows = {x['identity']: x for x in coverage}
    return {identity: dict(identity=identity, display_name=f'Research Person {n:03d}',
                           dataset=rows[identity]['dataset'])
            for n, identity in enumerate(sorted(rows), 1)}


def roster_assignment(people):
    groups = collections.defaultdict(list)
    for identity, row in people.items():
        groups[row['dataset']].append(identity)
    result = {x: [] for x in FIXED}
    orders = {}
    for corpus, ids in sorted(groups.items()):
        ids.sort(key=lambda x: (hashlib.sha256((SEED + x).encode()).hexdigest(), x))
        orders[corpus] = ids
        result[FIXED[0]].extend(ids[::2])
        result[FIXED[1]].extend(ids[1::2])
        result[FIXED[2]].extend(x for n, x in enumerate(ids) if n % 4 != 3)
    return {k: sorted(v) for k, v in result.items()}, orders


def plan_galleries(people, coverage, q_rows, scene_ids=None):
    fixed, orders = roster_assignment(people)
    eligible = {tier: {x['identity'] for x in coverage
                      if x['requested_usable_seconds'] == tier and x['status'] == 'AVAILABLE'} for tier in TIERS}
    casts = collections.defaultdict(set)
    if scene_ids is not None:
        for case in scene_ids:
            casts[case] = set()
    for row in q_rows:
        if scene_ids is not None and row['case_id'] not in casts:
            raise ValueError('Query occurrence is outside the canonical case grid')
        casts[row['case_id']].add(row['identity'])
    rows = []
    for tier in TIERS:
        for condition in FIXED:
            intended = fixed[condition]
            rows.append(dict(gallery_condition=condition, enrollment_tier=tier, case_id=None,
                             intended_identities=intended,
                             available_identities=sorted(set(intended) & eligible[tier]),
                             unavailable_identities=sorted(set(intended) - eligible[tier]),
                             scene_derived_setup=False))
        for case, cast in sorted(casts.items()):
            cast = sorted(cast)
            selected = cast[:1] if cast else sorted(fixed[FIXED[0]])[:4]
            absent = [x for x in sorted(people, key=lambda x: (hashlib.sha256((SEED + x).encode()).hexdigest(), x))
                      if x not in cast and x in eligible[tier]]
            wrong = absent[:1] if cast else sorted(fixed[FIXED[0]])[:4]
            for condition, intended in zip(SETUP, (cast, selected, wrong)):
                if not cast:
                    intended = sorted(fixed[FIXED[0]])[:4]
                rows.append(dict(gallery_condition=condition, enrollment_tier=tier, case_id=case,
                                 intended_identities=intended,
                                 available_identities=sorted(set(intended) & eligible[tier]),
                                 unavailable_identities=sorted(set(intended) - eligible[tier]),
                                 scene_derived_setup=True,
                                 setup_assumption='Explicit simulated user participant selection; scorer cast is used only to construct this labeled setup condition'))
    return rows, fixed, orders


def freeze():
    if PLAN.exists():
        plan = read(PLAN)
        validate_plan(plan)
        return plan
    material_path = REPORT / 'enrollment_inventory/v2/PREPARATION_RECEIPT.json'
    material = read(material_path)
    if material['status'] != 'PASS_SOURCE_ACCOUNTING_ONLY':
        raise ValueError('Completed material accounting is required')
    verify(material['manifest'])
    verify(material['tier_coverage'])
    manifest = read(material['manifest']['path'])
    if any(manifest['leakage_audit']['exact_intersections'].values()):
        raise ValueError('Nonempty E/C/Q intersection')
    verify(manifest['query_manifest'])
    q_rows = read(manifest['query_manifest']['path'])['rows']
    old_epoch = SIM / 'reports/S6B/20260909T230840Z/EPOCH2_EXECUTION_MANIFEST.json'
    old_spec = read(old_epoch)
    scene_binding = verify(old_spec['scene_manifest'])
    scenes = read(scene_binding['path'])['scenes']
    scene_ids = [x['case_id'] for x in scenes]
    if len(q_rows) != 777 or len(scene_ids) != 240 or len(set(scene_ids)) != 240:
        raise ValueError('Canonical source/case denominator differs')
    for scene in scenes:
        if set(scene['cast'].values()) != {q['identity'] for q in q_rows if q['case_id'] == scene['case_id']}:
            raise ValueError('Canonical scene cast differs from Q source accounting')
    review_path = REPORT / 'independent_review/SOURCE_MATERIAL_REVIEW_V1.json'
    review = read(review_path)
    if 'PASS' not in str(review.get('status', '')):
        raise ValueError('Independent material review must pass')
    people = named_people(manifest['coverage'])
    galleries, fixed, orders = plan_galleries(people, manifest['coverage'], q_rows, scene_ids)
    intake = read(REPORT / 'INTAKE_AND_SNAPSHOT.json')
    modules = []
    for row in intake['application_snapshot']:
        if row['relative_path'].endswith('.py'):
            modules.append(verify(row['snapshot']))
    asset_rows = old_spec['assets']
    assets = [a for a in asset_rows if a['component_id'] in ('redimnet2_b2_fp32', 'pyannote_segmentation_3_0_fp32')]
    if len(assets) != 2:
        raise ValueError('Exact native speaker assets required')
    for a in assets:
        verify(a['binding'])
    from importlib.metadata import version
    plan = dict(schema='s6c-native-enrollment-plan.v1', status='FROZEN_BEFORE_ENROLLMENT_OR_CALIBRATION_INFERENCE',
        created_utc=utc(), code=bind(__file__), readme=bind(Path(__file__).with_name('README_S6C_ENROLLMENT.md')),
        supersedes_unexecuted_plan=bind(OUT / 'ENROLLMENT_PLAN_V1.json'),
        resume_repair_lineage=bind(OUT / 'UNEXECUTED_PLAN1_RESUME_REPAIR_LINEAGE_V1.json'),
        material_receipt=bind(material_path), material_manifest=material['manifest'],
        material_review=bind(review_path), query_manifest=manifest['query_manifest'], scene_manifest=scene_binding,
        canonical_case_count=len(scene_ids), Q_occurrence_count=len(q_rows),
        source_empty_cases=sorted(set(scene_ids) - {q['case_id'] for q in q_rows}),
        snapshot_authority=bind(REPORT / 'INTAKE_AND_SNAPSHOT.json'), app_root=str(STAGING / 's6b_app'),
        app_modules=modules, asset_authority=bind(old_epoch), assets=assets,
        versions={x: version(x) for x in ('numpy', 'onnxruntime', 'scipy', 'soundfile', 'psutil')},
        python=sys.version, registered_design=bind(REPORT / 'design/REGISTERED_DESIGN_V1.json'),
        calibration_amendment=bind(REPORT / 'design/C_ONLY_CALIBRATION_AMENDMENT_V1.json'),
        people=people, fixed_rosters=fixed, per_corpus_seed_order=orders, galleries=galleries,
        roster_rule=dict(seed=SEED, fixed_A='even zero-based indices per corpus', fixed_B='odd indices per corpus',
            large='indices modulo4 !=3 per corpus; withheld people remain strangers',
            all_expected='all cast identities as explicitly modeled user setup', selected='lexicographic first cast identity',
            wrong='replace selected identity with first seeded absent eligible person; all true cast unselected',
            source_empty='first4 global lexicographic fixedA identities; explicitly retain all11 source-empty canonical controls',
            unavailability='omit unsupported templates while retaining intended roster and every Q denominator; explicit empty manifest allowed'),
        enrollment=dict(function='unchanged enrollment.enroll_wavs', source='E only',
            window_samples=32000, hop_samples=16000, minimum_window_samples=8000,
            minimum_rms=0.002, gain=1.0, trimming=False, speaker_threads=1,
            cache='exact float32 waveform bytes + bound plan/backend/code/versions; centroid aggregation remains native'),
        C_query_protocol=dict(source='accepted C only, condition fitting restricts to available known roster members',
            window_samples=32000, hop_samples=32000, minimum_window_samples=8000,
            short_tail='less than0.5s unqueried; no padding/looping',
            score='cosine of native normalized window embedding against actual ProfileStore-normalized template',
            weighting='each nonoverlapping window is one query; identity and clip counts also reported',
            calibrated_probability=False, Q_embedding_calls=0, probe_dependent_fit=False),
        payload_root=str(PAYLOAD), model_load_policy='one lazy shared SpeakerModels with one inner CPU thread; loads ReDim and segmentation, calls embed only')
    save(PLAN, plan)
    return plan


def validate_plan(plan):
    if plan['code'] != bind(__file__) or plan['readme'] != bind(Path(__file__).with_name('README_S6C_ENROLLMENT.md')):
        raise ValueError('Plan helper/README changed; preserve this plan and diagnose')
    for field in ('material_receipt', 'material_manifest', 'material_review', 'query_manifest', 'scene_manifest',
                  'supersedes_unexecuted_plan', 'resume_repair_lineage',
                  'snapshot_authority', 'asset_authority', 'registered_design', 'calibration_amendment'):
        verify(plan[field])
    for row in plan['app_modules']:
        verify(row)
    for row in plan['assets']:
        verify(row['binding'])
    from importlib.metadata import version
    if plan['python'] != sys.version or any(version(k) != v for k, v in plan['versions'].items()):
        raise ValueError('Native numerical runtime changed')


def native_api(plan):
    if any(x == 'edge_speech_pipeline' or x.startswith('edge_speech_pipeline.') for x in sys.modules):
        raise ValueError('Fresh process required; an application module is already imported')
    sys.path.insert(0, plan['app_root'])
    from edge_speech_pipeline.config import PipelineConfig, AssetSpec
    from edge_speech_pipeline.models import SpeakerModels
    from edge_speech_pipeline.enrollment import enroll_wavs
    from edge_speech_pipeline.speakers import ProfileStore
    assets = tuple(AssetSpec(a['component_id'], Path(a['path']), a['sha256'], a['deployment_relative_path']) for a in plan['assets'])
    config = PipelineConfig(assets=assets, speaker_threads=1, profile_root=PAYLOAD / 'unused', session_root=PAYLOAD / 'unused_sessions')
    for name, module in list(sys.modules.items()):
        if name == 'edge_speech_pipeline' or name.startswith('edge_speech_pipeline.'):
            if Path(module.__file__).resolve().parent != (Path(plan['app_root']) / 'edge_speech_pipeline').resolve():
                raise ValueError('Unexpected application import: ' + name)
    return config, SpeakerModels, enroll_wavs, ProfileStore


class ExactEmbeddingCache:
    def __init__(self, model_class, config, plan_hash):
        self.model_class, self.config, self.plan_hash = model_class, config, plan_hash
        self.model = None
        self.calls = self.hits = self.loads = 0
        self.native_compute_sec = self.admission_sec = 0.
        self.context = None
        self.touched = {}

    def embed(self, waveform):
        x = np.ascontiguousarray(waveform, dtype=np.float32).reshape(-1)
        if len(x) < 8000 or not np.all(np.isfinite(x)):
            raise ValueError('Invalid native embedding waveform')
        identity = dict(plan_sha256=self.plan_hash, samples=len(x),
                        waveform_sha256=hashlib.sha256(x.tobytes()).hexdigest())
        key = digest(identity)
        receipt = PAYLOAD / 'embedding_cache' / (key + '.json')
        target = receipt.with_suffix('.npy')
        if receipt.exists():
            old = read(receipt)
            if old['identity'] != identity or old['status'] != 'COMPLETE':
                raise ValueError('Embedding cache identity differs')
            if Path(old['vector']['path']).resolve() != target.resolve():
                raise ValueError('Embedding cache binding redirects away from exact keyed vector')
            raw = target.read_bytes()
            if len(raw) != old['vector']['bytes'] or hashlib.sha256(raw).hexdigest() != old['vector']['sha256']:
                raise ValueError('Embedding cache vector bytes differ')
            vector = np.load(io.BytesIO(raw), allow_pickle=False)
            self.hits += 1
        else:
            if target.exists():
                raise ValueError('Unreceipted embedding vector preserved: ' + str(target))
            if self.model is None:
                started = time.perf_counter()
                self.model = self.model_class(self.config)
                self.admission_sec = time.perf_counter() - started
                self.loads += 1
            started = time.perf_counter()
            vector = self.model.embed(x)
            elapsed = time.perf_counter() - started
            self.native_compute_sec += elapsed
            self.calls += 1
            target.parent.mkdir(parents=True, exist_ok=True)
            np.save(target, vector, allow_pickle=False)
            save(receipt, dict(status='COMPLETE', identity=identity, vector=bind(target), native_compute_sec=elapsed,
                               creator_context=self.context, created_utc=utc()))
        if vector.shape != (192,) or vector.dtype != np.float32 or not np.all(np.isfinite(vector)) or np.linalg.norm(vector) <= 0:
            raise ValueError('Invalid cached native vector')
        self.touched[key] = bind(receipt)
        return vector.copy()


def template_key(identity, tier):
    return f'{identity}_T{tier:02d}'


def validate_template(record, expected):
    if record.get('identity') != expected or record.get('status') != 'COMPLETE':
        raise ValueError('Template checkpoint source/tier/code identity differs')
    verify(record['metadata'])
    verify(record['vector'])
    m = read(record['metadata']['path'])
    expected_root = (PAYLOAD / 'templates' / template_key(expected['metadata_identity'], expected['tier'])).resolve()
    mp = Path(record['metadata']['path']).resolve()
    vp = Path(record['vector']['path']).resolve()
    if mp.parent != expected_root or vp != mp.with_suffix('.npy') or mp.stem != record['profile_id'] or mp.suffix != '.json':
        raise ValueError('Template must use exact isolated identity/tier root and native sibling files')
    if (m['display_name'] != expected['display_name'] or m['profile_id'] != record['profile_id']
        or m['backend_id'] != 'redimnet2_b2_fp32' or m['backend_sha256'] != expected['backend_sha256']):
        raise ValueError('Wrong template metadata/name')
    paths = [str(Path(x['path']).resolve()) for x in m['source_files']]
    if paths != [str(Path(x['path']).resolve()) for x in expected['source_bindings']]:
        raise ValueError('Native template source files differ from exact ordered E tier')
    if m['embedding_count'] != expected['native_embedding_count']:
        raise ValueError('Native template embedding count differs from exact E windows')
    v = np.load(record['vector']['path'], allow_pickle=False)
    if v.shape != (192,) or v.dtype != np.float32 or not np.all(np.isfinite(v)) or np.linalg.norm(v) <= 0:
        raise ValueError('Invalid template vector')


def fit_grid(scores, true_columns, rule):
    scores = np.asarray(scores, dtype=np.float32)
    truths = np.asarray(true_columns, dtype=np.int64)
    if scores.ndim != 2 or len(scores) != len(truths) or not np.all(np.isfinite(scores)):
        raise ValueError('Invalid C-only score matrix')
    if scores.shape[1] == 0 or np.any(truths < 0) or np.any(truths >= scores.shape[1]):
        raise ValueError('Calibration query identity is not in this exact roster')
    order = np.argsort(-scores, axis=1, kind='stable')
    top = order[:, 0]
    # Runtime compares Python float cosine/margin to the configured thresholds.
    top_score = scores[np.arange(len(scores)), top].astype(np.float64)
    second = scores[np.arange(len(scores)), order[:, 1]].astype(np.float64) if scores.shape[1] > 1 else np.full(len(scores), -1.)
    margin = top_score - second
    table = []
    for threshold in rule['threshold_grid']:
        for gap in rule['margin_grid']:
            accepted = (top_score >= threshold) & (margin >= gap)
            table.append(dict(score_threshold=threshold, margin_threshold=gap,
                              wrong_known_accepted=int(np.sum(accepted & (top != truths))),
                              correct_known_accepted=int(np.sum(accepted & (top == truths))),
                              unknown_rejected=int(np.sum(~accepted)), total_queries=len(scores)))
    winner = min(table, key=lambda x: (x['wrong_known_accepted'], -x['correct_known_accepted'],
                                     -x['score_threshold'], -x['margin_threshold']))
    return winner, table


def run():
    plan = read(PLAN)
    validate_plan(plan)
    if (OUT / 'ENROLLMENT_COMPLETION.json').exists():
        return verify_complete()
    if shutil.disk_usage('C:/').free < 50 * 2**30 or shutil.disk_usage('G:/').free < 75 * 2**30:
        raise ValueError('Required storage reserve unavailable')
    import psutil
    process = psutil.Process()
    owner = dict(pid=process.pid, creation_time=process.create_time(), created_utc=utc(),
                 command=sys.argv, plan=bind(PLAN), threads=1,
                 model_owner='one shared immutable SpeakerModels; ReDim embed only, no ASR/segmentation calls')
    owner_path = OUT / 'workers' / f'{process.pid}_{round(process.create_time()*1000)}.json'
    save(owner_path, dict(status='RUNNING', **owner))
    print(json.dumps(dict(status='MODEL_OWNER_REGISTERED', **owner)), flush=True)
    config, model_class, enroll, store_class = native_api(plan)
    cache = ExactEmbeddingCache(model_class, config, bind(PLAN)['sha256'])
    manifest = read(plan['material_manifest']['path'])
    plan_hash = bind(PLAN)['sha256']
    sources = {x['source_id']: x for x in manifest['accepted_sources']}
    for source in sources.values():
        verify(source['decoded_16k_binding'])
        verify(source['source_binding'])
    templates = {}
    for coverage in manifest['coverage']:
        if coverage['status'] != 'AVAILABLE':
            continue
        identity, tier = coverage['identity'], coverage['requested_usable_seconds']
        key = template_key(identity, tier)
        ids = coverage['source_ids']
        if any(sources[x]['s6c_role'] != 'E' or sources[x]['identity'] != identity for x in ids):
            raise ValueError('Template input is not the intended E source')
        expected = dict(plan_sha256=plan_hash, metadata_identity=identity, tier=tier,
                        display_name=plan['people'][identity]['display_name'], source_ids=ids,
                        source_bindings=[sources[x]['decoded_16k_binding'] for x in ids],
                        backend_sha256=config.asset('redimnet2_b2_fp32').sha256,
                        native_embedding_count=sum(len(range(0, max(1, sources[x]['samples'] - 8000 + 1), 16000)) for x in ids))
        receipt = OUT / 'templates' / (key + '.json')
        root = PAYLOAD / 'templates' / key
        if receipt.exists():
            record = read(receipt)
            validate_template(record, expected)
        else:
            if root.exists() and any(root.iterdir()):
                raise ValueError('Unreceipted native enrollment artifacts preserved: ' + str(root))
            cache.context = dict(kind='E_NATIVE_ENROLLMENT', metadata_identity=identity, tier=tier)
            before_calls, before_hits = cache.calls, cache.hits
            started = time.perf_counter()
            meta = enroll(expected['display_name'], [Path(sources[x]['decoded_16k_binding']['path']) for x in ids],
                          models=cache, config=replace(config, profile_root=root))
            elapsed = time.perf_counter() - started
            record = dict(status='COMPLETE', identity=expected, profile_id=meta['profile_id'],
                metadata=bind(root / (meta['profile_id'] + '.json')), vector=bind(root / (meta['profile_id'] + '.npy')),
                native_function='unchanged enrollment.enroll_wavs', elapsed_sec=elapsed,
                actual_new_embedding_calls=cache.calls - before_calls, exact_window_cache_hits=cache.hits - before_hits,
                native_embedding_count=meta['embedding_count'], quality_status=meta['quality_status'],
                actual_estimated_unique_usable_sec=coverage['actual_estimated_usable_seconds'],
                actual_whole_clip_sec=coverage['actual_whole_clip_seconds'], created_utc=utc())
            validate_template(record, expected)
            loaded = store_class(root, expected_backend_sha256=config.asset('redimnet2_b2_fp32').sha256).load()
            if set(loaded) != {expected['display_name']}:
                raise ValueError('Actual native ProfileStore did not load enrolled template')
            save(receipt, record)
        templates[(identity, tier)] = record
        print(json.dumps(dict(status='TEMPLATE_COMPLETE', identity=identity, tier=tier, count=len(templates),
                              new_model_calls=cache.calls, exact_cache_hits=cache.hits)), flush=True)
    gallery_rows, scorer_rows, unique_galleries = [], [], {}
    backend = config.asset('redimnet2_b2_fp32').sha256
    for row in plan['galleries']:
        members = row['available_identities']
        tier = row['enrollment_tier']
        key = digest(dict(tier=tier, members=members))[:24]
        root = PAYLOAD / 'galleries' / key / 'profiles'
        gpath = PAYLOAD / 'galleries' / key / 'GALLERY.json'
        if key not in unique_galleries:
            root.mkdir(parents=True, exist_ok=True)
            profiles = []
            for identity in members:
                record = templates[(identity, tier)]
                target_m = root / Path(record['metadata']['path']).name
                target_v = root / Path(record['vector']['path']).name
                for original, target in ((record['metadata'], target_m), (record['vector'], target_v)):
                    if target.exists():
                        if bind(target)['sha256'] != original['sha256']:
                            raise ValueError('Copied native gallery bytes differ')
                    else:
                        shutil.copy2(original['path'], target)
                profiles.append(dict(profile_id=record['profile_id'], display_name=plan['people'][identity]['display_name'],
                                     metadata=bind(target_m), vector=bind(target_v)))
            gallery = dict(schema_version='edge-research-gallery.v1', gallery_id='S6C_' + key,
                           profile_root=str(root.resolve()), backend_sha256=backend, profiles=profiles)
            save(gpath, gallery)
            loaded = store_class(root, expected_backend_sha256=backend).load()
            if set(loaded) != {x['display_name'] for x in profiles}:
                raise ValueError('Actual ProfileStore roster differs')
            expected_files = {Path(p[k]['path']).resolve() for p in profiles for k in ('metadata', 'vector')}
            if {p.resolve() for p in root.iterdir()} != expected_files:
                raise ValueError('Unmanifested file in isolated gallery root')
            unique_galleries[key] = dict(manifest=bind(gpath), profiles=profiles, members=members, tier=tier)
        g = unique_galleries[key]
        index = {k: row[k] for k in ('gallery_condition', 'enrollment_tier', 'case_id')}
        gallery_rows.append(dict(**index, manifest=g['manifest']))
        scorer_rows.append(dict(**row, manifest=g['manifest'], loaded_count=len(members),
                               eligibility='AVAILABLE' if members else 'NO_AVAILABLE_TEMPLATES',
                               profiles=[dict(metadata_identity=identity, profile_id=templates[(identity, tier)]['profile_id'],
                                   display_name=plan['people'][identity]['display_name']) for identity in members]))
    # Only people known in at least one actually available gallery need C windows.
    union_known = {x for g in plan['galleries'] for x in g['available_identities']}
    Crows = []
    for source in sorted(sources.values(), key=lambda x: x['source_id']):
        if source['s6c_role'] != 'C' or source['identity'] not in union_known:
            continue
        x, sr = sf.read(source['decoded_16k_binding']['path'], dtype='float32')
        if sr != RATE or x.ndim != 1:
            raise ValueError('Prepared C waveform shape/rate differs')
        for left in range(0, len(x), 32000):
            right = min(left + 32000, len(x))
            if right - left < 8000:
                continue
            cache.context = dict(kind='C_QUERY', source_id=source['source_id'], samples=[left, right])
            vector = cache.embed(x[left:right])
            Crows.append(dict(source_id=source['source_id'], metadata_identity=source['identity'],
                              source_start_sample=left, source_end_sample=right, vector=vector.tolist()))
    cpath = PAYLOAD / 'calibration' / 'C_WINDOW_EMBEDDINGS.json'
    save(cpath, dict(schema='s6c-C-only-embeddings.v1', plan=bind(PLAN), rows=Crows,
                    eligibility='Reusable C pool; fitting filters to the exact available known roster, including no withheld identities'))
    amendment = read(plan['calibration_amendment']['path'])
    calibration = []
    for candidate in amendment['candidates']:
        settings = candidate['settings']
        match = [x for x in scorer_rows if x['gallery_condition'] == settings['gallery_condition']
                 and x['enrollment_tier'] == settings['enrollment_tier'] and x['case_id'] is None]
        if len(match) != 1:
            raise ValueError('C calibration exact roster/tier is ambiguous')
        gallery = match[0]
        members = sorted(gallery['available_identities'], key=lambda x: plan['people'][x]['display_name'])
        rows = [x for x in Crows if x['metadata_identity'] in members]
        if any(x['metadata_identity'] not in members for x in rows):
            raise ValueError('Withheld stranger in calibration')
        native_gallery = read(gallery['manifest']['path'])
        loaded = store_class(Path(native_gallery['profile_root']), expected_backend_sha256=backend).load()
        if set(loaded) != {plan['people'][x]['display_name'] for x in members}:
            raise ValueError('C score roster differs from actual native ProfileStore')
        matrix = np.stack([loaded[plan['people'][x]['display_name']] for x in members]).astype(np.float32) if members else np.empty((0, 192), np.float32)
        vectors = np.asarray([x['vector'] for x in rows], np.float32).reshape((-1, 192))
        # Preserve the actual gallery's single-query float32 dot arithmetic.
        scores = np.stack([matrix @ v for v in vectors]) if len(vectors) else np.empty((0, len(members)), np.float32)
        truths = [members.index(x['metadata_identity']) for x in rows]
        winner, grid = (fit_grid(scores, truths, amendment['fitted_rule']) if len(rows) >= amendment['fitted_rule']['minimum_queries'] and members else (None, []))
        detail = dict(candidate_id=candidate['candidate_id'], gallery_condition=settings['gallery_condition'],
            enrollment_tier=settings['enrollment_tier'], manifest=gallery['manifest'],
            known_metadata_identities=members, withheld_metadata_identities=sorted(set(plan['people']) - set(members)),
            calibration_metadata_identities=sorted({x['metadata_identity'] for x in rows}),
            total_window_queries=len(rows), calibration_unique_clips=len({x['source_id'] for x in rows}),
            calibration_people=len({x['metadata_identity'] for x in rows}),
            known_people_without_C=sorted(set(members) - {x['metadata_identity'] for x in rows}),
            status='FITTED_C_ONLY' if winner else 'UNAVAILABLE_CALIBRATION',
            selected=winner or dict(score_threshold=config.identity_score_threshold, margin_threshold=config.identity_margin_threshold),
            grid=grid, score_columns=[dict(metadata_identity=x, display_name=plan['people'][x]['display_name'], profile_id=templates[(x, settings['enrollment_tier'])]['profile_id']) for x in members],
            score_rows=[{k: v for k, v in x.items() if k != 'vector'} for x in rows],
            cosine_scores=scores.tolist(), wrong_template_scores='Every nontrue score column is a legitimate known-person/wrong-template comparison; no withheld-identity C query used',
            interpretation='Threshold score/margin calibration only, not calibrated posterior or Q identification result',
            C_embeddings=bind(cpath), plan=bind(PLAN))
        dpath = OUT / 'calibration' / (candidate['candidate_id'] + '.json')
        save(dpath, detail)
        calibration.append(dict(candidate_id=candidate['candidate_id'], status=detail['status'], selected=detail['selected'],
                                gallery_condition=settings['gallery_condition'], enrollment_tier=settings['enrollment_tier'],
                                receipt=bind(dpath)))
    idx = REPORT / 'RESEARCH_GALLERY_INDEX.json'
    scoremap = OUT / 'SCORER_GALLERY_MAP.json'
    save(idx, dict(schema='s6c-research-gallery-index.v1', status='COMPLETE', plan=bind(PLAN), rows=gallery_rows))
    save(scoremap, dict(schema='s6c-scorer-gallery-map.v1', status='COMPLETE', runtime_input=False,
                       plan=bind(PLAN), people=plan['people'], rows=scorer_rows,
                       warning='Corpus-qualified metadata identities and scene cast/setup lineage are evaluator-only; never anonymous association inputs'))
    cindex = OUT / 'C_ONLY_CALIBRATION_INDEX.json'
    save(cindex, dict(schema='s6c-C-only-calibration-index.v1', status='COMPLETE', rows=calibration, plan=bind(PLAN)))
    template_index = OUT / 'TEMPLATE_INDEX.json'
    save(template_index, dict(status='COMPLETE', rows=[dict(metadata_identity=i, enrollment_tier=t,
        receipt=bind(OUT / 'templates' / (template_key(i, t) + '.json'))) for i, t in templates], plan=bind(PLAN)))
    cache_index = OUT / 'EMBEDDING_CACHE_INDEX.json'
    # All completed cache nodes are immutable and belong to the same plan.
    nodes = []
    for p in sorted((PAYLOAD / 'embedding_cache').glob('*.json')):
        record = read(p)
        if record['status'] != 'COMPLETE' or record['identity']['plan_sha256'] != plan_hash:
            raise ValueError('Foreign or partial embedding cache node')
        verify(record['vector'])
        nodes.append(bind(p))
    save(cache_index, dict(status='COMPLETE', plan=bind(PLAN), rows=nodes,
                          unique_native_waveform_invocations=len(nodes),
                          scope='One complete cache node per native waveform invocation; includes resumed processes if any'))
    validate_plan(plan)
    done = dict(schema='s6c-native-enrollment-completion.v1', status='COMPLETE', created_utc=utc(), plan=bind(PLAN),
        outputs=[bind(p) for p in (idx, scoremap, cindex, template_index, cpath, cache_index)],
        native_templates=len(templates), gallery_index_rows=len(gallery_rows), distinct_gallery_manifests=len(unique_galleries),
        unavailable_empty_rows=sum(not x['available_identities'] for x in scorer_rows),
        C_window_queries=len(Crows), C_people=len({x['metadata_identity'] for x in Crows}),
        actual_embedding_calls_this_process=cache.calls, cache_hits_this_process=cache.hits, model_loads_this_process=cache.loads,
        native_embedding_compute_sec_this_process=cache.native_compute_sec, model_admission_sec_this_process=cache.admission_sec,
        hardware_passes=0, Q_embedding_calls=0, model_training_steps=0,
        owner=owner, scope='Actual native enrollment and C score calibration; no Q identification metric or hardware result')
    save(OUT / 'ENROLLMENT_COMPLETION.json', done)
    save(owner_path, dict(status='COMPLETED_FUNCTION_BODY', **owner, completed_utc=utc()), immutable=False)
    return done


def verify_complete():
    done = read(OUT / 'ENROLLMENT_COMPLETION.json')
    verify(done['plan'])
    plan = read(done['plan']['path'])
    validate_plan(plan)
    for b in done['outputs']:
        verify(b)
    ti = read(OUT / 'TEMPLATE_INDEX.json')
    material = read(plan['material_manifest']['path'])
    sources = {x['source_id']: x for x in material['accepted_sources']}
    # Completed cache admission is still conditional on exact current inputs.
    for source in sources.values():
        verify(source['source_binding'])
        verify(source['decoded_16k_binding'])
    coverage = {(x['identity'], x['requested_usable_seconds']): x for x in material['coverage']}
    expected_keys = {k for k, x in coverage.items() if x['status'] == 'AVAILABLE'}
    if {(r['metadata_identity'], r['enrollment_tier']) for r in ti['rows']} != expected_keys or len(ti['rows']) != len(expected_keys):
        raise ValueError('Completed template grid differs from available source tiers')
    for row in ti['rows']:
        verify(row['receipt'])
        record = read(row['receipt']['path'])
        identity, tier = row['metadata_identity'], row['enrollment_tier']
        ids = coverage[(identity, tier)]['source_ids']
        expected = dict(plan_sha256=bind(PLAN)['sha256'], metadata_identity=identity, tier=tier,
                        display_name=plan['people'][identity]['display_name'], source_ids=ids,
                        source_bindings=[sources[x]['decoded_16k_binding'] for x in ids],
                        backend_sha256=next(x['sha256'] for x in plan['assets'] if x['component_id'] == 'redimnet2_b2_fp32'),
                        native_embedding_count=sum(len(range(0, max(1, sources[x]['samples'] - 8000 + 1), 16000)) for x in ids))
        validate_template(record, expected)
    galleries = read(REPORT / 'RESEARCH_GALLERY_INDEX.json')['rows']
    for path in {x['manifest']['path']: x['manifest'] for x in galleries}.values():
        verify(path)
        g = read(path['path'])
        for row in g['profiles']:
            verify(row['metadata'])
            verify(row['vector'])
    for row in read(OUT / 'C_ONLY_CALIBRATION_INDEX.json')['rows']:
        verify(row['receipt'])
    for b in read(OUT / 'EMBEDDING_CACHE_INDEX.json')['rows']:
        verify(b)
        verify(read(b['path'])['vector'])
    return dict(status='VERIFIED_COMPLETE_NATIVE_ENROLLMENT', completion=bind(OUT / 'ENROLLMENT_COMPLETION.json'), model_calls=0)


def self_test():
    checks = []
    people = {str(i): dict(dataset='corpus') for i in range(8)}
    rosters, _ = roster_assignment(people)
    assert set(rosters[FIXED[0]]).isdisjoint(rosters[FIXED[1]])
    assert set(rosters[FIXED[0]]) | set(rosters[FIXED[1]]) == set(people)
    assert len(rosters[FIXED[2]]) == 6
    checks += ['fixed rotations disjoint and complete', 'large cohort retains withheld strangers']
    cov = [dict(identity=x, requested_usable_seconds=t, status='UNAVAILABLE' if t == 30 else 'AVAILABLE') for x in people for t in TIERS]
    rows, _, _ = plan_galleries(people, cov, [dict(case_id='case', identity='1'), dict(case_id='case', identity='2')])
    assert all(not x['available_identities'] for x in rows if x['enrollment_tier'] == 30)
    checks.append('missing tier cannot borrow alternate material')
    assert next(x for x in rows if x['gallery_condition'] == 'SELECTED_PARTICIPANTS' and x['enrollment_tier'] == 5)['intended_identities'] == ['1']
    assert not set(next(x for x in rows if x['gallery_condition'] == 'WRONG_SELECTION_VISITORS' and x['enrollment_tier'] == 5)['intended_identities']) & {'1', '2'}
    checks += ['explicit selected first participant', 'wrong selection is absent']
    full, fixed, _ = plan_galleries(people, cov, [dict(case_id='speech', identity='1')], ['speech', 'empty'])
    empty = [x for x in full if x['case_id'] == 'empty']
    assert len(empty) == 9 and all(x['intended_identities'] == sorted(fixed[FIXED[0]])[:4] for x in empty)
    assert len(full) == len(FIXED)*len(TIERS) + len(SETUP)*len(TIERS)*2
    checks.append('source-empty canonical case retains all9 setup tier rows with frozen fallback')
    rule = dict(threshold_grid=[.45, .6, .75], margin_grid=[0., .03])
    win, _ = fit_grid([[.8, .3], [.2, .9]], [0, 1], rule)
    assert win['score_threshold'] == .75 and win['margin_threshold'] == .03
    checks.append('grid deterministic higher threshold and margin tie break')
    try:
        fit_grid([[.8, .3]], [2], rule)
    except ValueError:
        checks.append('withheld identity cannot enter exact-roster calibration')
    else:
        raise AssertionError('withheld query admitted')
    with tempfile.TemporaryDirectory() as temp:
        p = Path(temp) / 'a'
        p.write_bytes(b'aaa')
        old = bind(p)
        stamp = p.stat().st_mtime_ns
        p.write_bytes(b'bbb')
        os.utime(p, ns=(stamp, stamp))
        try:
            verify(old)
        except ValueError:
            checks.append('same-size old-mtime changed bytes rejected')
        else:
            raise AssertionError('changed bytes admitted')
        try:
            validate_template(dict(status='COMPLETE', identity={'tier': 5}), {'tier': 15})
        except ValueError:
            checks.append('same-plan wrong template checkpoint rejected')
        else:
            raise AssertionError('wrong checkpoint admitted')
        class FakeModel:
            def __init__(self, config):
                self.calls = 0
            def embed(self, waveform):
                self.calls += 1
                v = np.ones(192, np.float32)
                v[0] = float(waveform[0])
                return v / np.linalg.norm(v)
        global PAYLOAD
        saved_payload = PAYLOAD
        PAYLOAD = Path(temp) / 'cache_fixture'
        try:
            cache = ExactEmbeddingCache(FakeModel, None, 'planA')
            a = cache.embed(np.ones(8000, np.float32))
            b = cache.embed(np.ones(8000, np.float32))
            assert np.array_equal(a, b) and cache.calls == 1 and cache.hits == 1 and cache.loads == 1
            other = ExactEmbeddingCache(FakeModel, None, 'planB')
            other.embed(np.ones(8000, np.float32))
            assert other.calls == 1 and other.hits == 0
            checks += ['exact waveform cache parity and resident load reuse', 'different plan cannot hit prior vector cache']
            cache_receipt = Path(next(iter(cache.touched.values()))['path'])
            node = read(cache_receipt)
            alternate = PAYLOAD / 'alternate.npy'
            np.save(alternate, b, allow_pickle=False)
            target = cache_receipt.with_suffix('.npy')
            np.save(target, np.zeros(192, np.float32), allow_pickle=False)
            node['vector'] = bind(alternate)
            save(cache_receipt, node, immutable=False)
            try:
                cache.embed(np.ones(8000, np.float32))
            except ValueError:
                checks.append('alternate valid cache binding cannot validate a different returned target')
            else:
                raise AssertionError('redirected cache binding admitted')
            root = PAYLOAD / 'templates' / template_key('person', 5)
            root.mkdir(parents=True)
            mp, vp = root / 'native_id.json', root / 'native_id.npy'
            source_path = Path(temp) / 'E5.wav'
            source_path.write_bytes(b'fixture E bytes')
            expected = dict(metadata_identity='person', tier=5, display_name='Research Person 001',
                            source_bindings=[bind(source_path)], backend_sha256='backend', native_embedding_count=1)
            meta = dict(display_name=expected['display_name'], profile_id='native_id', backend_id='redimnet2_b2_fp32',
                        backend_sha256='backend', source_files=[dict(path=str(source_path))], embedding_count=1)
            save(mp, meta)
            np.save(vp, b, allow_pickle=False)
            record = dict(status='COMPLETE', identity=expected, profile_id='native_id', metadata=bind(mp), vector=bind(vp))
            validate_template(record, expected)
            checks.append('exact native template fixture admitted')
            meta['source_files'][0]['path'] = str(Path(temp) / 'other_tier_E15.wav')
            save(mp, meta, immutable=False)
            record['metadata'] = bind(mp)
            try:
                validate_template(record, expected)
            except ValueError:
                checks.append('same-name wrong-tier native source metadata rejected despite correct outer identity')
            else:
                raise AssertionError('swapped inner template tier admitted')
        finally:
            PAYLOAD = saved_payload
    return dict(status='PASS_MODEL_FREE_CHECKS', checks=checks, model_calls=0, hardware_passes=0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('freeze', 'run', 'verify', 'self-test'))
    args = parser.parse_args()
    result = {'freeze': freeze, 'run': run, 'verify': verify_complete, 'self-test': self_test}[args.action]()
    if args.action == 'freeze':
        result = dict(status=result['status'], plan=bind(PLAN), gallery_rows=len(result['galleries']))
    print(json.dumps(result, indent=2, allow_nan=False), flush=True)
