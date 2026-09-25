"""Review 51 existing saved scores, without rescoring. README_SCORING_REVIEW.md."""
import argparse
from datetime import datetime, timezone
import io
from pathlib import Path
import time
import unittest

from common import bind, fingerprint, freeze, load, verify
from integrated_scoring_adapter import convert, read_artifact, read_component_events
from metric_process import exact_process, identity, pin
from probe_integrated_scoring import verify_environment
from review_scoring_bank import code_bindings, guard, owners_closed, require, shared_allowance, validate_score
from scoring_bank import writer_lock
from test_scoring_review import ScoringReviewTests


def run(output):
    process = pin(); started = time.monotonic(); here = Path(__file__).resolve().parent
    public = load(here/'SCORING_BANK_IMPLEMENTATION_V1.json'); parent_binding = public['private_metric_probe']
    verify(parent_binding); parent = load(parent_binding['path']); verify(parent['admission']); admission = load(parent['admission']['path'])
    require(parent['status'] == 'PASS_51_OWNED_PROCESS_SCORING_CHECKS' and len(parent['checks']) == 51, 'Original saved scoring population differs')
    require(exact_process(admission['owner']) is None, 'Saved scoring probe still active')
    owners_closed([parent['closure']], 51)
    local = Path(parent_binding['path']).parents[2]
    require(not output.exists() and output.resolve().is_relative_to((local/'n4').resolve()), 'Fresh private output required')
    with writer_lock(local/'n4/metric-scoring.owner.lock'):
        guard(output, local, started, 720); inventory = shared_allowance(local)
        files = verify_environment(admission['environment']); verify(admission['truth'])
        for binding in admission['code']: verify(binding)
        code = code_bindings(); truths = {r['job_id']: r for r in load(admission['truth']['path'])['cells']}
        require(len(truths) == 480, 'Truth population differs')
        freeze(output/'ADMISSION.json', dict(owner=identity(process), parent=parent_binding, code=code,
            environment=admission['environment'], environment_files_verified=files, truth=admission['truth'],
            inventory=inventory, cases=51, models_loaded=0, integrated_N4_cells=0))
        checked = []; tests = None
        try:
            stream = io.StringIO(); tests = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ScoringReviewTests))
            (output/'tests.txt').write_text(stream.getvalue(), encoding='utf-8')
            require(tests.wasSuccessful(), 'Scoring review regression tests failed')
            for check in parent['checks']:
                guard(output, local, started, 720); verify(check['expected']); saved = load(check['expected']['path'])
                for binding in [*saved['inputs'], saved['consumer_closure']]: verify(binding)
                asr, speaker = [load(b['path']) for b in saved['inputs']]; job = asr['job']; truth = truths[job['job_id']]
                require(speaker['job'] == job and truth['frames'] == job['frames'] and truth['tap'] == job['tap']
                        and load(saved['consumer_closure']['path'])['full_event_consumer_drained'], 'Saved prediction join/closure differs')
                pub = read_artifact(saved['publication']); proj = read_artifact(saved['projection'])
                pred = convert(pub, proj, read_component_events(speaker), job, pub['contract']['diarization'])
                require(check['input_sha256'] == fingerprint(dict(truth=truth, prediction=pred))
                        and check['score_sha256'] == fingerprint(saved['score']) and check['exact_score_equal'] is True, 'Saved metric/input binding differs')
                validate_score(saved['score'], truth, pred)
                checked.append(dict(expected=check['expected'], metric_input_sha256=check['input_sha256'], score_sha256=check['score_sha256']))
            for binding in code+[parent_binding, admission['truth']]: verify(binding)
            freeze(output/'RESULT.json', dict(status='PASS_51_SAVED_SCORE_REVIEWS_AND_REJECTION_TESTS', utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'), checks=checked, tests=bind(output/'tests.txt'), tests_passed=tests.testsRun,
                metric_alignment_recomputed=False, environment_files_verified=files, models_loaded=0, integrated_N4_cells=0,
                scope='Dictionary rejection tests and 51 existing development scores; no production bank admitted or reviewed'))
            print('PASS: 51 saved reviews and '+str(tests.testsRun)+' rejection tests', flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json', dict(status='FAILED_REVIEW_PROBE_PRESERVED', error_type=type(exc).__name__,
                admission=bind(output/'ADMISSION.json'), checked=len(checked), tests_passed=tests.testsRun if tests and tests.wasSuccessful() else None,
                integrated_N4_cells=0))
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
