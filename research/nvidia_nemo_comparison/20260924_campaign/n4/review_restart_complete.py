"""Complete restart transport/observation review. README_RESTART_COMPLETE_REVIEW.md."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import time

from common import bind, fingerprint, freeze, load, verify
from metric_process import exact_process, identity, pin
from paced_child_admission import assert_plain_path
from restart_application_plan import execution_payload
from review_restart_run import stopped_run, directory_names, validate_population, LOCAL
from review_restart_transport import review_cell as review_transport, record
from review_restart_observations import review_observations, session_windows
from review_scoring_bank import guard, require, shared_allowance
from scoring_bank import writer_lock

HERE = Path(__file__).resolve().parent
OWN = ('review_restart_complete.py', 'test_restart_complete.py', 'probe_restart_complete.py',
       'README_RESTART_COMPLETE_REVIEW.md')
QUALIFICATION = 'RESTART_COMPLETE_REVIEW_CHECK_V1.json'
CELL_STATUS = 'PASS_RESTART_TRANSPORT_AND_OBSERVATIONS_JOINED_ONLY'
RUN_STATUS = 'PASS_COMPLETE_SELECTED_RESTART_OBSERVATIONS_ONLY'


def code_bindings():
    qb, q = record(HERE/'RESTART_OBSERVATION_CHECK_V1.json', HERE)
    require(q['status'] == 'PASS_RESTART_OBSERVATION_DEVELOPMENT_ONLY', 'Observation qualification differs')
    verify(q['private_receipt']); verify(q['private_admission'])
    require(load(q['private_receipt']['path'])['admission'] == q['private_admission']
            and exact_process(load(q['private_admission']['path'])['owner']) is None, 'Observation admission/owner differs')
    result = {}
    for b in q['code']+[qb]+[bind(HERE/n) for n in OWN]:
        verify(b); require(b['path'] not in result or result[b['path']] == b, 'Conflicting complete-review dependency')
        result[b['path']] = b
    return [b for _, b in sorted(result.items())]


def join_reviews(folder, payload, transport, observations):
    """Join separately reconstructed evidence; never promote these checks to acceptance."""
    folder = Path(folder).resolve(strict=True)
    require(transport['status'] == 'PASS_RESTART_TRANSPORT_AND_PAIR_JOINS_ONLY'
            and observations['status'] == 'PASS_RESTART_OBSERVATION_ATTRIBUTION_ONLY', 'Independent restart readers required')
    require(transport['cell_id'] == payload['cell_id'] and observations['viewport_rows_reviewed'] is True
            and observations['resource_samples_reviewed'] is True, 'Cell identity or observation coverage differs')
    for value in (transport, observations):
        require(value['actual_restart_qualified'] is False and value['N4_accepted'] is False
                and type(value['integrated_N4_cells']) is int and value['integrated_N4_cells'] == 0
                and value['source_to_widget_latency_qualified'] is False and value['controlled_resources_qualified'] is False,
                'Independent review improperly promoted acceptance')
    require(fingerprint(transport['pair_review']) == fingerprint(observations['pair_review']),
            'Pair changed between transport and observation reconstruction')
    pair = observations['pair_review']
    require(pair['cell_id'] == payload['cell_id'] and pair['application_owner'] == transport['application']
            and pair['full_job_sha256'] == fingerprint(payload['job']), 'Observed owner or full planned job differs')
    require(observations['native_caption_payloads_joined'] is False, 'Observation component cannot qualify native semantics')
    windows = session_windows(pair['sessions'])
    resources = observations['resource_review']
    require(resources['status'] == 'PASS_RESTART_RESOURCE_WINDOW_ATTRIBUTION_ONLY'
            and resources['reconstruction']['owner'] == transport['application'] and resources['windows'] == windows,
            'Resource observations belong to another owner or session interval')
    viewports = observations['viewport_reviews']
    require(len(viewports) == 2, 'Both ordered viewport reviews required')
    for index, value in enumerate(viewports):
        require(value['status'] == 'PASS_RESTART_VIEWPORT_SESSION_ATTRIBUTION_ONLY'
                and value['session'] == windows[index]['session']
                and value['reconstruction']['source_origin_monotonic_sec'] == windows[index]['start']
                and value['native_caption_payloads_joined'] is False and value['source_to_widget_latency_qualified'] is False,
                'Viewport review order, origin or semantics differs')
    records = {}
    for b in transport['evidence']+observations['evidence']:
        require(b['path'] not in records or records[b['path']] == b, 'Evidence changed between independent restart readers')
        records[b['path']] = b
    cb, _ = record(folder/'COLLECTED.json', folder)
    rb, _ = record(folder/'application/RESULT.json', folder)
    require(cb == transport['collected'] and rb == pair['cell_result']
            and records.get(cb['path']) == cb and records.get(rb['path']) == rb, 'Fixed cell receipts were not independently joined')
    for b in records.values(): verify(b)
    require(exact_process(transport['application']) is None and exact_process(transport['coordinator']) is None,
            'Reviewed process identity is still active')
    return dict(status='PASS_RESTART_COMMON_EVIDENCE_JOIN_ONLY', cell_id=payload['cell_id'], collected=cb,
        evidence=list(records.values()), source_windows=windows, observed_sessions=2,
        both_sessions_have_complete_resource_samples=resources['both_sessions_have_complete_samples'],
        current_viewport_spans=[v['current_spans'] for v in viewports], retained_viewport_spans=[v['retained_spans'] for v in viewports],
        native_caption_payloads_joined=False, actual_restart_qualified=False, integrated_N4_cells=0, N4_accepted=False)


def review_cell(folder, *, checkpoint=None, **expected):
    if checkpoint: checkpoint()
    transport = review_transport(folder, checkpoint=checkpoint, **expected)
    if checkpoint: checkpoint()
    observations = review_observations(Path(folder)/'application', payload=expected['payload'],
        application_owner=transport['application'], checkpoint=checkpoint)
    joins = join_reviews(folder, expected['payload'], transport, observations)
    if checkpoint: checkpoint()
    return dict(status=CELL_STATUS, cell_id=expected['payload']['cell_id'], collected=transport['collected'],
        transport=transport, observations=observations, joins=joins, viewport_rows_reviewed=True, resource_samples_reviewed=True,
        complete_selected_population_reviewed=False, native_caption_payloads_joined=False, actual_restart_qualified=False,
        source_to_widget_latency_qualified=False, controlled_resources_qualified=False, integrated_N4_cells=0, N4_accepted=False)


def review_population(context, output, *, checkpoint):
    """Internal driver; context must come from the unchanged stopped_run admission."""
    folder = context['folder']; plan = context['plan']; names = directory_names(folder)
    collected = []; progress = []; progress_bindings = []
    for index, row in enumerate(plan['rows']):
        checkpoint()
        cb, _ = record(folder/'cells'/row['cell_id']/'COLLECTED.json', folder); collected.append(cb)
        pb, value = record(folder/'progress'/f'{index+1:04d}.json', folder)
        progress.append(value); progress_bindings.append(pb)
    population = validate_population(plan, context['terminal'], collected, progress, *names)
    reviewed = []; all_evidence = {}
    def keep(b):
        require(b['path'] not in all_evidence or all_evidence[b['path']] == b, 'Cross-pair evidence changed')
        all_evidence[b['path']] = b
    for b in context['bindings']+[context['plan_binding']]+collected+progress_bindings: keep(b)
    coverage = []; owners = set(); native_sessions = set()
    for index, row in enumerate(plan['rows']):
        checkpoint(); payload = execution_payload(plan, index)
        value = review_cell(folder/'cells'/row['cell_id'], payload=payload, plan_sha256=fingerprint(plan),
            coordinator=context['coordinator'], code=context['code'], parent_code=context['parent_code'],
            executable=context['executable'], coordinator_argv=context['coordinator_argv'], state=context['state'], checkpoint=checkpoint)
        require(value['status'] == CELL_STATUS and value['collected'] == collected[index] and value['cell_id'] == row['cell_id']
                and value['viewport_rows_reviewed'] is True and value['resource_samples_reviewed'] is True
                and value['actual_restart_qualified'] is False and value['N4_accepted'] is False,
                'Cell changed, incomplete observation coverage or promoted acceptance')
        owner = value['transport']['application']; key = (owner['pid'], owner['create_time'])
        sessions = [s['native_session'] for s in value['transport']['pair_review']['sessions']]
        require(key not in owners and len(sessions) == len(set(sessions)) == 2 and not native_sessions.intersection(sessions),
                'Different pair cells reused an application identity or native session')
        owners.add(key); native_sessions.update(sessions)
        for b in value['joins']['evidence']: keep(b)
        target = output/'cells'/f'{index+1:04d}.json'; freeze(target, value); reviewed.append(bind(target))
        coverage.append(dict(cell_id=row['cell_id'], sessions=2,
            complete_resource_samples_both_sessions=value['joins']['both_sessions_have_complete_resource_samples']))
    for b in list(all_evidence.values())+reviewed: verify(b)
    require(directory_names(folder) == names and exact_process(context['coordinator']) is None,
            'Run directories or coordinator changed during review')
    checkpoint()
    return dict(population=population, pair_reviews=reviewed, coverage=coverage, input_evidence=list(all_evidence.values()),
        all_pairs_have_complete_resource_samples=all(r['complete_resource_samples_both_sessions'] for r in coverage))


def run(run_root, output):
    process = pin(); started = time.monotonic(); output = assert_plain_path(output, LOCAL/'n4')
    require(not output.exists() and not output.is_relative_to(run_root.resolve())
            and not run_root.resolve().is_relative_to(output), 'Fresh private output separate from run required')
    with writer_lock(LOCAL/'n4/metric-scoring.owner.lock'):
        check = lambda: guard(output, LOCAL, started, 3600)
        check(); inventory = shared_allowance(LOCAL)
        freeze(output/'REVIEW_OWNER.json', dict(owner=identity(process), run=str(run_root.resolve()), utc=datetime.now(timezone.utc).isoformat()))
        try:
            code = code_bindings(); qb, q = record(HERE/QUALIFICATION, HERE)
            require(q['status'] == 'PASS_RESTART_COMPLETE_REVIEW_DEVELOPMENT_ONLY' and q['code'] == code, 'Complete reviewer not qualified')
            verify(q['private_receipt']); verify(q['private_admission'])
            require(exact_process(load(q['private_admission']['path'])['owner']) is None, 'Qualification probe still active')
            context = stopped_run(run_root)
            freeze(output/'ADMISSION.json', dict(owner=identity(process), run_admission=context['admission'], plan=context['plan_binding'],
                code=code, qualification=qb, inventory=inventory))
            result = review_population(context, output, checkpoint=check)
            for b in code+[qb, q['private_receipt'], q['private_admission']]+result['input_evidence']+result['pair_reviews']: verify(b)
            check()
            freeze(output/'REVIEW.json', dict(result, status=RUN_STATUS, utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'), complete_planned_evidence_population_reviewed=True,
                viewport_rows_reviewed=True, resource_samples_reviewed=True, native_caption_payloads_joined=False,
                full_lease_history_available=False, complete_process_history_available=False,
                actual_restart_qualified=False, source_to_widget_latency_qualified=False, controlled_resources_qualified=False,
                physical_scanout_measured=False, deployment_tier='UNKNOWN', integrated_N4_cells=0, N4_accepted=False))
            print('Complete selected restart transport/viewport/resource evidence joined; functional acceptance remains separate', flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json', dict(status='FAILED_COMPLETE_RESTART_REVIEW_PRESERVED', owner=identity(process),
                error_type=type(exc).__name__, error=str(exc)[:2000], actual_restart_qualified=False, integrated_N4_cells=0, N4_accepted=False))
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True); args = parser.parse_args(); run(args.run, args.output)
