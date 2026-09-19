"""Prepare non-executable width scorer proposals; README_S6D_SCORE_QUEUE_PREPARATION.md."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True
PLAN_SHA = '5504e9a6cd49767816ad7dc17c913f5a4f3a76db44f0f235ed30153a619a05dd'
WRAPPER_SHA = 'f348ae09db926b519533e5380f54e64a4ab805af6585d2c3190958caa3e343e3'
RUNNER_SHA = '3c0e5f71578f5fc6bbd34bddde42393912d878107f1b07d5c5edc0d2a258b1b3'
JOB_ID = 'OPERATIONAL_WIDTH_SCORE_ALL5760_V1'


def bind(path, expected=None):
    path = Path(path).resolve()
    before = path.stat()
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    after = path.stat()
    result = dict(path=str(path), bytes=after.st_size, sha256=digest.hexdigest())
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('Changed file while binding: ' + str(path))
    if expected is not None and result['sha256'] != expected:
        raise ValueError('Source hash differs: ' + str(path))
    return result


def verify(value):
    actual = bind(value['path'], value['sha256'])
    if actual != value:
        raise ValueError('Declared file binding differs')
    return actual


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path, value):
    with Path(path).open('x', encoding='utf-8') as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write('\n')
    return bind(path)


def cell_key(row):
    return row['candidate_id'], row['stream'], row['case_id']


def prepare(output, width_queue, adapter_plan, protocol_source, runner):
    output = output.resolve()
    if output.exists():
        raise ValueError('Fresh proposal directory required')
    queue_binding = bind(width_queue)
    upstream = read(width_queue)
    plan_binding = bind(adapter_plan, PLAN_SHA)
    plan = read(adapter_plan)
    wrapper_binding = bind(protocol_source, WRAPPER_SHA)
    runner_binding = bind(runner, RUNNER_SHA)
    sim = Path(plan['adapter_sources'][0]['path']).parent.parent
    report = Path(plan['analysis_report_root']).parent.parent
    if upstream['run_id'] != '20260913T195357Z' or len(upstream['jobs']) != 1:
        raise ValueError('Exact upstream width queue required')
    expected_jobs = [f'S6D_{p}_W{w:02d}_{t}' for p in ('C079', 'C120') for w in (2, 5, 10, 20) for t in ('O0', 'O1')]
    if plan['expected_jobs'] != expected_jobs or len(plan['new_cells']) != 3840 or len(plan['controls']) != 1920:
        raise ValueError('Frozen literal scorer matrix differs')
    indices = [Path(a['path']) for a in upstream['jobs'][0]['expected_artifacts'] if Path(a['path']).name == 'PREDICTION_INDEX.json']
    if len(indices) != 1:
        raise ValueError('One literal upstream prediction-index path required')
    index_path = indices[0]
    observation = dict(observed_utc=datetime.now(timezone.utc).isoformat(), expected_index_path=str(index_path),
        status='PENDING_INDEX_NOT_PRESENT', prediction_indices=[], poll_loop_used=False,
        source_queue=queue_binding, adapter_plan=plan_binding, validated_prediction_bytes=0,
        actual_prediction_coverage_verified=False, root_semantic_width_closure_required=True,
        real_scoring_calls=0, model_calls=0, hardware_calls=0)
    if index_path.exists():
        index_binding = bind(index_path)
        index = read(index_path)
        if (index.get('status') != 'COMPLETE_ADMITTED_POLICY_REPLAY_ONLY'
                or index.get('source_plan') != plan['width_plan'] or index.get('completed') != 3840
                or index.get('requested') != 3840 or index.get('new_neural_jobs') != 0
                or index.get('hardware_jobs') != 0 or index.get('scoring_complete') is not False
                or sorted(index.get('jobs', [])) != sorted(expected_jobs)):
            raise ValueError('Present index is not exact complete replay evidence; no scoring proposal admission')
        rows = index['rows']
        expected = {cell_key(c): c for c in plan['new_cells']}
        if len(rows) != 3840 or len({cell_key(row) for row in rows}) != 3840 or {cell_key(row) for row in rows} != set(expected):
            raise ValueError('Prediction index coverage is missing, duplicate or outside matrix')
        total = 0
        populations = {}
        for n, row in enumerate(rows, 1):
            cell = expected[cell_key(row)]
            if (row.get('status') != 'COMPLETE' or row.get('identity_tap') != cell['identity_tap']
                    or Path(row['result']['path']).resolve() != Path(cell['expected_prediction_path']).resolve()):
                raise ValueError('Wrong prediction route/status/path')
            actual = verify(row['result'])
            total += actual['bytes']
            route = row['candidate_id'] + '/' + row['stream']
            populations.setdefault(route, Counter())[cell['population']] += 1
            if n % 960 == 0:
                print(json.dumps(dict(phase='READ_ONLY_PREDICTION_BINDING',verified=n,requested=3840)), flush=True)
        if any(dict(counts) != plan['populations_per_route'] for counts in populations.values()) or len(populations) != 16:
            raise ValueError('Actual route population coverage differs')
        verify(index_binding)
        observation.update(status='COMPLETE_INDEX_BOUND_READ_ONLY_PENDING_ROOT_WIDTH_CLOSURE',
            prediction_indices=[index_binding], validated_prediction_bytes=total, validated_prediction_files=len(rows),
            actual_prediction_coverage_verified=True, exact_jobs=expected_jobs, route_population_counts=populations,
            semantic_scope='Exact index metadata/coverage/path and actual compressed-byte bindings; upstream process/semantic closure and future scorer payload checks remain separate')
    packages = {name: version(name) for name in plan['packages']}
    if packages != plan['packages']:
        raise ValueError('Use the pinned analysis interpreter')
    executable = bind(sys.executable)
    dependency_bindings = [verify(value) for value in plan['adapter_sources'] + plan['scorer_codes']]
    review_path = report / 'angles' / 'width_score_protocol_review_v1' / 'INDEPENDENT_SCORE_PROTOCOL_REVIEW_V1.json'
    review = read(review_path)
    if review.get('status') != 'PASS_EXACT_SOURCE_AND_51_SYNTHETIC_CHECKS' or review.get('wrapper_sha256') != WRAPPER_SHA:
        raise ValueError('Independent final protocol acceptance missing')
    review_bindings = [bind(review_path), verify(review['review']),
        bind(report / 'angles' / 'width_scorer_plan_v2' / 'ROOT_SCORER_SOURCE_REVIEW_V1.json'),
        bind(report / 'runner' / 'independent_runner_write_review_v1' / 'INDEPENDENT_RUNNER_WRITE_REVIEW_V3_FINAL.json')]
    root_closure_path = report / 'angles' / 'operational_width_v1' / 'ROOT_WIDTH_CLOSURE_AND_SCORE_SOURCE_ACCEPTANCE_V1.json'
    root_closure_binding = bind(root_closure_path, '5db5357af922256ac544286bee12c0047b2bcabb8ec70bbffb20ea6d9bce374f')
    root_closure = read(root_closure_path)
    if (root_closure.get('width_status') != '3840_POLICY_CELLS_COMPLETE_SCORING_PENDING'
            or not all(root_closure['width_protocol']['semantic_checks'].values())
            or observation['prediction_indices'] != [root_closure['width_protocol']['index']]):
        raise ValueError('Exact root width closure and current prediction index differ')
    observation.update(status='COMPLETE_INDEX_AND_ALL3840_FILES_BOUND_ROOT_WIDTH_CLOSURE_ACCEPTED',
        root_semantic_width_closure_required=False,root_width_closure=root_closure_binding)
    review_bindings.append(root_closure_binding)
    future = report / 'runner' / 'width_score_queue_v1'
    fresh_paths = [future, Path(plan['analysis_report_root']), Path(plan['bulk_score_payload_root'])]
    if any(path.exists() for path in fresh_paths):
        raise ValueError('Intended production/scoring output namespace is not fresh')
    output.mkdir(parents=True)
    epoch = output / 'source_epoch'; epoch.mkdir()
    copies = []
    for source in (Path(protocol_source), Path(protocol_source).with_name('README_S6D_WIDTH_SCORE_PROTOCOL.md')):
        target = epoch / source.name
        shutil.copyfile(source, target)
        if bind(source)['sha256'] != bind(target)['sha256']:
            raise ValueError('Snapshot differs')
        copies.append(dict(maintained=bind(source), snapshot=bind(target)))
    readme = Path(__file__).with_name('README_S6D_SCORE_QUEUE_PREPARATION.md')
    shutil.copyfile(readme, output / 'README.md')
    future_admission = future / 'ROOT_SCORER_ADMISSION_V1.json'
    protocol = future / 'protocol' / JOB_ID
    complete = protocol / 'COMPLETION.json'
    periodic = [runner_binding] + [pair['snapshot'] for pair in copies] + [plan_binding] + dependency_bindings + observation['prediction_indices']
    periodic = list({value['path']: value for value in periodic}.values())
    if any(b['bytes'] > 16 * 1024 ** 2 for b in periodic) or sum(b['bytes'] for b in periodic) > 64 * 1024 ** 2:
        raise ValueError('Periodic runner source limits exceeded')
    expected_fields = {'status':'COMPLETE','failure':None,'protocol_observer_closed':True,'protocol_errors':[],
        'stop_requested':False,'scoring_complete':True,'committed_new_scores':3840,'hardware_calls':0,'model_calls':0,
        'semantic_checks.committed_new_scores':3840,'semantic_checks.exact_coverage_cells':5760,
        'semantic_checks.exact_scene_cells':5760,'semantic_checks.bound_aggregate_artifacts':15,
        'adapter_plan.sha256':PLAN_SHA,'wrapper.sha256':WRAPPER_SHA,'scorer.sha256':plan['adapter_sources'][0]['sha256'],
        'admission.sha256':None}
    job = dict(job_id=JOB_ID,kind='offline',workload='cached',
        argv=[str(Path(sys.executable).resolve()),str(epoch / Path(protocol_source).name),
              '--adapter-plan',str(Path(adapter_plan).resolve()),'--authorization',str(future_admission),
              '--prediction-indices',str(index_path)],cwd=str(sim),
        environment={'PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1'},
        source_bindings=periodic,heartbeat_path=str(protocol / 'HEARTBEAT.json'),
        completion_path=str(complete),stop_request_path=str(protocol / 'STOP_REQUEST.json'),
        timeout_s=14400,stall_after_s=1800,heartbeat_stale_s=45,stop_grace_s=45,allow_owned_termination=True,
        expected_artifacts=[dict(path=str(complete),format='json',min_bytes=1,expected_fields=expected_fields),
            dict(path=str(Path(plan['analysis_report_root']) / 'SCORING_RECEIPT.json'),format='json',min_bytes=1,
                expected_fields={'schema':'s6d-width-scoring-receipt.v1','status':'COMPLETE_BOUNDED_MATRIX_SCORING',
                    'adapter_plan.sha256':PLAN_SHA,'prediction_indices':observation['prediction_indices'],
                    'scored_new_cells':3840,'reused_exact_control_cells':1920,'total_scored_cells':5760,
                    'raw_word_invariance_cells':3840,'population_counts_per_route':plan['populations_per_route'],
                    'model_calls':0,'hardware_calls':0,'native_confirmation_required_before_retention':True})],
        scientific_scope='Only frozen width predictions plus exact original controls; no model/hardware execution or retention/native claim')
    proposal = {key:upstream[key] for key in ('run_id','owner_thread_id','owner_session_id','fixture_only','campaign','disk_policy','payload_policy')}
    proposal.update(schema='s6d_score_queue_proposal_v1',production_status='PROPOSAL_ONLY_NOT_RUNNABLE_NO_ROOT_AUTHORIZATION',
        runner_sha256=RUNNER_SHA,jobs=[job],created_utc=datetime.now(timezone.utc).isoformat(),
        final_queue_path=str(future / 'QUEUE.json'), final_state_dir=str(future / 'state'),
        unresolved_required_changes=['Root scoring queue approval using the bound accepted width closure','Create exact root scorer authorization',
            'Add actual authorization binding to job.source_bindings and its SHA256 to completion predicate',
            'If index absent, bind actual complete index and add it to source_bindings/receipt predicate/admission',
            'Change to reviewed runner queue schema only after root review; compute final job and queue digests',
            'Create separate final runner approval and validate before any launch'])
    approval = dict(schema='s6d_score_approval_proposal_v1',run_id=upstream['run_id'],queue_sha256=None,
        authorization_ref=str(future_admission),approved_job_sha256=[],executable_bindings=[executable],
        allowed_working_directories=[str(sim)],allowed_output_roots=upstream['payload_policy']['new_payload_roots'],
        approval_state='WITHHELD_ROOT_REVIEW_REQUIRED',final_approval_path=str(future / 'APPROVAL.json'))
    recipe = dict(schema='s6d-score-admission-recipe.v1',status='INSTRUCTIONS_ONLY_NO_AUTHORIZATION',
        final_admission_path=str(future_admission),required_authorization_values=dict(root_review_passed=False,
            adapter_plan_sha256=PLAN_SHA,prediction_indices=observation['prediction_indices'],protocol_wrapper_sha256=WRAPPER_SHA,
            run_id=upstream['run_id'],job_id=JOB_ID,owner_thread_id=upstream['owner_thread_id'],owner_session_id=upstream['owner_session_id']),
        root_review_false_is_deliberate=True,independent_reviews=review_bindings,
        root_must_bind='Actual width index/outputs and upstream semantic completion/process exit, these exact sources, actual reviewed scoring queue/admission.',
        timing_proposal='14400 s total,1800 s no-new-score stall,45 s heartbeat and stop grace. Bounds are conservative proposals, not measured scorer performance. Root must review aggregation allowance.',
        finalization_order=['Review exact width semantic closure and index validation',
            'Recheck fresh outputs, deadline, C50/G75 and total40GiB cap without editing inherited floors',
            'Root creates admission from required values only after approval, sets root_review_passed true, adds concrete review evidence and binds exact bytes',
            'Root creates QUEUE.json from proposal: accepted schema, actual admission/index source bindings and expected predicates; remove proposal-only fields',
            'Compute each job digest using runner.digest canonical sorted compact JSON; compute SHA256 of final QUEUE.json bytes',
            'Root creates APPROVAL.json with accepted schema, queue hash, approved job digest and actual executable/output allowlist',
            'Run reviewed runner --validate-only with literal final queue and approval hashes; independent root review closes that result',
            'Only root may then launch the literal validated runner command; never call scorer/wrapper directly'],
        production_authorization_created=False,production_jobs_launched=0)
    artifacts = [save(output / 'INDEX_VALIDATION.json', observation),save(output / 'QUEUE_PROPOSAL.json',proposal),
        save(output / 'APPROVAL_PROPOSAL.json',approval),save(output / 'ROOT_ADMISSION_RECIPE.json',recipe),bind(output / 'README.md')]
    frozen = dict(schema='s6d-score-queue-preparation-freeze.v1',status='PROSPECTIVE_QUEUE_PREPARED_NO_AUTHORIZATION',
        source_queue=queue_binding,adapter_plan=plan_binding,source_pairs=copies,runner=runner_binding,executable=executable,
        packages=packages,scorer_source_graph=dependency_bindings,independent_reviews=review_bindings,
        preparation_sources=[bind(__file__),bind(readme)],artifacts=artifacts,
        prediction_indices=observation['prediction_indices'],source_bytes_periodically_checked=sum(b['bytes'] for b in periodic),
        hardware_calls=0,model_calls=0,real_scoring_calls=0,production_authorization_created=False,production_jobs_launched=0,
        unchanged_output_namespaces=[str(p) for p in fresh_paths])
    freeze_binding = save(output / 'SOURCE_FREEZE.json',frozen)
    print(json.dumps(dict(status=frozen['status'],freeze=freeze_binding,index_status=observation['status'],
        index_bindings=observation['prediction_indices'],predictions_verified=observation.get('validated_prediction_files',0)),indent=2),flush=True)


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('output','width-queue','adapter-plan','protocol-source','runner'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    prepare(a.output,a.width_queue,a.adapter_plan,a.protocol_source,a.runner)
