"""Guarded-score planner diagnostic only. README_PACED_PANEL_PLAN_GUARDED_V1.md."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

from common import bind, fingerprint, freeze, load, verify
from guarded_execution_v1 import start_output, save_check
from metric_process import pin
from reservation_budget_v1 import require
import paced_panel_plan as original
import paced_panel_plan_v4 as legacy
import paced_panel_plan_guarded_v1 as subject
import test_paced_panel_plan as fixtures


def run(args):
    pin(); code = subject.code_bindings(); pb = bind(args.plan)
    g = start_output(args.output, pb, 'probe', 8*1024**2, 1200,
        dict(planner_code=code, planner_probe_only=True), development=True)
    checks = []
    try:
        with g:
            checks.append(save_check(g, 'GUARD_INITIAL.json'))
            for name in subject.OWN:
                p = g.output/'source'/name; p.parent.mkdir(parents=True, exist_ok=True)
                with p.open('xb') as stream: stream.write((subject.HERE/name).read_bytes())
            import test_paced_panel_plan_guarded_v1 as tests
            with (g.output/'tests.txt').open('x', encoding='utf-8') as stream:
                result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
                    unittest.defaultTestLoader.loadTestsFromModule(tests))
            require(result.wasSuccessful() and result.testsRun == 10 and not result.skipped,
                    'Guarded planner fixture tests failed or missing')
            reviews, main, modes = subject.scores.read_pair(args.main_review, args.modes_review)
            require(load(reviews['modes-panel']['path'])['plan'] == pb, 'Modes plan differs')
            g.fast_check()
            ab, app, source = subject.previous.application_qualification()
            prep_binding = load(subject.HERE/'PREPARATION_V2_CHECK.json')['preparation']; verify(prep_binding)
            outputs = {Path(b['path']).name:b for b in load(prep_binding['path'])['outputs']}
            manifest, panel, anchors = [outputs[n] for n in ('AUDIO_ONLY_480.json', 'PACED_AUDIO_ONLY_24.json', 'REGRESSION_AUDIO_ONLY_8.json')]
            for b in (manifest, panel, anchors): verify(b)
            jobs, panel_jobs, anchor_jobs = [load(b['path'])['jobs'] for b in (manifest, panel, anchors)]
            for job in panel_jobs:
                g.fast_check(); require(bind(job['audio_path'])['sha256'] == job['audio_sha256'], 'Saved panel waveform differs')
            common = dict(manifest=manifest, panel=panel, regression=anchors, models_root='NO_MODEL_PAYLOAD', assets=[],
                planner_qualification={'development_fixture':'NOT_A_PRODUCTION_PLAN'}, code=code)
            context = subject.application_context(main['context'], source, app['application_context'], ab, common)
            old_context = deepcopy(context); old_context['scoring_review_policy'] = deepcopy(legacy.scores.POLICY)
            catalog = load(source['catalog']['path']); comparisons = []
            for candidate in sorted(original.COMPOSITIONS):
                g.fast_check()
                chosen = [original.BASELINE] if candidate == original.BASELINE else [original.BASELINE, candidate]
                selection = fixtures.selection(chosen, reviews)
                plan = subject.build_plan(selection, reviews, jobs, panel_jobs, anchor_jobs, catalog, context)
                old = legacy.build_plan(selection, reviews, jobs, panel_jobs, anchor_jobs, catalog, old_context)
                require(plan['required'] == old['required'], 'Population differs')
                for i, row in enumerate(plan['rows']):
                    payload = subject.execution_payload(plan, i)
                    require(payload == legacy.execution_payload(old, i) and payload['job'] == row['job']
                        and len(payload) == 13 and payload['source_execution_authorized'] is False
                        and row['cache_key'] != old['rows'][i]['cache_key'], 'Child parity or distinct cache policy failed')
                    require(not set(payload)&{'reviews','selection','scoring_review_policy','truth','reference'}, 'Evaluator data in child')
                comparisons.append(dict(candidate=candidate,fixture_cells=plan['required'],content_sha256=fingerprint(plan)))
            require(len(comparisons) == 16 and sum(v['fixture_cells'] for v in comparisons) == 1240,
                    'Complete baseline/candidate fixture coverage required')
            require('torch' not in sys.modules, 'Planner imported model runtime')
            checks.append(save_check(g, 'GUARD_FINAL.json'))
            for b in code+[pb, ab, prep_binding, *reviews.values()]: verify(b)
            g.fast_check()
            freeze(g.output/'RESULT.json',dict(status='PASS_GUARDED_PANEL_ADAPTER_DIAGNOSTIC_ONLY',
                utc=datetime.now(timezone.utc).isoformat(),admission=g.admission,planner_code=code,
                tests=bind(g.output/'tests.txt'),tests_passed=result.testsRun,real_reviews=reviews,
                required_main=main['required'],required_modes=modes['required'],original_modes_plan=pb,
                application_qualification=ab,application_context=app['application_context'],preparation=prep_binding,
                fixture_comparisons=comparisons,fixture_payloads=1240,child_payloads_equal_to_V4=True,
                source_snapshots=[bind(g.output/'source'/n) for n in subject.OWN],guard_checks=checks,
                actual_shortlist_selected=False,production_plan_created=False,production_reconstruction_implemented=False,
                downstream_runner_and_restart_rebound=False,actual_application_or_model_started=False,
                integrated_N4_cells=0,N4_accepted=False,N5_complete=False))
    except BaseException as exc:
        freeze(g.output/'FAILED.json',dict(status='FAILED_GUARDED_PANEL_ADAPTER_PRESERVED',admission=g.admission,
            reason=str(exc),error_type=type(exc).__name__,guard_checks=checks,integrated_N4_cells=0,
            N4_accepted=False,N5_complete=False))
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('plan','main-review','modes-review','output'): p.add_argument('--'+name,type=Path,required=True)
    run(p.parse_args())
