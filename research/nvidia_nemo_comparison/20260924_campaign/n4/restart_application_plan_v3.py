import restart_family_v3 as family
"""Selected two-session application plans; see README_RESTART_FAMILY_V3.md."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import time

from common import audio_only, bind, fingerprint, freeze, load, verify
from metric_process import exact_process, identity, pin
from paced_child_admission import assert_plain_path
import paced_panel_plan as original
import paced_panel_plan_guarded_v2 as panels
import guarded_execution_v1 as resource
from restart_plan_policy import JOBS, POLICY, stop_after_samples
from review_scoring_bank import require

HERE = Path(__file__).resolve().parent
LOCAL = family.LOCAL
SCHEMA = 'n4-restart-application-plan-v3'
STATUS = 'PREPARED_SELECTED_RESTART_PAIRS_ONLY'
APPLICATION_POLICY = dict(schema='n4-restart-application-variant-v1',
    cell_module='restart_application_cell', variant='same-controller-restart-v1',
    success_status='COLLECTED_RESTART_PAIR_CLOSED_REQUIRES_REVIEW',
    independent_two_session_review_required=True)
OWN = ('restart_plan_policy.py', 'restart_application_plan.py', 'test_restart_plan.py',
       'probe_restart_plan.py', 'README_RESTART_FAMILY_V3.md')


def lifecycle_qualification():
    binding = bind(HERE/'RESTART_APPLICATION_CHECK_V1.json'); value = load(binding['path'])
    require(value['status'] == 'PASS_RESTART_APPLICATION_DEVELOPMENT_ONLY', 'Restart lifecycle not qualified')
    for b in value['code']+[value['private_receipt']]: verify(b)
    result = load(value['private_receipt']['path']); verify(result['admission'])
    admitted = load(result['admission']['path'])
    require(result['status'] == 'PASS_RESTART_APPLICATION_DEVELOPMENT_CHECKS_ONLY'
        and result['tests_passed'] == 21 and admitted['code'] == value['code']
        and exact_process(admitted['owner']) is None, 'Lifecycle qualification or stopped probe differs')
    require(result['actual_restart_pair'] is False and result['actual_restart_qualified'] is False
        and result['integrated_N4_cells'] == 0 and result['N4_accepted'] is False,
        'Development qualification cannot claim a model-backed restart')
    verify(binding)
    return binding, value


def code_bindings():
    return family.code_bindings()


def row_key(plan, row):
    return dict(schema=SCHEMA, cell_id=row['cell_id'], composition=row['composition'],
        job=row['job'], contract=row['contract'], kind=row['kind'], repeat=row['repeat'],
        stop_after_samples=row['stop_after_samples'], restart=plan['restart'],
        execution=plan['execution'], context_sha256=fingerprint(plan['context']),
        panel=plan['panel'], lifecycle_qualification=plan['lifecycle_qualification'])


def build_plan(panel_binding, panel, lifecycle_binding):
    """Pure fixture-compatible builder; production requires reconstruct/admit_plan."""
    require(panel['schema'] == panels.SCHEMA and panel['status'] == 'PREPARED_PANELS_AND_REPEATS_ONLY'
        and panel['execution'] == original.EXECUTION_POLICY and panel['source_relationship'] == panels.adapter.previous.SOURCE_RELATIONSHIP
        and panel['context']['application_policy'] == panels.APPLICATION_POLICY,
        'Qualified actual guarded source panel required')
    candidates = original.validate_selection(panel['selection'], panel['reviews'])
    require(panel['candidates'] == candidates and panel['required'] == len(candidates)*40
        and len(panel['rows']) == panel['required'] and panel['integrated_N4_cells'] == 0
        and panel['N4_accepted'] is False, 'Source panel population differs')
    contracts = {}; jobs = {}; seen = set(); counts = {c: {} for c in candidates}
    for index, row in enumerate(panel['rows']):
        payload = panels.execution_payload(panel, index); candidate = row['composition']; job = payload['job']
        require(candidate in candidates and candidate == '_'.join(payload['contract'][k] for k in ('variant','diarization','encoder')),
            'Selected contract/composition differs')
        require(candidate not in contracts or contracts[candidate] == payload['contract'], 'Inconsistent composition contract')
        contracts[candidate] = payload['contract']; key = (candidate, job['job_id'], row['kind'], row['repeat'])
        require(key not in seen, 'Duplicate source panel occurrence'); seen.add(key)
        require((row['kind'] == 'panel' and row['repeat'] == 0)
            or (row['kind'] == 'timing_repeat' and row['repeat'] in (1,2) and job['job_id'] in original.ANCHORS),
            'Source panel occurrence scope differs')
        counts[candidate][row['kind']] = counts[candidate].get(row['kind'], 0)+1
        require(job['job_id'] not in jobs or jobs[job['job_id']] == job, 'Saved job differs across candidates or repeats')
        jobs[job['job_id']] = deepcopy(job)
    require(all(c == {'panel':24,'timing_repeat':16} for c in counts.values()), 'Incomplete source panel/repeat census')
    for candidate in candidates:
        for jid in JOBS:
            stop_after_samples(jobs[jid])
            require(all((candidate,jid,kind,repeat) in seen for kind,repeat in (('panel',0),('timing_repeat',1),('timing_repeat',2))),
                'Both fixed tap anchors must be present for every candidate')
    context = deepcopy(panel['context']); context['application_policy'] = deepcopy(APPLICATION_POLICY)
    plan = dict(schema=SCHEMA,status=STATUS,panel=deepcopy(panel_binding),lifecycle_qualification=deepcopy(lifecycle_binding),
        context=context,execution=deepcopy(original.EXECUTION_POLICY),restart=deepcopy(POLICY),
        candidates=deepcopy(candidates),required=len(candidates)*2,required_sessions=len(candidates)*4,rows=[],
        source_execution_authorized=False,actual_restart_qualified=False,integrated_N4_cells=0,N4_accepted=False)
    for candidate in candidates:
        for jid in JOBS:
            job = jobs[jid]
            row = dict(cell_id='restart_0_'+jid+'_'+candidate,composition=candidate,job=deepcopy(job),
                contract=deepcopy(contracts[candidate]),kind='restart_pair',repeat=0,
                stop_after_samples=stop_after_samples(job),collection_credit=0)
            row['cache_key'] = fingerprint(row_key(plan,row)); plan['rows'].append(row)
    return plan


def execution_payload(plan, index):
    require(plan['schema'] == SCHEMA and plan['status'] == STATUS and plan['restart'] == POLICY
        and plan['execution'] == original.EXECUTION_POLICY and plan['context']['application_policy'] == APPLICATION_POLICY,
        'Wrong restart plan or execution policy')
    require(plan['source_execution_authorized'] is False and plan['actual_restart_qualified'] is False
        and plan['N4_accepted'] is False and plan['integrated_N4_cells'] == 0, 'Preparation cannot confer execution or acceptance')
    candidates = plan['candidates']
    require(1 <= len(candidates) <= 6 and candidates[0] == original.BASELINE and len(set(candidates)) == len(candidates)
        and set(candidates) <= original.COMPOSITIONS and plan['required'] == len(candidates)*2
        and plan['required_sessions'] == len(candidates)*4 and len(plan['rows']) == plan['required'], 'Restart population differs')
    require(type(index) is int and 0 <= index < plan['required'], 'Invalid restart cell index')
    row = plan['rows'][index]; job = audio_only(row['job']); candidate = candidates[index//2]
    require(set(row) == {'cell_id','composition','job','contract','kind','repeat','stop_after_samples','collection_credit','cache_key'},
        'Restart row allowlist differs')
    require(row['composition'] == candidate and job['job_id'] == JOBS[index%2]
        and row['cell_id'] == 'restart_0_'+job['job_id']+'_'+candidate and row['kind'] == 'restart_pair'
        and row['repeat'] == 0 and row['collection_credit'] == 0
        and candidate == '_'.join(row['contract'][k] for k in ('variant','diarization','encoder'))
        and row['contract']['mode'] == original.MAIN_MODE, 'Restart row identity or route differs')
    require(type(row['stop_after_samples']) is int and row['stop_after_samples'] == stop_after_samples(job)
        and row['cache_key'] == fingerprint(row_key(plan,row)), 'Restart threshold or source binding changed')
    context = plan['context']
    require(set(context['runtimes']) == {'n2_runtime.json','n3_runtime.json'}, 'Exact runtimes required')
    # Keep the existing 13-field child allowlist. The fixed future runner derives
    # the midpoint with restart_plan_policy, never by reading evaluator/plan data.
    return dict(schema='n4-paced-cell-input-v1',cell_id=row['cell_id'],job=deepcopy(job),contract=deepcopy(row['contract']),
        execution=deepcopy(plan['execution']),source_receipt=deepcopy(context['source_receipt']),catalog=deepcopy(context['catalog']),
        runtimes=[deepcopy(context['runtimes'][n]) for n in sorted(context['runtimes'])],
        gallery_preparation=deepcopy(context['gallery_preparation']),models_root=context['models_root'],assets=deepcopy(context['assets']),
        source_execution_authorized=False,
        remaining_gate='Exact supervised exclusive-slot owner, frozen launcher and live resource/deadline admission required')


def reconstruct(panel_path):
    pb, panel = panels.admit_plan(panel_path); qb, _ = lifecycle_qualification()
    value = build_plan(pb, panel, qb)
    for i in range(value['required']): execution_payload(value,i)
    verify(pb); verify(qb)
    return value


def admit_plan(path):
    path = assert_plain_path(Path(path),LOCAL/'n4'); binding = bind(path)
    require(path.name == 'PLAN.json', 'Fixed restart plan filename required')
    _, admission, _, result = family.closed_execution(path.parent, 'prepare')
    code = code_bindings(); qb, q = family.qualification(code)
    require(admission['panel'] == admission['plan'], 'Input panel binding differs')
    require(result['status'] == STATUS and result['plan'] == binding and result['source_execution_authorized'] is False
        and result['actual_restart_qualified'] is False and result['integrated_N4_cells'] == 0
        and result['N4_accepted'] is False, 'Restart plan receipt differs')
    rebuilt = reconstruct(Path(admission['panel']['path']))
    require(load(path) == rebuilt and result['required'] == rebuilt['required']
        and result['required_sessions'] == rebuilt['required_sessions'], 'Restart plan reconstruction differs')
    for b in code+[binding,qb]: verify(b)
    return binding, rebuilt


def prepare(args):
    output = args.output.resolve(); code = code_bindings(); pb = bind(args.panel_plan)
    g = family.start_output(output, pb, 'prepare', code, dict(panel=pb))
    checks = []
    try:
        with g:
            checks.append(resource.save_check(g, 'GUARD_INITIAL.json'))
            plan = reconstruct(args.panel_plan); g.fast_check()
            require(plan['panel'] == pb, 'Input panel changed during reconstruction')
            for b in code+[pb]: verify(b)
            freeze(output/'PLAN.json', plan)
            checks.append(resource.save_check(g, 'GUARD_FINAL.json')); g.fast_check()
            freeze(output/'RESULT.json', dict(status=STATUS, utc=datetime.now(timezone.utc).isoformat(),
                admission=g.admission, execution_plan=bind(output/'EXECUTION_PLAN.json'), guard_checks=checks,
                plan=bind(output/'PLAN.json'), required=plan['required'], required_sessions=plan['required_sessions'],
                source_execution_authorized=False, actual_restart_qualified=False, integrated_N4_cells=0, N4_accepted=False))
    except BaseException as exc:
        freeze(output/'FAILED.json', dict(status='FAILED_GUARDED_RESTART_PREPARATION_PRESERVED',
            admission=g.admission, guard_checks=checks, error_type=type(exc).__name__, error=str(exc)[:2000], N4_accepted=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--panel-plan',type=Path,required=True); parser.add_argument('--output',type=Path,required=True)
    prepare(parser.parse_args())
