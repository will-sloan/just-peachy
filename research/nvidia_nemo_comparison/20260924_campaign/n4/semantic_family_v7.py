"""Guarded semantic review of the actual V7 application family. See README_SEMANTIC_FAMILY_V7.md."""
from pathlib import Path
import json
import os
import sys

from common import bind, load, verify, freeze
from metric_process import exact_process, identity, pin
from reservation_budget_v1 import require
import semantic_family_v4 as previous
import application_family_v7 as application
import guarded_execution_v1 as resource
import guarded_metadata_probe_v1 as metadata

HERE = Path(__file__).resolve().parent
LOCAL = application.LOCAL
QUALIFICATION = 'SEMANTIC_FAMILY_CHECK_V7.json'
STATUS = 'PASS_V7_SEMANTIC_FAMILY_DEVELOPMENT_ONLY'
MAX_CODE_RECORDS = 512
OUTPUT_LIMIT = 16*1024**2
OWN = ('semantic_family_v7.py', 'review_application_semantics_v7.py', 'review_semantic_panel_v7.py',
    'review_application_content_panel_v7.py', 'test_application_semantics_v7.py', 'test_semantic_panel_v7.py',
    'test_application_content_panel_v7.py', 'test_semantic_family_v7.py', 'probe_semantic_family_v7.py',
    'README_SEMANTIC_FAMILY_V7.md', 'application_import_path_v1.py', 'README_APPLICATION_IMPORT_PATH_V1.md')
PARENTS = {previous.QUALIFICATION: previous.STATUS, application.QUALIFICATION: application.STATUS}
ENTRIES = dict(probe='probe_semantic_family_v7.py', names='review_semantic_panel_v7.py',
               content='review_application_content_panel_v7.py')


def code_bindings():
    values = [bind(HERE/name) for name in OWN]
    for module in (previous, application):
        qb = bind(HERE/module.QUALIFICATION); q = load(qb['path']); code = module.code_bindings()
        require(q['status'] == module.STATUS and q['code'] == code and q['N4_accepted'] is False,
                'Changed semantic family parent')
        verify(q['private_receipt']); r = load(q['private_receipt']['path']); verify(r['admission'])
        a = load(r['admission']['path'])
        require(a['code'] == code and exact_process(a['owner']) is None, 'Parent is not closed')
        values += [qb, *code]
    unique = {}
    for b in values:
        require(b['path'] not in unique or unique[b['path']] == b, 'Conflicting semantic dependency')
        unique[b['path']] = b
    require(0 < len(unique) <= MAX_CODE_RECORDS, 'Complete semantic source manifest exceeds cap')
    result = [b for _, b in sorted(unique.items())]
    for b in result: verify(b)
    return result


def freeze_bounded(path, value, output):
    require(Path(path).resolve().is_relative_to(Path(output).resolve()), 'Output escaped review directory')
    used = sum(p.stat().st_size for p in output.rglob('*') if p.is_file()) if output.exists() else 0
    size = len(os.linesep.encode())
    for chunk in json.JSONEncoder(indent=2, ensure_ascii=False, allow_nan=False).iterencode(value):
        size += len(chunk.replace('\n', os.linesep).encode('utf-8'))
        require(used+size+65536 <= OUTPUT_LIMIT, 'Next complete review receipt exceeds output bound')
    freeze(path, value)


def qualification(code=None):
    code = code_bindings() if code is None else code
    qb = bind(HERE/QUALIFICATION); q = load(qb['path']); verify(q['private_receipt']); verify(q['private_admission'])
    r = load(q['private_receipt']['path']); a = load(q['private_admission']['path'])
    require(q['status'] == STATUS and q['code'] == a['code'] == code
        and r['status'] == 'PASS_V7_SEMANTIC_FAMILY_CHECKS_ONLY' and r['admission'] == q['private_admission']
        and r['tests_passed'] == 66 and r['positive_production_plan_gate_executed'] is True
        and r['isolated_import_path_repair_verified'] is True
        and exact_process(a['owner']) is None and q['N4_accepted'] is False,
        'Closed matching semantic family qualification required')
    return qb, q


def start_output(output, plan_binding, role, code, extra):
    process = pin(); entry = bind(HERE/ENTRIES[role])
    require(Path(sys.argv[0]).resolve() == Path(entry['path']), 'Wrong semantic producer entrypoint')
    metadata.validate_manifest(code, resource.code_bindings(), entry)
    qb = None if role == 'probe' else qualification(code)[0]
    output = Path(output).resolve()
    require(not output.exists() and output.is_relative_to(LOCAL/'n4') and output != LOCAL/'n4', 'Fresh private semantic output required')
    for b in code+[plan_binding]: verify(b)
    seconds = 2400 if role == 'probe' else 7200
    freeze(output/'EXECUTION_PLAN.json', dict(schema='n4-guarded-semantic-execution-v1', role=role,
        plan=plan_binding, code=code, entry_script=entry, resource_qualification=resource.qualification(),
        family_qualification=qb, allocation_bytes=OUTPUT_LIMIT, maximum_seconds=seconds,
        application_permission_from_envelope=False))
    a = dict(owner=identity(process), code=code, plan=plan_binding, execution_plan=bind(output/'EXECUTION_PLAN.json'),
        qualification=qb, allocation_bytes=OUTPUT_LIMIT, maximum_seconds=seconds, cpu_affinity=process.cpu_affinity())
    require(not set(extra).intersection(a), 'Extra field replaces semantic provenance')
    a.update(extra); freeze(output/'ADMISSION.json', a)
    return resource.Guard(LOCAL, output, code, load(LOCAL/'n4/integrated-main-v3/RESULT.json')['plan'], seconds, production=True)


