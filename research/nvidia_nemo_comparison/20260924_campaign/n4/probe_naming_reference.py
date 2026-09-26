"""Guarded model-free reference qualification; see README_NAMING_REFERENCE.md."""
import argparse
from datetime import datetime, timezone
import io
from pathlib import Path
import time
import unittest

from common import bind, freeze, load, verify
from metric_process import exact_process, identity, pin
from naming_reference import build_context
from probe_application_transport_review import active_d1
from review_scoring_bank import guard, require, shared_allowance
from scoring_bank import writer_lock
import test_naming_reference as regression

HERE = Path(__file__).resolve().parent
LOCAL = Path('G:/Just_Peachy_N1/20260924_campaign/local')
OWN = ('naming_reference.py','test_naming_reference.py','probe_naming_reference.py','README_NAMING_REFERENCE.md')


def prerequisites():
    entries = [bind(HERE/name) for name in OWN]; qualifications = {}
    for name,status in (('APPLICATION_LABEL_CHECK_V1.json','PASS_APPLICATION_RECORDED_HEADING_DEVELOPMENT_ONLY'),
                        ('INTEGRATED_SCORING_CHECK_V1.json','PASS_SCORING_ADAPTER_DEVELOPMENT_ONLY')):
        q = load(HERE/name); require(q['status'] == status, 'Reference prerequisite status differs')
        verify(q['private_receipt']); proof = load(q['private_receipt']['path']); verify(proof['admission'])
        require(exact_process(load(proof['admission']['path'])['owner']) is None, 'Prior helper remains active')
        entries.extend([bind(HERE/name),*q['code']]); qualifications[name] = q
    result = {}
    for b in entries:
        require(b['path'] not in result or result[b['path']] == b, 'Conflicting reference dependency')
        result[b['path']] = b; verify(b)
    labels = qualifications['APPLICATION_LABEL_CHECK_V1.json']; scoring = qualifications['INTEGRATED_SCORING_CHECK_V1.json']
    verify(scoring['admission']); scoring_admission = load(scoring['admission']['path'])
    verify(labels['application_context']); application = load(labels['application_context']['path'])
    preparation = bind(LOCAL/'n4/preparation-v2/PREPARATION_RECEIPT.json'); prep = load(preparation['path'])
    manifests = [b for b in prep['outputs'] if Path(b['path']).name == 'AUDIO_ONLY_480.json']
    require(len(manifests) == 1, 'One prepared full-bank audio manifest required')
    inputs = dict(accepted_n2=bind(HERE.parent/'n2/FINAL_REVIEW.json'),
        accepted_screen=bind(HERE.parent/'n2/evaluation/SCREEN_SUMMARY.json'),
        scoring_qualification=bind(HERE/'INTEGRATED_SCORING_CHECK_V1.json'),scoring_admission=scoring['admission'],
        preparation=preparation,manifest=manifests[0],truth=scoring_admission['truth'],
        windows=bind(LOCAL/'n2/evaluation/WINDOW_MANIFEST.json'),
        gallery_preparation=application['gallery_preparation'],application_context=labels['application_context'])
    verify(labels['synthetic_heading_review'])
    return list(result.values()), inputs, labels['synthetic_heading_review']


def run(output):
    process = pin(); started = time.monotonic()
    require(not output.exists() and output.resolve().is_relative_to(LOCAL/'n4'), 'Fresh private reference probe required')
    with writer_lock(LOCAL/'n4/metric-scoring.owner.lock'):
        guard(output,LOCAL,started,720); inventory = shared_allowance(LOCAL); active = active_d1()
        freeze(output/'PROBE_OWNER.json',dict(owner=identity(process),utc=datetime.now(timezone.utc).isoformat()))
        (output/'source').mkdir(); snapshots = []
        for name in OWN:
            path = output/'source'/name; path.write_bytes((HERE/name).read_bytes())
            require(bind(path)['sha256'] == bind(HERE/name)['sha256'], 'Reference source snapshot differs')
            snapshots.append(bind(path))
        try:
            code, inputs, observed_binding = prerequisites()
            freeze(output/'ADMISSION.json',dict(owner=identity(process),code=code,source_snapshots=snapshots,
                inventory=inventory,D1_snapshot=active,reference_inputs=inputs,synthetic_observed_review=observed_binding,
                fixture_scope='Existing accepted evaluator truth and E provenance; prior synthetic GUI observation; no new app/audio/model'))
            checkpoint = lambda: guard(output,LOCAL,started,720)
            context = build_context(inputs,checkpoint=checkpoint); freeze(output/'CONTEXT.json',context)
            observed = load(observed_binding['path']); transport = observed['observed']['content']['cell']['transport']
            payloads = [b for b in transport['evidence'] if Path(b['path']).name == 'INPUT.json']
            require(len(payloads) == 1, 'One saved observed input required'); verify(payloads[0])
            regression.CONTEXT.update(context=context,observed=observed,payload=load(payloads[0]['path']),
                windows=load(inputs['windows']['path']),windows_binding=inputs['windows'],
                document=load(context['galleries']['E0']['gallery']['path']),truth=load(inputs['truth']['path']),
                manifest=load(inputs['manifest']['path']),checkpoint=checkpoint)
            stream = io.StringIO(); tests = unittest.TextTestRunner(stream=stream,verbosity=2).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(regression.ReferenceTests))
            (output/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
            require(tests.wasSuccessful() and tests.testsRun == 16 and not tests.skipped, 'Reference join tests failed')
            freeze(output/'SYNTHETIC_REFERENCE_JOIN.json',regression.CONTEXT['joined'])
            for b in code+context['evidence']+[observed_binding,payloads[0]]: verify(b)
            after = active_d1()
            require(after['result']['child'] == active['result']['child'] and after['run_id'] == active['run_id'], 'Numerical owner changed')
            checkpoint()
            freeze(output/'RESULT.json',dict(status='PASS_EVALUATOR_NAMING_REFERENCE_CHECKS_ONLY',
                utc=datetime.now(timezone.utc).isoformat(),admission=bind(output/'ADMISSION.json'),
                context=bind(output/'CONTEXT.json'),tests=bind(output/'tests.txt'),tests_passed=tests.testsRun,
                synthetic_reference_join=bind(output/'SYNTHETIC_REFERENCE_JOIN.json'),population=context['population'],
                galleries={e:{k:g[k] for k in ('available_size','intended_size','unavailable_count')} for e,g in context['galleries'].items()},
                D1_after=after,evaluator_truth_loaded=True,models_loaded=0,audio_loaded=False,
                synthetic_observation_only=True,naming_accuracy_qualified=False,integrated_N4_cells=0,N4_accepted=False))
            print('PASS: 16 reference checks; 480 existing truth cells and both E rosters; synthetic GUI join only',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_NAMING_REFERENCE_PROBE_PRESERVED',
                error_type=type(exc).__name__,owner=identity(process),source_snapshots=snapshots,
                admission=bind(output/'ADMISSION.json') if (output/'ADMISSION.json').exists() else None))
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
