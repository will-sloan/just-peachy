"""Guarded caption-to-widget reader checks. See README_NATIVE_WIDGET_REVIEW.md."""
import argparse
from datetime import datetime, timezone
import io
from pathlib import Path
import sys
import time
import unittest

from common import bind, freeze, load, verify
from metric_process import exact_process, identity, pin
from probe_application_transport_review import active_d1
from review_scoring_bank import guard, require, shared_allowance
from scoring_bank import writer_lock
import test_native_widget_review as regression

HERE = Path(__file__).resolve().parent
LOCAL = Path('G:/Just_Peachy_N1/20260924_campaign/local')
OWN = ('review_native_widget.py', 'test_native_widget_review.py', 'probe_native_widget_review.py',
       'README_NATIVE_WIDGET_REVIEW.md')
MODULES = ('research_s6d', 'research_s7_presentation', 'research_n1_spans')


def code_bindings():
    entries = [bind(HERE/name) for name in OWN]
    for name, status in (
        ('NATIVE_CAPTION_REVIEW_CHECK_V1.json', 'PASS_NATIVE_CAPTION_REVIEW_DEVELOPMENT_ONLY'),
        ('VIEWPORT_REVIEW_CHECK_V1.json', 'PASS_VIEWPORT_REVIEW_DEVELOPMENT_ONLY')):
        path = HERE/name; q = load(path)
        require(q['status'] == status, 'Prerequisite qualification differs: '+name)
        entries.extend([bind(path), *q['code']])
    result = {}
    for b in entries:
        require(b['path'] not in result or result[b['path']] == b, 'Conflicting code bindings')
        result[b['path']] = b
    return list(result.values())


def run(output):
    process = pin(); started = time.monotonic()
    require(not output.exists() and output.resolve().is_relative_to(LOCAL/'n4'), 'Fresh private N4 output required')
    with writer_lock(LOCAL/'n4/metric-scoring.owner.lock'):
        guard(output, LOCAL, started, 720); inventory = shared_allowance(LOCAL); active = active_d1()
        freeze(output/'PROBE_OWNER.json', dict(owner=identity(process), utc=datetime.now(timezone.utc).isoformat()))
        (output/'source').mkdir(); snapshots = []
        for name in OWN:
            path = output/'source'/name; path.write_bytes((HERE/name).read_bytes())
            require(bind(path)['sha256'] == bind(HERE/name)['sha256'], 'Attempt snapshot differs'); snapshots.append(bind(path))
        try:
            code = code_bindings()
            for b in code: verify(b)
            q = load(HERE/'NATIVE_CAPTION_REVIEW_CHECK_V1.json')
            for b in (q['private_receipt'], q['admission'], q['application_source']): verify(b)
            require(exact_process(load(q['admission']['path'])['owner']) is None, 'Native caption probe remains active')
            source = load(q['application_source']['path']); root = Path(source['prototype'])
            native = [dict(path=str(root/rel), **source['files'][rel]) for rel in
                      ['vendor/edge_speech_pipeline/'+name+'.py' for name in MODULES]+['app/casing.py']]
            for b in native: verify(b)
            freeze(output/'ADMISSION.json', dict(owner=identity(process), code=code, source_snapshots=snapshots,
                inventory=inventory, D1_snapshot=active, application_source=q['application_source'], native_pure_modules=native,
                fixture_clock='SYNTHETIC_PROTOCOL_VALUES_NOT_MEASURED_LATENCY', new_application_or_model_started=False))
            regression.CONTEXT.update(output=output/'tests', source=root, source_receipt=q['application_source'])
            regression.CONTEXT['output'].mkdir()
            stream = io.StringIO(); tests = unittest.TextTestRunner(stream=stream, verbosity=2).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(regression.NativeWidgetTests))
            (output/'tests.txt').write_text(stream.getvalue(), encoding='utf-8')
            require(tests.wasSuccessful() and tests.testsRun == 12 and not tests.skipped, 'Native widget reader tests failed')
            for name, b in zip(MODULES, native):
                require(Path(sys.modules['jp_n4_caption_fixture.'+name].__file__).resolve() == Path(b['path']).resolve(),
                    'Fixture imported a foreign application module')
            for b in code+native+[q['application_source']]: verify(b)
            after = active_d1(); require(after['result']['child'] == active['result']['child'] and after['run_id'] == active['run_id'],
                'Numerical owner changed during helper checks')
            guard(output, LOCAL, started, 720)
            freeze(output/'RESULT.json', dict(status='PASS_NATIVE_WIDGET_REVIEW_CHECKS_ONLY', utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'), tests=bind(output/'tests.txt'), tests_passed=tests.testsRun,
                synthetic_join=bind(output/'tests/test_complete_primary_text_and_first_final_latest_states/SYNTHETIC_WIDGET_JOIN.json'),
                D1_after=after, native_pure_span_and_casing_methods_actually_called=True, clocks_and_widget_geometry_are_synthetic=True,
                actual_complete_application_widget_history_joined=False, exact_consumed_event_attribution=False,
                source_to_widget_latency_qualified=False, naming_accuracy_qualified=False,
                new_application_or_model_started=False, integrated_N4_cells=0, N4_accepted=False))
            print('PASS: 12 native/widget join checks; synthetic geometry, no audio/model/UI launch', flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json', dict(status='FAILED_NATIVE_WIDGET_PROBE_PRESERVED', error_type=type(exc).__name__,
                owner=identity(process), source_snapshots=snapshots,
                admission=bind(output/'ADMISSION.json') if (output/'ADMISSION.json').exists() else None))
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
