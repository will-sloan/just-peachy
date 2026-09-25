"""Model-free fixed-source planning rehearsal. README_PACED_PANEL_PLAN.md."""
import argparse
from datetime import datetime, timezone
import io
from pathlib import Path
import time
import unittest

from common import bind, fingerprint, freeze, load, verify
from metric_process import identity, pin
from paced_panel_plan import (BASELINE, COMPOSITIONS, build_plan, code_bindings, execution_payload)
from review_scoring_bank import guard, require, shared_allowance
from scoring_bank import writer_lock
from test_paced_panel_plan import PacedPanelPlanTests, selection


def run(output):
    process = pin(); started = time.monotonic(); here = Path(__file__).resolve().parent
    prep_binding = load(here/'PREPARATION_V2_CHECK.json')['preparation']; verify(prep_binding); prep = load(prep_binding['path'])
    local = Path(prep_binding['path']).parents[2]
    require(not output.exists() and output.resolve().is_relative_to((local/'n4').resolve()), 'Fresh private output required')
    with writer_lock(local/'n4/metric-scoring.owner.lock'):
        guard(output, local, started, 720); inventory = shared_allowance(local)
        app_binding = bind(here/'PACED_APPLICATION_CELL_CHECK_V1.json'); app = load(app_binding['path'])
        for b in app['code']+[app['private_receipt'], app['source_receipt'], app['gallery_preparation']]: verify(b)
        source = load(app['source_receipt']['path']); root = Path(source['prototype'])
        for rel, b in source['files'].items(): verify(dict(path=str((root/rel).resolve()), **b))
        app_result = load(app['private_receipt']['path']); verify(app_result['admission']); app_admission = load(app_result['admission']['path'])
        outputs = {Path(b['path']).name: b for b in prep['outputs']}
        manifest, panel, regression = [outputs[n] for n in ('AUDIO_ONLY_480.json', 'PACED_AUDIO_ONLY_24.json', 'REGRESSION_AUDIO_ONLY_8.json')]
        for b in (manifest, panel, regression): verify(b)
        jobs, panel_jobs, regression_jobs = [load(b['path'])['jobs'] for b in (manifest, panel, regression)]
        for j in panel_jobs: require(bind(j['audio_path'])['sha256'] == j['audio_sha256'], 'Saved panel waveform changed')
        catalog = bind(root/'config/backends.json'); require(catalog == app_admission['catalog'], 'Actual catalog differs')
        code = code_bindings()
        freeze(output/'ADMISSION.json', dict(owner=identity(process), code=code, preparation=prep_binding,
            application_qualification=app_binding, source=app['source_receipt'], panel=panel, regression=regression,
            inventory=inventory, inference_started=False, scoring_reviews_available=False))
        checked = []
        try:
            stream = io.StringIO(); tests = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PacedPanelPlanTests))
            (output/'tests.txt').write_text(stream.getvalue(), encoding='utf-8'); require(tests.wasSuccessful(), 'Panel plan regressions failed')
            # Deliberately not passed-review bindings. These exist only inside
            # the pure planner; production read_review/prepare is never bypassed.
            reviews = dict(main={'development_fixture': 'UNAVAILABLE'}, **{'modes-panel': {'development_fixture': 'UNAVAILABLE'}})
            context = dict(source_receipt=app['source_receipt'], catalog=catalog,
                           runtimes={Path(b['path']).name: b for b in app_admission['runtimes']},
                           gallery_preparation=app['gallery_preparation'], models_root='NO_MODEL_PAYLOAD', assets=[])
            for candidate in sorted(COMPOSITIONS):
                guard(output, local, started, 720)
                chosen = [BASELINE] if candidate == BASELINE else [BASELINE, candidate]
                plan = build_plan(selection(chosen, reviews), reviews, jobs, panel_jobs, regression_jobs, load(catalog['path']), context)
                for index, row in enumerate(plan['rows']):
                    payload = execution_payload(plan, index)
                    require(payload['job'] == row['job'] and payload['contract'] == row['contract']
                            and payload['source_execution_authorized'] is False, 'Input allowlist differs')
                checked.append(dict(candidate=candidate, fixture_cells=plan['required'], plan_content_sha256=fingerprint(plan),
                                    source_seconds_per_candidate=plan['source_seconds_per_candidate'], production_admission=False))
            for b in code+[prep_binding, app_binding, catalog]: verify(b)
            freeze(output/'RESULT.json', dict(status='PASS_FIXED_SOURCE_PLANNING_REHEARSALS_ONLY', utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'), tests=bind(output/'tests.txt'), tests_passed=tests.testsRun, checks=checked,
                model_inference_started=False, actual_GUI_started=False, production_full_review_gate_executed=False,
                actual_shortlist_selected=False, production_plan_created=False, integrated_N4_cells=0))
            print('PASS: '+str(tests.testsRun)+' tests and 16 frozen-catalog routing rehearsals', flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json', dict(status='FAILED_PANEL_PLAN_PROBE_PRESERVED', error_type=type(exc).__name__,
                admission=bind(output/'ADMISSION.json'), checks=checked, integrated_N4_cells=0))
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
