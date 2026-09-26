"""Invisible delivery-cell preparation; README_DELIVERY_APPLICATION_PRESTART.md."""
import argparse
from datetime import datetime,timezone
import io
import os
from pathlib import Path
import secrets
import sys
import time
import unittest

import psutil
from common import bind,fingerprint,freeze,load,verify
from metric_process import exact_process,identity,pin
from application_source_context import prepare,review
from paced_application_runner import actual_desktop,qualified_interpreter
from private_application_process_v3 import PrivateApplicationProcess
from probe_application_transport_review import active_d1
from review_application_transport import record,validate_lifetime
from review_scoring_bank import guard,require,shared_allowance
from scoring_bank import writer_lock
import test_application_source_context as lineage_tests

HERE=Path(__file__).resolve().parent
LOCAL=Path('G:/Just_Peachy_N1/20260924_campaign/local')
QUALIFICATIONS={
    'PACED_APPLICATION_CELL_CHECK_V1.json':'PASS_PRIVATE_TK_AND_APPLICATION_PRESTART_ONLY',
    'NATIVE_JOURNAL_RETENTION_CHECK_V1.json':'PASS_NATIVE_JOURNAL_RETENTION_DEVELOPMENT_ONLY',
    'APPLICATION_DELIVERY_CHECK_V1.json':'PASS_APPLICATION_DELIVERY_INTEGRATION_DEVELOPMENT_ONLY',
    'APPLICATION_TRANSPORT_REVIEW_CHECK_V1.json':'PASS_APPLICATION_TRANSPORT_REVIEW_DEVELOPMENT_ONLY',
}


def code_bindings():
    names=('test_delivery_application_prestart.py','probe_delivery_application_prestart.py','README_DELIVERY_APPLICATION_PRESTART.md',
        'application_source_context.py','test_application_source_context.py','test_journal_application_prestart.py',
        'README_APPLICATION_SOURCE_CONTEXT.md','paced_application_runner.py',
        'probe_application_transport_review.py')
    values=[bind(HERE/name) for name in names]
    for name,status in QUALIFICATIONS.items():
        b=bind(HERE/name);q=load(b['path']);require(q['status']==status,'Prestart dependency qualification differs')
        values += [b,*q['code']]
    result={}
    for b in values:
        require(b['path'] not in result or result[b['path']]==b,'Conflicting source qualification');result[b['path']]=b
    return list(result.values())


def child(admission_path,nonce):
    process=pin();root=admission_path.parent
    _,admission=record(admission_path,root);_,registered=record(root/'REGISTRATION.json',root)
    require(registered['nonce']==nonce and len(nonce)==64 and registered['child']==identity(process)
        and registered['parent']==admission['owner'],'Exact model-free test registration differs')
    parent=exact_process(admission['owner'])
    require(parent is not None and parent.pid==process.ppid() and parent.cpu_affinity()==[14]
        and process.cpu_affinity()==[14] and actual_desktop()==registered['desktop'],
        'Wrong parent, CPU or private desktop for prestart test')
    require(registered['script']==bind(__file__) and registered['argv_sha256']==fingerprint(process.cmdline())
        and registered['admission']==bind(admission_path),'Test child command or admission differs')
    for b in admission['code']:verify(b)
    context=review(admission['application_context'])
    require(admission['source']==context['source_receipt'] and admission['gallery_preparation']==context['gallery_preparation']
        and admission['catalog']==context['catalog'] and admission['runtimes']==context['runtimes'],'Child application context differs')
    source=Path(load(context['source_receipt']['path'])['prototype'])
    require(not any(k=='app' or k.startswith('app.') for k in sys.modules),'Application imported before qualified derivative binding')
    sys.path[:0]=[str(source.parent),str(source),str(source/'vendor'),str(HERE.parents[3])]
    os.environ['N4_PACED_CELL_ADMISSION']=str(admission_path)
    from test_delivery_application_prestart import DeliveryApplicationTests
    stream=io.StringIO();tests=unittest.TextTestRunner(stream=stream,verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(DeliveryApplicationTests))
    (root/'gui_tests.txt').write_text(stream.getvalue(),encoding='utf-8')
    for b in admission['code']:verify(b)
    freeze(root/'CHILD_RESULT.json',dict(status='PASS_DELIVERY_APPLICATION_PRESTART_ONLY' if tests.wasSuccessful() else 'FAILED_PRESERVED',
        owner=identity(process),admission=bind(admission_path),tests=bind(root/'gui_tests.txt'),tests_run=tests.testsRun,
        failures=len(tests.failures),errors=len(tests.errors),skipped=len(tests.skipped),
        actual_source_or_model_execution=False,integrated_N4_cells=0,N4_accepted=False))
    require(tests.wasSuccessful() and tests.testsRun==9 and not tests.skipped,'Derivative GUI prestart tests failed')


