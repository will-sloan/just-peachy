"""Complete restart transport/observation review. README_RESTART_CONTENT_RUN.md."""
import argparse
from datetime import datetime, timezone, timedelta
import shutil
import json
import os
from pathlib import Path
import time

from common import bind, fingerprint, freeze, load, verify
from metric_process import exact_process, identity, pin
from paced_child_admission import assert_plain_path
from restart_application_plan import execution_payload
from review_restart_run import stopped_run, directory_names, validate_population, LOCAL
from review_restart_transport import review_cell as review_transport, record
from review_restart_observations import review_observations, session_windows
from review_scoring_bank import require
from review_scoring_bank_v3 import shared_allowance
from review_restart_content_cell import review_cell, CELL_STATUS
from scoring_bank import writer_lock

HERE = Path(__file__).resolve().parent
OWN = ('review_restart_content_cell.py', 'review_restart_content_run.py',
       'test_restart_content_run.py', 'probe_restart_content_run.py', 'README_RESTART_CONTENT_RUN.md')
QUALIFICATION = 'RESTART_CONTENT_RUN_CHECK_V1.json'
RUN_STATUS = 'PASS_COMPLETE_SELECTED_RESTART_CONTENT_ONLY'
OUTPUT_LIMIT = 64*1024**2


def code_bindings():
    result = {}
    prerequisites = (
        ('RESTART_COMPLETE_REVIEW_CHECK_V1.json','PASS_RESTART_COMPLETE_REVIEW_DEVELOPMENT_ONLY','code'),
        ('RESTART_NATIVE_CONTENT_CHECK_V1.json','PASS_RESTART_NATIVE_CONTENT_DEVELOPMENT_ONLY','code'),
        ('APPLICATION_CONTENT_CHECK_V1.json','PASS_APPLICATION_CONTENT_COMPOSITION_DEVELOPMENT_ONLY','code'),
        ('SCORING_HISTORY_CHECK_V3.json','PASS_SCORING_HISTORY_DERIVATIVE_DEVELOPMENT_ONLY','review_code'))
    for name, status, key in prerequisites:
        qb, q = record(HERE/name, HERE)
        require(q['status'] == status, 'Restart content prerequisite differs: '+name)
        verify(q['private_receipt']); receipt = load(q['private_receipt']['path']); verify(receipt['admission'])
        require(exact_process(load(receipt['admission']['path'])['owner']) is None, 'Prerequisite probe remains active')
        for b in q[key]+[qb]:
            verify(b); require(b['path'] not in result or result[b['path']] == b, 'Conflicting content dependency')
            result[b['path']] = b
    for name in OWN:
        b=bind(HERE/name);result[b['path']]=b
    return [b for _, b in sorted(result.items())]


def guard(output, local, started, seconds):
    require(time.monotonic()-started < seconds, 'Restart content review time budget reached')
    policy=load(local/'supervision/campaign.json')
    require(datetime.now(timezone.utc)<datetime.fromisoformat(policy['target_utc'])-timedelta(hours=12),
            'Packaging reserve reached')
    for drive,floor in (('C:/',50),('G:/',75)):
        require(shutil.disk_usage(drive).free >= floor*1024**3+OUTPUT_LIMIT, 'Review drive floor unavailable')
    if output.exists():
        require(sum(p.stat().st_size for p in output.rglob('*') if p.is_file()) < OUTPUT_LIMIT,
                'Restart content review output bound reached')


def freeze_bounded(path, value, output):
    """Reject the complete next receipt before creating it; retain failure space."""
    require(Path(path).resolve().is_relative_to(Path(output).resolve()), 'Output escaped review directory')
    used=sum(p.stat().st_size for p in output.rglob('*') if p.is_file()) if output.exists() else 0
    size=len(os.linesep.encode())
    for chunk in json.JSONEncoder(indent=2,ensure_ascii=False,allow_nan=False).iterencode(value):
        size+=len(chunk.replace('\n',os.linesep).encode('utf-8'))
        require(used+size+65536<=OUTPUT_LIMIT, 'Next complete review receipt exceeds output bound')
    freeze(path,value)


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
                and value['native_caption_payloads_joined'] is True
                and value['fixed_display_roster_independently_joined'] is True
                and value['source_delivery_independently_joined'] is True
                and value['actual_restart_qualified'] is False and value['N4_accepted'] is False,
                'Cell changed, incomplete observation coverage or promoted acceptance')
        owner = value['transport']['application']; key = (owner['pid'], owner['create_time'])
        sessions = [s['native_session'] for s in value['transport']['pair_review']['sessions']]
        require(key not in owners and len(sessions) == len(set(sessions)) == 2 and not native_sessions.intersection(sessions),
                'Different pair cells reused an application identity or native session')
        owners.add(key); native_sessions.update(sessions)
        for b in value['joins']['evidence']: keep(b)
        target = output/'cells'/f'{index+1:04d}.json'; freeze_bounded(target, value, output); reviewed.append(bind(target))
        coverage.append(dict(cell_id=row['cell_id'], sessions=2,
            complete_resource_samples_both_sessions=value['joins']['both_sessions_have_complete_resource_samples'],
            native_caption_payloads_joined=True,fixed_display_roster_independently_joined=True,
            native_span_population=[w['native_span_population'] for w in value['widgets']],
            observed_span_population=[w['observed_span_population'] for w in value['widgets']]))
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
            require(q['status'] == 'PASS_RESTART_CONTENT_RUN_DEVELOPMENT_ONLY' and q['code'] == code, 'Complete reviewer not qualified')
            verify(q['private_receipt']); verify(q['private_admission'])
            require(exact_process(load(q['private_admission']['path'])['owner']) is None, 'Qualification probe still active')
            context = stopped_run(run_root)
            freeze(output/'ADMISSION.json', dict(owner=identity(process), run_admission=context['admission'], plan=context['plan_binding'],
                code=code, qualification=qb, inventory=inventory,maximum_output_bytes=OUTPUT_LIMIT,
                output_charged_to_contingency=True,max_seconds=3600))
            result = review_population(context, output, checkpoint=check)
            for b in code+[qb, q['private_receipt'], q['private_admission']]+result['input_evidence']+result['pair_reviews']: verify(b)
            check()
            freeze_bounded(output/'REVIEW.json', dict(result, status=RUN_STATUS, utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'), complete_planned_evidence_population_reviewed=True,
                viewport_rows_reviewed=True, resource_samples_reviewed=True, native_caption_payloads_joined=True,
                fixed_display_roster_independently_joined=True,source_delivery_independently_joined=True,
                full_lease_history_available=False, complete_process_history_available=False,
                actual_restart_qualified=False, source_to_widget_latency_qualified=False, controlled_resources_qualified=False,
                physical_scanout_measured=False, deployment_tier='UNKNOWN', integrated_N4_cells=0, N4_accepted=False), output)
            print('Complete selected restart lifecycle/roster/native content joined; timing and functional acceptance remain separate', flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json', dict(status='FAILED_RESTART_CONTENT_RUN_REVIEW_PRESERVED', owner=identity(process),
                error_type=type(exc).__name__, error=str(exc)[:2000], actual_restart_qualified=False, integrated_N4_cells=0, N4_accepted=False))
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True); args = parser.parse_args(); run(args.run, args.output)
