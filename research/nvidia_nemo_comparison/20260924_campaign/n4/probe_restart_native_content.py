"""Guarded released-native text/widget checks. README_RESTART_NATIVE_CONTENT.md."""
import argparse
from datetime import datetime, timezone
import io
from pathlib import Path
import sys
import time
import unittest

from common import bind, freeze, load, verify
from metric_process import identity, pin
from probe_application_transport_review import active_d1
from review_scoring_bank import guard, require, shared_allowance
from scoring_bank import writer_lock
import review_restart_native_content as subject
import test_restart_native_content as tests
import test_native_caption_review as original

LOCAL = Path('G:/Just_Peachy_N1/20260924_campaign/local')
MODULES = ('research_s6d', 'research_s7_presentation', 'research_n1_spans')


def run(output):
    process = pin(); started = time.monotonic()
    require(not output.exists() and output.resolve().is_relative_to(LOCAL/'n4'), 'Fresh private native-content probe required')
    with writer_lock(LOCAL/'n4/metric-scoring.owner.lock'):
        check = lambda: guard(output, LOCAL, started, 720)
        check(); inventory = shared_allowance(LOCAL); active = active_d1()
        freeze(output/'PROBE_OWNER.json', dict(owner=identity(process), utc=datetime.now(timezone.utc).isoformat()))
        (output/'source').mkdir(); snapshots = []
        for name in subject.OWN:
            target = output/'source'/name; target.write_bytes((subject.HERE/name).read_bytes())
            require(bind(target)['sha256'] == bind(subject.HERE/name)['sha256'], 'Snapshot differs'); snapshots.append(bind(target))
        try:
            code = subject.code_bindings(); q = load(subject.HERE/'NATIVE_CAPTION_REVIEW_CHECK_V1.json')
            verify(q['application_source']); source = load(q['application_source']['path']); root = Path(source['prototype'])
            native = [dict(path=str(root/('vendor/edge_speech_pipeline/'+name+'.py')),
                           **source['files']['vendor/edge_speech_pipeline/'+name+'.py']) for name in MODULES]
            for b in native: verify(b)
            freeze(output/'ADMISSION.json', dict(owner=identity(process), code=code, source_snapshots=snapshots,
                application_source=q['application_source'], native_pure_modules=native, inventory=inventory,
                D1_snapshot=active, fixture_clock='SYNTHETIC_NOT_MEASURED_LATENCY', actual_application_or_model_started=False))
            tests.OUTPUT = output/'tests'; (tests.OUTPUT/'native').mkdir(parents=True); (tests.OUTPUT/'widget').mkdir()
            tests.SOURCE_RECEIPT = q['application_source']; original.SOURCE = root
            suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(tests.ReleasedNativeContentTests),
                unittest.defaultTestLoader.loadTestsFromTestCase(tests.RestartNativeWidgetTests)])
            stream = io.StringIO(); result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
            (output/'tests.txt').write_text(stream.getvalue(), encoding='utf-8')
            require(result.wasSuccessful() and result.testsRun == 23 and not result.skipped, 'Released native-content checks failed')
            for name, b in zip(MODULES, native):
                require(Path(sys.modules['jp_n4_caption_fixture.'+name].__file__).resolve() == Path(b['path']).resolve(),
                        'Fixture imported a foreign pure module')
            for b in code+native+snapshots+[q['application_source']]: verify(b)
            after = active_d1()
            require(after['run_id'] == active['run_id'] and after['result']['child'] == active['result']['child'], 'D1 owner changed')
            check()
            freeze(output/'RESULT.json', dict(status='PASS_RESTART_NATIVE_CONTENT_CHECKS_ONLY', utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'), tests=bind(output/'tests.txt'), tests_passed=result.testsRun,
                code_records=len(code), D1_after=after, actual_pure_span_and_casing_methods=True,
                synthetic_native_clocks_and_viewport_geometry=True, actual_native_readers_mocked=False,
                actual_production_pair_or_run_reviewed=False, actual_application_or_model_started=False,
                source_to_widget_latency_qualified=False, actual_restart_qualified=False, integrated_N4_cells=0, N4_accepted=False))
            print('PASS: 23 released native and retained-caption widget checks; synthetic clocks, no model/UI execution', flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json', dict(status='FAILED_RESTART_NATIVE_CONTENT_PROBE_PRESERVED', owner=identity(process),
                error_type=type(exc).__name__, source_snapshots=snapshots,
                admission=bind(output/'ADMISSION.json') if (output/'ADMISSION.json').exists() else None)); raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