def run(output):
    process=pin();started=time.monotonic();require(not output.exists() and output.resolve().is_relative_to(LOCAL/'n4'),
        'Fresh private prestart output required')
    with writer_lock(LOCAL/'n4/metric-scoring.owner.lock'):
        checkpoint=lambda:guard(output,LOCAL,started,720)
        checkpoint();inventory=shared_allowance(LOCAL);active=active_d1();code=code_bindings()
        for b in code:verify(b)
        (output/'source').mkdir(parents=True)
        for b in code[:5]:(output/'source'/Path(b['path']).name).write_bytes(Path(b['path']).read_bytes())
        application_context=prepare(output/'context');context=review(application_context)
        original=load(HERE/'PACED_APPLICATION_CELL_CHECK_V1.json');old=load(original['private_receipt']['path'])
        verify(old['admission']);original_admission=load(old['admission']['path'])
        job=original_admission['job'];verify(original_admission['panel'])
        require(job in load(original_admission['panel']['path'])['jobs'],'Prestart job is outside the fixed panel')
        freeze(output/'ADMISSION.json',dict(owner=identity(process),output=str(output.resolve()),code=code,
            source_snapshots=[bind(p) for p in sorted((output/'source').iterdir())],application_context=application_context,
            source=context['source_receipt'],catalog=context['catalog'],gallery_preparation=context['gallery_preparation'],
            runtimes=context['runtimes'],job=job,inventory=inventory,D1_snapshot=active,models_loaded=0,
            source_execution_authorized_by_this_probe=False))
        owned=None
        try:
            lineage_tests.CONTEXT.update(parent_binding=context['component_source_receipt'],parent=load(context['component_source_receipt']['path']),
                child=load(context['source_receipt']['path']),parent_catalog=context['component_catalog'],catalog=context['catalog'],
                gallery=load(context['component_gallery_preparation']['path']))
            stream=io.StringIO();tests=unittest.TextTestRunner(stream=stream,verbosity=2).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(lineage_tests.SourceContextTests))
            (output/'lineage_tests.txt').write_text(stream.getvalue(),encoding='utf-8')
            require(tests.wasSuccessful() and tests.testsRun==4 and not tests.skipped,'Source context regression failed')
            nonce=secrets.token_hex(32);executable=qualified_interpreter();script=bind(__file__)
            owned=PrivateApplicationProcess(output/'lifetime',executable_binding=executable,script_binding=script,
                arguments=['child','--admission',str((output/'ADMISSION.json').resolve()),'--nonce',nonce],cpu=14)
            def register(who,**bindings):
                freeze(output/'REGISTRATION.json',dict(parent=identity(process),child=who,nonce=nonce,desktop=owned.desktop_name,
                    admission=bind(output/'ADMISSION.json'),script=script,argv_sha256=bindings['argv_sha256']))
            owned.spawn_suspended();owned.resume(register)
            until=time.monotonic()+240
            while not owned.root_exited():
                checkpoint();require(time.monotonic()<until,'Derivative prestart child time budget reached')
                owned.members();time.sleep(.5)
            lifetime=owned.close(grace_seconds=0)
            validation=validate_lifetime(lifetime,owner=owned.owner,executable=executable,script=script,
                argv_sha256=fingerprint(owned.argv),desktop=owned.desktop_name,cpu=14)
            result=load(output/'CHILD_RESULT.json');checks=load(output/'CHECKS.json')
            require(result['status']=='PASS_DELIVERY_APPLICATION_PRESTART_ONLY' and result['tests_run']==9 and result['skipped']==0
                and result['owner']==checks['owner']==owned.owner and len(checks['prepared_cells'])==16,'Application prestart population differs')
            catalog=load(context['catalog']['path']);expected={r['key'] for r in catalog['backends'] if r['implemented']}
            require({r['backend'] for r in checks['prepared_cells']}==expected,'Missing or duplicated prepared backend')
            for r in checks['prepared_cells']:
                verify(r['prepared']);verify(r['result']);closed=load(r['result']['path'])
                require(closed['status']=='PREPARED_ONLY_CLOSED' and closed['controller_worker_exited'] is True
                    and closed['source_start_requested'] is False,'Prepared Controller failed to close')
                verify(closed['delivery_capture']); delivery=load(closed['delivery_capture']['path'])
                require(delivery['status']=='PREPARED_WITHOUT_SOURCE_DELIVERY' and delivery['test_seams_used'] is False
                    and delivery['launch_attempts']==0 and delivery['observation'] is None and delivery['trace'] is None
                    and closed['delivery_join'] is None and closed['application_variant']=='source-delivery-v2',
                    'Delivery adapter ran unexpectedly during prestart')
            for b in code:verify(b)
            review(application_context);checkpoint();after=active_d1()
            require(after['result']['child']==active['result']['child'] and after['run_id']==active['run_id'],'D1 ownership changed')
            freeze(output/'RESULT.json',dict(status='PASS_DELIVERY_CONTEXT_AND_PRESTART_ONLY',utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'),application_context=application_context,
                lineage_tests=bind(output/'lineage_tests.txt'),child_result=bind(output/'CHILD_RESULT.json'),checks=bind(output/'CHECKS.json'),
                factory_checks=bind(output/'FACTORY_CHECKS.json'),lifetime=bind(output/'lifetime/LIFETIME.json'),lifetime_review=validation,
                tests_passed=13,prepared_backends=16,actual_Tk_and_Controller_prestart=True,actual_source_or_model_execution=False,
                source_run_branch_tested=False,application_plan_or_runner_rebound=False,D1_after=after,integrated_N4_cells=0,N4_accepted=False))
            print('PASS: four lineage and nine invisible GUI checks; 16 delivery-cell backends prepared and closed; no inference',flush=True)
        except BaseException as exc:
            if owned is not None and not owned.closed:owned.close(grace_seconds=2)
            freeze(output/'FAILED.json',dict(status='FAILED_DELIVERY_APPLICATION_PRESTART_PRESERVED',error_type=type(exc).__name__,
                admission=bind(output/'ADMISSION.json')))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    prepare_parser=sub.add_parser('run');prepare_parser.add_argument('--output',type=Path,required=True)
    child_parser=sub.add_parser('child');child_parser.add_argument('--admission',type=Path,required=True);child_parser.add_argument('--nonce',required=True)
    args=parser.parse_args()
    if args.command=='run':run(args.output)
    else:child(args.admission,args.nonce)