def run_panel(run_root, output, role):
    """Keep evidence interpretation unchanged within an explicit guarded allocation."""
    from datetime import datetime, timezone
    import time
    from common import fingerprint
    import review_semantic_panel_v7 as names
    import review_application_content_panel_v7 as content
    module = names if role == 'names' else content
    require(role in ('names', 'content'), 'Unknown semantic review role')
    run_root = Path(run_root).resolve(strict=True); output = Path(output).resolve()
    require(not output.is_relative_to(run_root) and not run_root.is_relative_to(output), 'Run and review must be separate')
    ab = bind(run_root/'ADMISSION.json'); a = load(ab['path']); verify(a['plan'])
    require(exact_process(a['owner']) is None, 'Application run still active')
    code = code_bindings(); sys.path.insert(0, str(HERE.parents[3]))
    g = start_output(output, a['plan'], role, code, dict(run_admission=ab, evaluator_only=True))
    guards = []; last = [0.]
    def checkpoint():
        if time.monotonic()-last[0] >= 1:
            g.fast_check(); last[0] = time.monotonic()
    def save(path, value): freeze_bounded(path, value, output)
    try:
        with g:
            guards.append(resource.save_check(g, 'GUARD_INITIAL.json'))
            context = module.stopped_run(run_root); plan = context['plan']
            require(context['admission'] == ab and context['plan_binding'] == a['plan'], 'Producer changed after review admission')
            cells, collected, progress, census = module.population(context)
            references = module.load_reference_context(checkpoint=checkpoint) if role == 'names' else None
            save(output/'RUN_BINDINGS.json', dict(run_admission=ab, run_records=context['bindings'],
                plan=context['plan_binding'], progress=progress, population=census,
                reference_inputs=references['inputs'] if references else None,
                reference_context_sha256=fingerprint(references) if references else None))
            summaries = []; outputs = []; registry = {}
            for i, row in enumerate(plan['rows']):
                checkpoint(); payload = module.execution_payload(plan, i)
                checked = module.review_cell(cells/row['cell_id'], payload=payload, plan_sha256=fingerprint(plan),
                    coordinator=context['coordinator'], code=context['code'], executable=context['executable'],
                    coordinator_argv=context['coordinator_argv'], state=context['state'], checkpoint=checkpoint)
                body = checked['observed']['content'] if role == 'names' else checked
                require(body['cell']['transport']['collected'] == collected[i], 'Cell changed after population census')
                if role == 'names':
                    score = module.score_cell(references, checked, payload, checkpoint=checkpoint)
                    summary = module.compact(checked, score, references, row, payload, registry)
                else: summary = module.compact_content(checked, row, payload, registry)
                summaries.append(summary); path = output/'cells'/f'{i+1:04d}.json'
                save(path, summary); outputs.append(bind(path))
            report = module.aggregate(summaries)
            require(report['cells'] == census['planned_cells'], 'Incomplete review population')
            for b in code+context['bindings']+[context['plan_binding']]+collected+progress+list(registry.values()): verify(b)
            require(exact_process(context['coordinator']) is None, 'Producer unexpectedly active')
            save(output/'INPUT_BINDINGS.json', dict(bindings=sorted(registry.values(), key=lambda b:b['path'])))
            guards.append(resource.save_check(g, 'GUARD_FINAL.json')); g.fast_check()
            result = dict(status=('PASS_COMPLETE_V7_PANEL_NAME_DIAGNOSTICS_ONLY' if role == 'names'
                                 else 'PASS_COMPLETE_V7_PANEL_CONTENT_COVERAGE_ONLY'),
                utc=datetime.now(timezone.utc).isoformat(), admission=g.admission,
                execution_plan=bind(output/'EXECUTION_PLAN.json'), guard_checks=guards,
                run_bindings=bind(output/'RUN_BINDINGS.json'), population=census, cell_reviews=outputs,
                input_bindings=bind(output/'INPUT_BINDINGS.json'), report=report,
                complete_planned_content_population_reviewed=True,
                complete_planned_name_diagnostic_population_reviewed=role == 'names',
                primary_caption_text_consistency_reviewed=True, conditional_name_diagnostics_scored=role == 'names',
                exact_consumed_event_attribution=False, exact_word_identity_established=False,
                names_independently_scored=role == 'names', accuracy_qualified=False, naming_accuracy_qualified=False,
                source_to_widget_latency_qualified=False, controlled_resources_qualified=False,
                continuity_included=False, stop_restart_qualified=False, integrated_N4_cells=0,
                N4_accepted=False, N5_complete=False)
            save(output/'RESULT.json', result); save(output/'REVIEW.json', result)
    except BaseException as exc:
        freeze(output/'FAILED.json', dict(status='FAILED_V7_SEMANTIC_REVIEW_PRESERVED', admission=g.admission,
            execution_plan=bind(output/'EXECUTION_PLAN.json'), guard_checks=guards,
            error_type=type(exc).__name__, reason=str(exc)[:2000], integrated_N4_cells=0,
            N4_accepted=False, N5_complete=False))
        raise
