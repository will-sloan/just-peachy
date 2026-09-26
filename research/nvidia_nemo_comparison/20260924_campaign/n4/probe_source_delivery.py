"""Guarded source-delivery observer checks; README_SOURCE_DELIVERY.md."""
import argparse
from datetime import datetime, timezone
import io
from pathlib import Path
import time
import unittest

from common import bind, freeze, load, verify
from metric_process import identity, pin
from probe_application_transport_review import active_d1
from review_scoring_bank import guard, require, shared_allowance
from scoring_bank import writer_lock
import test_source_delivery as regression

HERE = Path(__file__).resolve().parent
LOCAL = Path('G:/Just_Peachy_N1/20260924_campaign/local')
OWN = ('source_delivery.py', 'test_source_delivery.py', 'probe_source_delivery.py', 'README_SOURCE_DELIVERY.md')


def inputs():
    qpath = HERE/'JOURNAL_APPLICATION_PRESTART_CHECK_V1.json'; q = load(qpath)
    code = [bind(HERE/name) for name in OWN + ('common.py', 'metric_process.py',
        'probe_application_transport_review.py', 'review_scoring_bank.py', 'scoring_bank.py', 'paced_slot.py')]
    code += [bind(qpath), *q['code']]
    code = list({b['path']: b for b in code}.values())
    for b in code + [q['private_receipt'], q['source_receipt']]: verify(b)
    source = load(q['source_receipt']['path']); root = Path(source['prototype'])
    paths = ('app/pipeline.py', 'app/buffers.py', 'vendor/edge_speech_pipeline/research_s7.py')
    actual = [dict(path=str((root/name).resolve()), **source['files'][name]) for name in paths]
    for b in actual: verify(b)
    return dict(code=code, qualification=bind(qpath), qualified_prestart=q['private_receipt'],
                source_receipt=q['source_receipt'], class_source_files=actual, prototype=root)


def run(output):
    process = pin(); started = time.monotonic()
    require(not output.exists() and output.resolve().is_relative_to(LOCAL/'n4'), 'Fresh private source-delivery probe required')
    with writer_lock(LOCAL/'n4/metric-scoring.owner.lock'):
        guard(output, LOCAL, started, 720); inventory = shared_allowance(LOCAL); active = active_d1()
        freeze(output/'PROBE_OWNER.json', dict(owner=identity(process), utc=datetime.now(timezone.utc).isoformat()))
        (output/'source').mkdir(); snapshots = []
        for name in OWN:
            path = output/'source'/name; path.write_bytes((HERE/name).read_bytes())
            require(bind(path)['sha256'] == bind(HERE/name)['sha256'], 'Source snapshot differs'); snapshots.append(bind(path))
        try:
            admitted = inputs()
            freeze(output/'ADMISSION.json', dict(owner=identity(process), source_snapshots=snapshots, inventory=inventory,
                D1_snapshot=active, **{k: v for k, v in admitted.items() if k != 'prototype'},
                actual_application_or_audio_file_started=False, original_source_bodies_extracted_without_imports=True))
            checkpoint = lambda: guard(output, LOCAL, started, 720)
            regression.CONTEXT.update(output=output, prototype=admitted['prototype'], checkpoint=checkpoint)
            stream = io.StringIO(); tests = unittest.TextTestRunner(stream=stream, verbosity=2).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(regression.DeliveryTests))
            (output/'tests.txt').write_text(stream.getvalue(), encoding='utf-8')
            require(tests.wasSuccessful() and tests.testsRun == 18 and not tests.skipped, 'Source-delivery development checks failed')
            for b in admitted['code'] + admitted['class_source_files'] + [admitted['source_receipt']]: verify(b)
            after = active_d1()
            require(after['result']['child'] == active['result']['child'] and after['run_id'] == active['run_id'], 'D1 owner changed')
            checkpoint()
            freeze(output/'RESULT.json', dict(status='PASS_SOURCE_DELIVERY_DEVELOPMENT_CHECKS_ONLY',
                utc=datetime.now(timezone.utc).isoformat(), admission=bind(output/'ADMISSION.json'), tests=bind(output/'tests.txt'),
                tests_passed=tests.testsRun, synthetic_observation=bind(output/'SYNTHETIC_DELIVERY.json'),
                synthetic_trace=bind(output/'SYNTHETIC_DELIVERY.bin'), trace_budget=bind(output/'TRACE_BUDGET.json'), D1_after=after,
                exact_source_classes_with_RAM_only_fixture=True, actual_application_or_audio_file_started=False,
                application_runner_rebound=False, actual_deadline_or_continuity_qualified=False, integrated_N4_cells=0, N4_accepted=False))
            print('PASS: 18 source-delivery development checks; no application, model or audio file started', flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json', dict(status='FAILED_SOURCE_DELIVERY_PROBE_PRESERVED', error_type=type(exc).__name__,
                owner=identity(process), source_snapshots=snapshots,
                admission=bind(output/'ADMISSION.json') if (output/'ADMISSION.json').exists() else None))
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
