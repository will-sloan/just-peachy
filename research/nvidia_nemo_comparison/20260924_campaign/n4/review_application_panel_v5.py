"""Review all stopped V4 panel cells. README_APPLICATION_FAMILY_V5.md."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
import time

from common import bind, fingerprint, freeze, load, verify
from metric_process import exact_process, identity, pin
from paced_child_admission import assert_plain_path
from paced_panel_plan_guarded_v2 import admit_plan, execution_payload
from paced_application_runner_v5 import RUN_SCHEMA, code_bindings as runner_code, qualified_interpreter
from review_application_cell_v5 import review_cell
from review_application_transport_v5 import record
from review_scoring_bank_v3 import guard, require, shared_allowance
from scoring_bank_v3 import writer_lock

HERE = Path(__file__).resolve().parent
LOCAL = Path('G:/Just_Peachy_N1/20260924_campaign/local')
QUALIFICATION = 'APPLICATION_FAMILY_CHECK_V5.json'


def code_bindings():
    from application_family_v5 import code_bindings as family_code
    return family_code()



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
        population_origin='Reconstructed qualified V4 plan; no available-evidence denominator substitution')


def stopped_run(folder):
    """Reconstruct the actual guarded plan, complete producer and run boundaries."""
    import application_family_v5 as family
    folder = assert_plain_path(folder, LOCAL/'n4')
    ab, a, rb, terminal = family.closed_execution(folder, 'run')
    code = runner_code(); executable = qualified_interpreter()
    require(a['schema'] == RUN_SCHEMA and a['status'] == 'ADMITTED_GUARDED_PACED_RUN_REQUIRES_PLAN_RECONSTRUCTION'
        and a['actual_application_started'] is False and terminal['owner'] == a['owner']
        and a['executable'] == executable, 'Guarded fixed runner admission differs')
    require(Path(a['output']).resolve() == folder and Path(a['state']).resolve() == LOCAL/'supervision', 'Foreign run output/state')
    plan_binding, plan = admit_plan(Path(a['plan']['path']))
    require(plan_binding == a['plan'] and terminal['required'] == plan['required'], 'Guarded run plan/census differs')
    argv = [executable['path'], '-B', str(HERE/'paced_application_runner_v5.py'), 'run', '--plan', plan_binding['path'], '--output', str(folder)]
    wb, worker = record(folder/'worker.json', folder)
    require(worker == dict(argv=argv, cwd=str(HERE)), 'Prepared fixed coordinator command differs')
    return dict(folder=folder, admission=ab, plan_binding=plan_binding, plan=plan, terminal=terminal,
        coordinator=a['owner'], code=code, executable=executable, coordinator_argv=argv,
        state=Path(a['state']), bindings=[ab, rb, a['execution_plan'], wb, *terminal['guard_checks']])


def compact_cell(checked, row, payload):
    require(checked['status'] == 'PASS_V5_APPLICATION_CELL_EVIDENCE_JOINS_ONLY'
        and checked['integrated_N4_cells'] == 0 and checked['N4_accepted'] is False, 'Joined cell reader did not pass')
    obs = checked['observations']; joins = checked['joins']
    delivery=checked['transport']['source_delivery_review']
    require(checked['transport']['cell_id']==row['cell_id']==payload['cell_id'] and row['job']==payload['job']
        and row['contract']==payload['contract'],'Compact panel row/input/transport differs')
    require(delivery['status']=='PASS_APPLICATION_DELIVERY_SOURCE_CLOCK_JOIN_ONLY'
        and delivery['source_samples']==joins['delivery_samples']==payload['job']['frames']
        and delivery['summary']['records']==joins['delivery_records']
        and delivery['source_origin_perf_counter']==joins['source_origin_monotonic_sec']==obs['phase_intervals']['source_origin_monotonic_sec']
        and delivery['deadline_or_continuity_accepted'] is False and joins['delivery_deadlines_accepted'] is False
        and checked['transport']['source_delivery_deadlines_accepted'] is False,'Delivery census/origin or acceptance scope differs')
    return dict(status='PASS_V5_CELL_EVIDENCE_COVERAGE_ONLY',cell_id=row['cell_id'],composition=row['composition'],
        kind=row['kind'],repeat=row['repeat'],tap=row['job']['tap'],job_id=row['job']['job_id'],
        planned_row_sha256=fingerprint(row),input_sha256=fingerprint(payload),full_reader_result_sha256=fingerprint(checked),
        collected=checked['transport']['collected'],evidence=joins['evidence'],
        native_events=joins['native_events'],consumed_events=joins['consumed_events'],
        coalesced_obsolete_ui_partials=joins['coalesced_obsolete_ui_partials'],
        phase_intervals=obs['phase_intervals'],final_span_census=obs['final_span_census'],
        source_delivery=dict(envelope=checked['transport']['source_delivery_envelope_binding'],
            source_samples=delivery['source_samples'],source_origin_monotonic_sec=delivery['source_origin_perf_counter'],
            last_append_monotonic_sec=joins['last_delivery_append_monotonic_sec'],summary=delivery['summary'],
            scheduling_or_append_cost_subtracted=False,deadline_or_continuity_accepted=False),
        native_payload_semantics_reviewed=False,accuracy_qualified=False,source_to_widget_latency_qualified=False,
        controlled_resources_qualified=False,deployment_tier='UNKNOWN',integrated_N4_cells=0,N4_accepted=False)


def run(run_root, output):
    import application_family_v5 as family
    import guarded_execution_v1 as resource
    pin(); sys.path.insert(0, str(HERE.parents[3]))
    run_root = assert_plain_path(run_root, LOCAL/'n4')
    require(not output.resolve().is_relative_to(run_root) and not run_root.is_relative_to(output.resolve()), 'Separate immutable run and review required')
    code = code_bindings(); plan_binding = load(run_root/'ADMISSION.json')['plan']
    g = family.start_output(output, plan_binding, 'review', code, 16*1024**2, 7200, dict(reviewed_run=str(run_root)))
    checks = []
    try:
        with g:
            checks.append(resource.save_check(g, 'GUARD_INITIAL.json'))
            context = stopped_run(run_root); folder = context['folder']; plan = context['plan']
            cells = assert_plain_path(folder/'cells', folder); progress_root = assert_plain_path(folder/'progress', folder)
            cell_entries = list(cells.iterdir()); progress_entries = list(progress_root.iterdir())
            require(len(cell_entries) <= 240 and len(progress_entries) <= 240, 'Panel directory census exceeds bound')
            for p in cell_entries: require(assert_plain_path(p, folder).is_dir(), 'Unexpected non-directory cell entry')
            for p in progress_entries: require(assert_plain_path(p, folder).is_file(), 'Unexpected non-file progress entry')
            collected = []; progress = []; progress_bindings = []
            for index, row in enumerate(plan['rows']):
                cb, _ = record(cells/row['cell_id']/'COLLECTED.json', folder); collected.append(cb)
                pb, value = record(progress_root/f'{index+1:04d}.json', folder); progress_bindings.append(pb); progress.append(value)
            population = validate_population(plan, context['terminal'], collected, progress,
                [p.name for p in cell_entries], [p.name for p in progress_entries])
            freeze(output/'RUN_BINDINGS.json', dict(run_admission=context['admission'], plan=context['plan_binding'],
                run_records=context['bindings'], progress=progress_bindings, population=population))
            summaries = []
            for index, row in enumerate(plan['rows']):
                g.fast_check(); payload = execution_payload(plan, index)
                checked = review_cell(cells/row['cell_id'], payload=payload, plan_sha256=fingerprint(plan),
                    coordinator=context['coordinator'], code=context['code'], executable=context['executable'],
                    coordinator_argv=context['coordinator_argv'], state=context['state'], checkpoint=g.fast_check)
                require(checked['transport']['collected'] == collected[index], 'Cell changed after population census')
                target = output/'cells'/f'{index+1:04d}.json'; freeze(target, compact_cell(checked, row, payload)); summaries.append(bind(target))
            for b in code+context['bindings']+[context['plan_binding']]+collected+progress_bindings: verify(b)
            require(exact_process(context['coordinator']) is None, 'Coordinator unexpectedly active')
            checks.append(resource.save_check(g, 'GUARD_FINAL.json')); g.fast_check()
            result = dict(status='PASS_COMPLETE_V5_PANEL_EVIDENCE_COVERAGE_ONLY', utc=datetime.now(timezone.utc).isoformat(),
                admission=g.admission, execution_plan=bind(output/'EXECUTION_PLAN.json'), guard_checks=checks,
                run_bindings=bind(output/'RUN_BINDINGS.json'), population=population, cell_reviews=summaries,
                complete_planned_evidence_population_reviewed=True, native_payload_semantics_reviewed=False,
                accuracy_qualified=False, source_to_widget_latency_qualified=False, controlled_resources_qualified=False,
                continuity_included=False, stop_restart_qualified=False, N4_accepted=False, integrated_N4_cells=0)
            freeze(output/'RESULT.json', result); freeze(output/'REVIEW.json', result)
    except BaseException as exc:
        freeze(output/'FAILED.json', dict(status='FAILED_V5_PANEL_REVIEW_PRESERVED', admission=g.admission,
            execution_plan=bind(output/'EXECUTION_PLAN.json'), error_type=type(exc).__name__, error=str(exc)[:2000],
            guard_checks=checks, integrated_N4_cells=0, N4_accepted=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True); args = parser.parse_args(); run(args.run, args.output)
