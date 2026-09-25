"""Review all stopped V2 panel cells. README_APPLICATION_PANEL_REVIEW_V2.md."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
import time

from common import bind, fingerprint, freeze, load, verify
from metric_process import exact_process, identity, pin
from paced_child_admission import assert_plain_path
from paced_panel_plan_v2 import admit_plan, execution_payload
from paced_application_runner_v2 import RUN_SCHEMA, code_bindings as runner_code, qualified_interpreter
from review_application_cell_v2 import review_cell
from review_application_transport_v2 import record
from review_scoring_bank import guard, require, shared_allowance
from scoring_bank import writer_lock

HERE = Path(__file__).resolve().parent
LOCAL = Path('G:/Just_Peachy_N1/20260924_campaign/local')
QUALIFICATION = 'APPLICATION_PANEL_REVIEW_CHECK_V2.json'


def code_bindings():
    entries = [bind(HERE/name) for name in ('review_application_panel_v2.py','test_application_panel_review_v2.py',
        'probe_application_panel_review_v2.py','README_APPLICATION_PANEL_REVIEW_V2.md')]
    for name, status in (
        ('APPLICATION_CELL_REVIEW_CHECK_V2.json','PASS_V2_APPLICATION_CELL_REVIEW_DEVELOPMENT_ONLY'),
        ('PACED_RUNNER_CHECK_V2.json','PASS_PACED_RUNNER_V2_DEVELOPMENT_ONLY'),
        ('PACED_PANEL_PLAN_CHECK_V2.json','PASS_JOURNAL_DERIVATIVE_PANEL_PLANNER_DEVELOPMENT_ONLY')):
        q = load(HERE/name); require(q['status'] == status, 'Panel reviewer prerequisite differs')
        verify(q['private_receipt']); proof = load(q['private_receipt']['path']); verify(proof['admission'])
        require(exact_process(load(proof['admission']['path'])['owner']) is None, 'Prerequisite helper still active')
        entries += [bind(HERE/name), *q['code']]
    result = {}
    for b in entries:
        require(b['path'] not in result or result[b['path']] == b, 'Conflicting review dependency')
        result[b['path']] = b
    return list(result.values())


def validate_population(plan, terminal, collected, progress, cell_names, progress_names):
    """Expectations originate in the reconstructed plan, never available folders."""
    required = plan['required']; rows = plan['rows']
    require(type(required) is int and 40 <= required <= 240 and required % 40 == 0
        and len(rows) == required, 'Reconstructed panel census differs')
    ids = [r['cell_id'] for r in rows]
    require(len(set(ids)) == required and len(cell_names) == required and set(cell_names) == set(ids),
        'Missing, extra or duplicated application cell directories')
    expected_progress = [f'{i+1:04d}.json' for i in range(required)]
    require(len(progress_names) == required and set(progress_names) == set(expected_progress),
        'Missing or extra panel progress records')
    require(terminal['schema'] == RUN_SCHEMA and terminal['status'] == 'COLLECTED_PACED_APPLICATION_PANEL_REQUIRES_REVIEW'
        and type(terminal['completed']) is int and type(terminal['required']) is int
        and terminal['completed'] == terminal['required'] == required and terminal['error'] is None
        and terminal['integrated_N4_cells'] == 0 and terminal['N4_accepted'] is False
        and terminal['continuity_included'] is False, 'Terminal run is partial, failed or improperly claims acceptance')
    require(len(collected) == required and len(progress) == required and terminal['collected'] == collected,
        'Terminal collected sequence differs from planned cell order')
    for index, (binding, value) in enumerate(zip(collected, progress)):
        expected = dict(completed=index+1,total=required,cell=binding,integrated_N4_cells=0)
        require(fingerprint(value) == fingerprint(expected), 'Progress receipt differs from exact planned sequence')
    return dict(planned_cells=required, collected_cells=required, additional_or_missing_cells=0,
        population_origin='Reconstructed qualified V2 plan; no available-evidence denominator substitution')


def stopped_run(folder):
    """Production admission path: reconstruct plan and exact fixed runner binding."""
    folder = assert_plain_path(folder,LOCAL/'n4')
    bindings = []
    def read(name):
        b,value = record(folder/name,folder); bindings.append(b); return b,value
    ab,a = read('ADMISSION.json'); _,terminal = read('RESULT.json'); _,owner = read('RUN_OWNER.json'); _,worker = read('worker.json')
    require(a['schema'] == RUN_SCHEMA and a['status'] == 'PREPARED_PACED_APPLICATION_RUN_ONLY'
        and a['actual_application_started'] is False, 'Prepared V2 run admission required')
    require(owner['admission'] == ab == terminal['admission'] and owner['owner'] == terminal['owner']
        and exact_process(a['owner']) is None and exact_process(owner['owner']) is None, 'Run/preparer identity remains active or differs')
    require(Path(a['output']).resolve() == folder and Path(a['state']).resolve() == LOCAL/'supervision', 'Run output/state escaped campaign')
    rq = bind(HERE/'PACED_RUNNER_CHECK_V2.json'); q = load(rq['path'])
    code = runner_code(); executable = qualified_interpreter()
    require(a['qualification'] == rq and q['status'] == 'PASS_PACED_RUNNER_V2_DEVELOPMENT_ONLY'
        and a['code'] == q['code'] == code and a['executable'] == executable, 'Qualified runner or interpreter differs')
    for b in code+[rq,a['plan']]: verify(b)
    plan_binding,plan = admit_plan(Path(a['plan']['path']))
    require(plan_binding == a['plan'] and type(a['required']) is int and a['required'] == plan['required'], 'Run plan/census differs')
    argv = [executable['path'],'-B',str(HERE/'paced_application_runner_v2.py'),'run','--admission',str(folder/'ADMISSION.json')]
    require(worker == dict(argv=argv,cwd=str(HERE)), 'Prepared fixed coordinator command differs')
    for b in bindings: verify(b)
    return dict(folder=folder,admission=ab,plan_binding=plan_binding,plan=plan,terminal=terminal,
        coordinator=owner['owner'],code=code,executable=executable,coordinator_argv=argv,state=Path(a['state']),bindings=bindings)


def compact_cell(checked, row, payload):
    require(checked['status'] == 'PASS_V2_APPLICATION_CELL_EVIDENCE_JOINS_ONLY'
        and checked['integrated_N4_cells'] == 0 and checked['N4_accepted'] is False, 'Joined cell reader did not pass')
    obs = checked['observations']; joins = checked['joins']
    return dict(status='PASS_V2_CELL_EVIDENCE_COVERAGE_ONLY',cell_id=row['cell_id'],composition=row['composition'],
        kind=row['kind'],repeat=row['repeat'],tap=row['job']['tap'],job_id=row['job']['job_id'],
        planned_row_sha256=fingerprint(row),input_sha256=fingerprint(payload),full_reader_result_sha256=fingerprint(checked),
        collected=checked['transport']['collected'],evidence=joins['evidence'],
        native_events=joins['native_events'],consumed_events=joins['consumed_events'],
        coalesced_obsolete_ui_partials=joins['coalesced_obsolete_ui_partials'],
        phase_intervals=obs['phase_intervals'],final_span_census=obs['final_span_census'],
        native_payload_semantics_reviewed=False,accuracy_qualified=False,source_to_widget_latency_qualified=False,
        controlled_resources_qualified=False,deployment_tier='UNKNOWN',integrated_N4_cells=0,N4_accepted=False)


def run(run_root, output):
    process = pin(); started = time.monotonic(); sys.path.insert(0,str(HERE.parents[3]))
    require(not output.exists() and output.resolve().is_relative_to(LOCAL/'n4'), 'Fresh private review output required')
    require(not output.resolve().is_relative_to(run_root.resolve()) and not run_root.resolve().is_relative_to(output.resolve()),
        'Review output and immutable run must be separate')
    with writer_lock(LOCAL/'n4/metric-scoring.owner.lock'):
        guard(output,LOCAL,started,3600); inventory = shared_allowance(LOCAL)
        freeze(output/'REVIEW_OWNER.json',dict(owner=identity(process),run=str(run_root.resolve()),utc=datetime.now(timezone.utc).isoformat()))
        try:
            code = code_bindings(); qb = bind(HERE/QUALIFICATION); qualification = load(qb['path'])
            require(qualification['status'] == 'PASS_V2_PANEL_CENSUS_REVIEW_DEVELOPMENT_ONLY'
                and qualification['code'] == code, 'Panel review code is not qualified')
            for b in code: verify(b)
            context = stopped_run(run_root); folder = context['folder']; plan = context['plan']
            cells = assert_plain_path(folder/'cells',folder); progress_root = assert_plain_path(folder/'progress',folder)
            cell_entries = list(cells.iterdir()); progress_entries = list(progress_root.iterdir())
            require(len(cell_entries) <= 240 and len(progress_entries) <= 240, 'Panel directory census exceeds bound')
            for p in cell_entries: require(assert_plain_path(p,folder).is_dir(), 'Unexpected non-directory cell entry')
            for p in progress_entries: require(assert_plain_path(p,folder).is_file(), 'Unexpected non-file progress entry')
            collected = []; progress = []; progress_bindings = []
            for index,row in enumerate(plan['rows']):
                cb,_ = record(cells/row['cell_id']/'COLLECTED.json',folder); collected.append(cb)
                pb,value = record(progress_root/f'{index+1:04d}.json',folder); progress_bindings.append(pb); progress.append(value)
            population = validate_population(plan,context['terminal'],collected,progress,
                [p.name for p in cell_entries],[p.name for p in progress_entries])
            freeze(output/'ADMISSION.json',dict(owner=identity(process),run_admission=context['admission'],plan=context['plan_binding'],
                run_records=context['bindings'],progress=progress_bindings,population=population,code=code,qualification=qb,inventory=inventory))
            summaries = []
            def checkpoint(): guard(output,LOCAL,started,3600)
            for index,row in enumerate(plan['rows']):
                checkpoint(); payload = execution_payload(plan,index)
                checked = review_cell(cells/row['cell_id'],payload=payload,plan_sha256=fingerprint(plan),
                    coordinator=context['coordinator'],code=context['code'],executable=context['executable'],
                    coordinator_argv=context['coordinator_argv'],state=context['state'],checkpoint=checkpoint)
                require(checked['transport']['collected'] == collected[index], 'Cell changed after population census')
                target = output/'cells'/f'{index+1:04d}.json'; freeze(target,compact_cell(checked,row,payload)); summaries.append(bind(target))
            for b in code+context['bindings']+[context['plan_binding']]+collected+progress_bindings: verify(b)
            require(exact_process(context['coordinator']) is None,'Coordinator identity unexpectedly active')
            checkpoint()
            freeze(output/'REVIEW.json',dict(status='PASS_COMPLETE_V2_PANEL_EVIDENCE_COVERAGE_ONLY',utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'),population=population,cell_reviews=summaries,
                complete_planned_evidence_population_reviewed=True,native_payload_semantics_reviewed=False,
                accuracy_qualified=False,source_to_widget_latency_qualified=False,controlled_resources_qualified=False,
                continuity_included=False,stop_restart_qualified=False,N4_accepted=False,integrated_N4_cells=0))
            print('Complete planned V2 evidence population checked; semantic/timing/resource acceptance remains separate',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_V2_PANEL_REVIEW_PRESERVED',owner=identity(process),
                error_type=type(exc).__name__,error=str(exc)[:2000],integrated_N4_cells=0,N4_accepted=False))
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True); args = parser.parse_args(); run(args.run,args.output)
