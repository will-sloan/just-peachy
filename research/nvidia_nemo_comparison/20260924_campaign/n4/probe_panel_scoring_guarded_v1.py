"""Supervised, bounded reader check. README_PANEL_SCORING_GUARDED_V1.md."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import unittest

from common import bind, freeze, load, verify
from guarded_execution_v1 import start_output, save_check
from metric_process import pin
from reservation_budget_v1 import require
import panel_scoring_admission_guarded_v1 as reader


def run(args):
    pin()
    require(bool(args.main_review) == bool(args.modes_review), 'Supply both real reviews or neither')
    code = reader.code_bindings(); pb = bind(args.plan)
    g = start_output(args.output, pb, 'probe', 8*1024**2, 1200,
        dict(reader_code=code, reader_probe_only=True), development=True)
    checks = []
    try:
        with g:
            checks.append(save_check(g, 'GUARD_INITIAL.json'))
            for name in reader.OWN:
                p = reader.HERE/name; target = g.output/'source'/name
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as stream: stream.write(p.read_bytes())
            import test_panel_scoring_admission_guarded_v1 as tests
            with (g.output/'tests.txt').open('x', encoding='utf-8') as stream:
                result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
                    unittest.defaultTestLoader.loadTestsFromModule(tests))
            require(result.wasSuccessful() and result.testsRun == 11, 'Reader regression tests failed or missing')
            g.fast_check()
            parent = bind(reader.HERE/'MAIN_MODELED_SCORING_ACCEPTANCE_V1.json')
            accepted = load(parent['path']); verify(accepted['review']); verify(accepted['scoring_result'])
            require(accepted['status'] == 'ACCEPTED_REVIEWED_MAIN_MODELED_SCORING_ONLY'
                and accepted['main_modeled_scoring_accepted'] is True, 'Main acceptance differs')
            mpb = load(accepted['review']['path'])['plan']; verify(mpb)
            main = load(mpb['path'])
            modes = load(pb['path']); reader.previous.validate_contexts(main, modes)
            real = None
            if args.main_review:
                reviews, main, modes = reader.read_pair(args.main_review, args.modes_review)
                require(load(reviews['modes-panel']['path'])['plan'] == pb,
                    'Real modes review targets a different original plan')
                real = dict(reviews=reviews, required_main=main['required'], required_modes=modes['required'])
            checks.append(save_check(g, 'GUARD_FINAL.json'))
            for b in code+[pb, mpb, parent]: verify(b)
            g.fast_check()
            freeze(g.output/'RESULT.json', dict(
                status='PASS_REAL_CLOSED_SCORE_PAIR_READER_ONLY' if real else 'PASS_READER_FIXTURES_ONLY',
                utc=datetime.now(timezone.utc).isoformat(), admission=g.admission,
                reader_code=code, original_modes_plan=pb, tests=bind(g.output/'tests.txt'),
                tests_passed=result.testsRun, real_review_pair=real, real_context_headers_match=True,
                main_acceptance=parent, original_main_plan=mpb, guard_checks=checks,
                source_snapshots=[bind(g.output/'source'/n) for n in reader.OWN],
                application_plan_prepared=False, GUI_family_qualified=False,
                integrated_N4_cells=0, N4_accepted=False, N5_complete=False))
    except BaseException as exc:
        freeze(g.output/'FAILED.json', dict(status='FAILED_READER_CHECK_PRESERVED',
            admission=g.admission, reason=str(exc), error_type=type(exc).__name__,
            guard_checks=checks, integrated_N4_cells=0, N4_accepted=False, N5_complete=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('plan', 'output'): parser.add_argument('--'+name, type=Path, required=True)
    for name in ('main-review', 'modes-review'): parser.add_argument('--'+name, type=Path)
    run(parser.parse_args())
