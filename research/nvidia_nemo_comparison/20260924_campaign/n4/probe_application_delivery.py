"""Guarded application delivery integration checks; README_APPLICATION_DELIVERY.md."""
import argparse
from datetime import datetime, timezone
import io
from pathlib import Path
import time
import unittest

from common import bind, freeze, load, verify
from metric_process import identity, pin
from probe_application_transport_review import active_d1
from probe_source_delivery import inputs as source_inputs
from review_scoring_bank import guard, require, shared_allowance
from scoring_bank import writer_lock
import test_application_delivery as regression

HERE = Path(__file__).resolve().parent
LOCAL = Path('G:/Just_Peachy_N1/20260924_campaign/local')
OWN = ('application_delivery.py','paced_application_cell_v2.py','test_application_delivery.py',
       'probe_application_delivery.py','README_APPLICATION_DELIVERY.md')


def inputs():
    source = source_inputs(); entries = [bind(HERE/name) for name in OWN]
    for name in ('SOURCE_DELIVERY_CHECK_V1.json','APPLICATION_CLOSURE_CHECK_V2.json'):
        q = load(HERE/name); verify(q['private_receipt']); entries += [bind(HERE/name),*q['code']]
    entries += source['code']; registry = {}
    for b in entries:
        require(b['path'] not in registry or registry[b['path']] == b, 'Conflicting source qualification')
        verify(b); registry[b['path']] = b
    source['code'] = list(registry.values())
    return source


def run(output):
    process = pin(); started = time.monotonic()
    require(not output.exists() and output.resolve().is_relative_to(LOCAL/'n4'), 'Fresh private delivery-integration probe required')
    with writer_lock(LOCAL/'n4/metric-scoring.owner.lock'):
        guard(output,LOCAL,started,720); inventory=shared_allowance(LOCAL); active=active_d1()
        freeze(output/'PROBE_OWNER.json',dict(owner=identity(process),utc=datetime.now(timezone.utc).isoformat()))
        (output/'source').mkdir(); snapshots=[]
        for name in OWN:
            path=output/'source'/name; path.write_bytes((HERE/name).read_bytes())
            require(bind(path)['sha256']==bind(HERE/name)['sha256'],'Source snapshot differs'); snapshots.append(bind(path))
        try:
            admitted=inputs()
            freeze(output/'ADMISSION.json',dict(owner=identity(process),source_snapshots=snapshots,inventory=inventory,
                D1_snapshot=active,**{k:v for k,v in admitted.items() if k!='prototype'},
                actual_application_or_audio_file_started=False,actual_private_GUI_prestart_run=False,
                pure_join_fixture_flags_normalized_only_in_copies=True))
            checkpoint=lambda:guard(output,LOCAL,started,720)
            regression.CONTEXT.update(output=output,prototype=admitted['prototype'],checkpoint=checkpoint)
            regression.source_tests.CONTEXT.update(output=output,prototype=admitted['prototype'],checkpoint=checkpoint)
            stream=io.StringIO(); tests=unittest.TextTestRunner(stream=stream,verbosity=2).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(regression.ApplicationDeliveryTests))
            (output/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
            require(tests.wasSuccessful() and tests.testsRun==16 and not tests.skipped,'Application delivery development checks failed')
            for b in admitted['code']+admitted['class_source_files']+[admitted['source_receipt']]:verify(b)
            after=active_d1(); require(after['result']['child']==active['result']['child'] and after['run_id']==active['run_id'],'D1 owner changed')
            checkpoint()
            freeze(output/'RESULT.json',dict(status='PASS_APPLICATION_DELIVERY_INTEGRATION_DEVELOPMENT_CHECKS_ONLY',
                utc=datetime.now(timezone.utc).isoformat(),admission=bind(output/'ADMISSION.json'),tests=bind(output/'tests.txt'),
                tests_passed=tests.testsRun,synthetic_join=bind(output/'SYNTHETIC_JOIN.json'),
                synthetic_file_join=bind(output/'SYNTHETIC_FILE_JOIN.json'),
                synthetic_cell_wiring=bind(output/'SYNTHETIC_CELL_WIRING.json'),D1_after=after,
                exact_source_classes_with_RAM_only_fixture=True,actual_new_cell_methods_with_mocked_Controller_UI_and_closure=True,
                actual_application_or_audio_file_started=False,actual_private_GUI_prestart_run=False,
                application_runner_or_planner_rebound=False,actual_deadline_or_continuity_qualified=False,integrated_N4_cells=0,N4_accepted=False))
            print('PASS: 16 application delivery launch/join/cell wiring checks; actual GUI prestart/source run remains',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_APPLICATION_DELIVERY_PROBE_PRESERVED',error_type=type(exc).__name__,
                owner=identity(process),source_snapshots=snapshots,
                admission=bind(output/'ADMISSION.json') if (output/'ADMISSION.json').exists() else None)); raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
