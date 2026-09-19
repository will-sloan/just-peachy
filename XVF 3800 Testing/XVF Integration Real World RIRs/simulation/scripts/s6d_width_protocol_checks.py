"""Independent model-free width protocol fixtures; README_S6D_WIDTH_PROTOCOL_CHECKS.md."""
from __future__ import annotations
import argparse
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import importlib.util
import inspect
import io
import json
import os
from pathlib import Path
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

W = None
OUT = None
MATRIX = None
PLAN = None
PLAN_BINDING = None
SERIAL = 0


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def bind(p):
    p=Path(p).resolve(); data=p.read_bytes()
    return dict(path=str(p),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())


def save(p,v):
    p=Path(p); p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(v,sort_keys=True)+'\n',encoding='utf-8')


def validate(value):
    if len(inspect.signature(W.validate_index).parameters)>=3:
        return W.validate_index(value,PLAN_BINDING,PLAN)
    return W.validate_index(value,PLAN_BINDING)


def observer(owner,hb,stop,cells,expected):
    kwargs={'interval':.01}
    if 'expected_cells' in inspect.signature(W.Observer).parameters:
        kwargs['expected_cells']=expected
    return W.Observer(owner,hb,stop,cells,**kwargs)


def fresh(label):
    global SERIAL
    SERIAL+=1; path=OUT/'cases'/f'{SERIAL:02d}_{label}'
    path.mkdir(parents=True)
    return path


def make_matrix(reuse=None):
    global MATRIX,PLAN,PLAN_BINDING
    payload=b'{"synthetic_fixture_only": true}\n'
    checksum=hashlib.sha256(payload).hexdigest()
    if reuse is not None:
        root=Path(reuse).resolve();PLAN=json.loads((root/'PLAN.json').read_text(encoding='utf-8'))
        cells=PLAN['cells'];rows=[]
        if len(cells)!=3840 or [r['job_id'] for r in PLAN['jobs']]!=W.JOBS:
            raise ValueError('Exact prior synthetic matrix required')
        paths=set()
        for cell in cells:
            path=Path(cell['output_path']).resolve()
            if path.parent!=root or path in paths or path.read_bytes()!=payload:
                raise ValueError('Only distinct existing tiny synthetic inputs may be reused')
            paths.add(path)
            rows.append({k:cell[k] for k in ('candidate_id','case_id','stream','identity_tap')} |
                        dict(status='COMPLETE',result=dict(path=str(path),bytes=len(payload),sha256=checksum)))
        PLAN_BINDING=bind(root/'PLAN.json')
        MATRIX=dict(status='COMPLETE_ADMITTED_POLICY_REPLAY_ONLY',completed=3840,requested=3840,rows=rows,jobs=W.JOBS,
            source_plan=PLAN_BINDING,new_neural_jobs=0,hardware_jobs=0,scoring_complete=False)
        return
    root=OUT/'synthetic_matrix'; root.mkdir()
    cells=[]; rows=[]
    for job in W.JOBS:
        candidate,tap=job.rsplit('_',1)
        for family in range(1,13):
            for number in range(1,21):
                cid=f'S45_{family:02d}_{number:02d}'
                cell_id=f'{job}__{cid}'; p=root/(cell_id+'.json'); p.write_bytes(payload)
                b=dict(path=str(p.resolve()),bytes=len(payload),sha256=checksum)
                cells.append(dict(cell_id=cell_id,job_id=job,candidate_id=candidate,case_id=cid,stream=tap,identity_tap=tap,output_path=str(p.resolve())))
                rows.append(dict(candidate_id=candidate,case_id=cid,stream=tap,identity_tap=tap,status='COMPLETE',result=b))
    PLAN={'cells':cells,'jobs':[{'job_id':j} for j in W.JOBS],'output_root':str(root)}
    save(root/'PLAN.json',PLAN); PLAN_BINDING=bind(root/'PLAN.json')
    MATRIX=dict(status='COMPLETE_ADMITTED_POLICY_REPLAY_ONLY',completed=3840,requested=3840,rows=rows,jobs=W.JOBS,
        source_plan=PLAN_BINDING,new_neural_jobs=0,hardware_jobs=0,scoring_complete=False)


class WidthProtocolChecks(unittest.TestCase):
    def test_atomic_save_retries_transient_permission_without_partial_target(self):
        root=fresh('save_transient'); target=root/'heartbeat.json'; save(target,{'old':True})
        real_replace=W.os.replace; calls=[]
        def temporarily_blocked(source,destination):
            calls.append((str(source),str(destination)))
            self.assertEqual(json.loads(target.read_text()),{'old':True})
            if len(calls)<3:
                error=PermissionError(13,'Synthetic transient Windows access refusal'); error.winerror=5
                raise error
            return real_replace(source,destination)
        with patch.object(W.os,'replace',temporarily_blocked), patch.object(W.time,'sleep') as sleep:
            W.save(target,{'new':True})
        self.assertEqual(len(calls),3); self.assertEqual(len({c[0] for c in calls}),1)
        self.assertEqual(json.loads(target.read_text()),{'new':True})
        self.assertGreaterEqual(sleep.call_count,2)

    def test_atomic_save_persistent_permission_is_bounded_and_preserves_old_target(self):
        root=fresh('save_persistent'); target=root/'heartbeat.json'; save(target,{'old':True})
        error=PermissionError(13,'Synthetic persistent Windows access refusal'); error.winerror=5
        with patch.object(W.os,'replace',side_effect=error) as replace, patch.object(W.time,'sleep'):
            with self.assertRaises(PermissionError): W.save(target,{'new':True})
        self.assertGreater(replace.call_count,1); self.assertLessEqual(replace.call_count,20)
        self.assertEqual(json.loads(target.read_text()),{'old':True})

    def test_atomic_save_does_not_retry_other_os_errors(self):
        root=fresh('save_no_space'); target=root/'heartbeat.json'; save(target,{'old':True})
        with patch.object(W.os,'replace',side_effect=OSError(28,'Synthetic no space')) as replace:
            with self.assertRaises(OSError): W.save(target,{'new':True})
        self.assertEqual(replace.call_count,1)
        self.assertEqual(json.loads(target.read_text()),{'old':True})

    def test_exact_matrix_positive(self):
        self.assertTrue(all(validate(deepcopy(MATRIX)).values()))

    def test_missing_duplicate_failed_and_wrong_hash_reject(self):
        mutations=[lambda v:v['rows'].pop(),lambda v:v['rows'].__setitem__(0,deepcopy(v['rows'][1])),
            lambda v:v['rows'][0].update(status='FAILED'),lambda v:v['rows'][0]['result'].update(sha256='0'*64)]
        for mutation in mutations:
            v=deepcopy(MATRIX); mutation(v)
            with self.assertRaises((ValueError,KeyError)): validate(v)

    def test_arbitrary_unique_matrix_rejects_despite_3840_count(self):
        v=deepcopy(MATRIX)
        for index,row in enumerate(v['rows']):
            row.update(candidate_id='UNDECLARED',case_id=f'ARBITRARY_{index}',stream='INVENTED',identity_tap='INVENTED')
        with self.assertRaises(ValueError): validate(v)

    def test_reused_prediction_path_rejects(self):
        v=deepcopy(MATRIX)
        v['rows'][1]['result']=deepcopy(v['rows'][0]['result'])
        with self.assertRaises(ValueError): validate(v)

    def test_identity_tap_mutation_rejects(self):
        v=deepcopy(MATRIX); v['rows'][0]['identity_tap']='O1'
        with self.assertRaises(ValueError): validate(v)

    def test_progress_counts_only_valid_exact_committed_cells(self):
        root=fresh('progress'); cells=root/'cells'; cells.mkdir()
        selected=PLAN['cells'][:3]
        owner=dict(run_id='fixture',job_id='fixture_job',child_run_id='fixture_child',pid=os.getpid(),creation_time=1.)
        o=observer(owner,root/'heartbeat.json',root/'stop.json',cells,selected)
        def committed(i):return dict(cell=selected[i],result=MATRIX['rows'][i]['result'],raw_words_invariant=True)
        save(cells/(selected[0]['cell_id']+'.json'),committed(0))
        (cells/(selected[1]['cell_id']+'.json')).write_text('{',encoding='utf-8')
        save(cells/'UNDECLARED.json',committed(0))
        broken=committed(2); broken['raw_words_invariant']=False
        save(cells/(selected[2]['cell_id']+'.json'),broken)
        o.publish()
        self.assertEqual(o.count,1,'Filename presence is not a committed exact cell receipt')
        save(cells/(selected[1]['cell_id']+'.json'),committed(1)); o.publish()
        self.assertEqual(o.count,2)
        value=json.loads((root/'heartbeat.json').read_text())
        self.assertEqual(value['progress_count'],2)

    def test_foreign_stop_ignored_and_exact_owner_stop_signalled(self):
        root=fresh('stop_owner'); owner=dict(run_id='fixture',job_id='fixture_job',child_run_id='fixture_child',pid=os.getpid(),creation_time=1.)
        stop=root/'stop.json'; o=observer(owner,root/'heartbeat.json',stop,root/'cells',PLAN['cells'][:1])
        # Match supervisor.save's atomic STOP replacement, not a synthetic truncate/write race.
        W.save(stop,dict(owner,child_run_id='different'))
        signals=[]; foreign_read=threading.Event(); signalled=threading.Event(); original_read=W.read
        def checked_read(path):
            value=original_read(path)
            if Path(path)==stop and value.get('child_run_id')=='different':foreign_read.set()
            return value
        def interrupt():signals.append(True); signalled.set()
        with patch.object(W._thread,'interrupt_main',interrupt),patch.object(W,'read',checked_read):
            o.thread.start()
            try:
                self.assertTrue(foreign_read.wait(3.)); self.assertEqual(signals,[])
                W.save(stop,owner); self.assertTrue(signalled.wait(3.))
            finally:o.close()
        save(root/'OBSERVED_STOP.json',dict(signals=signals,stop_requested=o.stop_requested,errors=o.errors))
        self.assertEqual(signals,[True]); self.assertTrue(o.stop_requested); self.assertEqual(o.errors,[])

    def test_partial_stop_document_is_error_not_matching_owner_stop(self):
        root=fresh('partial_stop'); owner=dict(run_id='fixture',job_id='fixture_job',child_run_id='fixture_child',pid=os.getpid(),creation_time=1.)
        stop=root/'stop.json'; stop.write_text('{',encoding='utf-8')
        o=observer(owner,root/'heartbeat.json',stop,root/'cells',PLAN['cells'][:1])
        signalled=threading.Event()
        with patch.object(W._thread,'interrupt_main',signalled.set):
            o.thread.start()
            try:self.assertTrue(signalled.wait(3.))
            finally:o.close()
        save(root/'OBSERVED_STOP.json',dict(stop_requested=o.stop_requested,errors=o.errors))
        self.assertFalse(o.stop_requested); self.assertTrue(o.errors)

    def test_schema_invalid_receipts_are_unfinished_not_observer_crash(self):
        root=fresh('schema_invalid'); cells=root/'cells'; cells.mkdir()
        owner=dict(run_id='fixture',job_id='fixture_job',child_run_id='fixture_child',pid=os.getpid(),creation_time=1.)
        selected=PLAN['cells'][:2]
        save(cells/(selected[0]['cell_id']+'.json'),[])
        save(cells/(selected[1]['cell_id']+'.json'),dict(cell=selected[1],raw_words_invariant=True,result=None))
        o=observer(owner,root/'heartbeat.json',root/'stop.json',cells,selected)
        o.publish()
        self.assertEqual(o.count,0)

    def test_close_preempts_running_receipt_scan_between_entries(self):
        root=fresh('close_scan'); cells=root/'cells'; cells.mkdir()
        owner=dict(run_id='fixture',job_id='fixture_job',child_run_id='fixture_child',pid=os.getpid(),creation_time=1.)
        selected=PLAN['cells'][:3]
        for i,cell in enumerate(selected):save(cells/(cell['cell_id']+'.json'),dict(cell=cell,result=MATRIX['rows'][i]['result'],raw_words_invariant=True))
        o=observer(owner,root/'heartbeat.json',root/'stop.json',cells,selected)
        started,release=threading.Event(),threading.Event(); reads=[]; original_read=W.read
        def gated_read(path):
            reads.append(str(path))
            if len(reads)==1:started.set(); release.wait(1.)
            return original_read(path)
        with patch.object(W,'read',gated_read):
            o.thread=threading.Thread(target=o.publish)
            o.thread.start(); self.assertTrue(started.wait(1.))
            o.closed.set(); release.set(); o.close()
        self.assertLessEqual(len(reads),1,'A close request must not wait for the remainder of a3840-receipt scan')
        self.assertFalse(o.thread.is_alive())

    def test_final_scan_revalidates_changed_and_removed_cached_receipts(self):
        root=fresh('final_receipt'); cells=root/'cells'; cells.mkdir()
        owner=dict(run_id='fixture',job_id='fixture_job',child_run_id='fixture_child',pid=os.getpid(),creation_time=1.)
        cell=PLAN['cells'][0]; p=cells/(cell['cell_id']+'.json')
        valid=dict(cell=cell,result=MATRIX['rows'][0]['result'],raw_words_invariant=True)
        save(p,valid); o=observer(owner,root/'heartbeat.json',root/'stop.json',cells,[cell])
        o.publish(); self.assertEqual(o.count,1)
        o.closed.set(); save(p,dict(valid,raw_words_invariant=False))
        o.publish('FINALIZING',final=True)
        self.assertEqual(o.count,0,'Final scan must not trust cached progress after receipt mutation')
        save(p,valid); o.publish('FINALIZING',final=True); self.assertEqual(o.count,1)
        p.unlink(); o.publish('FINALIZING',final=True)
        self.assertEqual(o.count,0,'Final scan must detect removal of a previously cached receipt')

    def test_final_scan_still_observes_matching_stop_after_observer_join(self):
        root=fresh('final_stop'); cells=root/'cells'; cells.mkdir()
        owner=dict(run_id='fixture',job_id='fixture_job',child_run_id='fixture_child',pid=os.getpid(),creation_time=1.)
        cell=PLAN['cells'][0]
        save(cells/(cell['cell_id']+'.json'),dict(cell=cell,result=MATRIX['rows'][0]['result'],raw_words_invariant=True))
        stop=root/'stop.json'; o=observer(owner,root/'heartbeat.json',stop,cells,[cell])
        o.closed.set(); W.save(stop,owner)
        with self.assertRaises((RuntimeError,KeyboardInterrupt)):
            o.publish('FINALIZING',final=True)
        self.assertTrue(o.stop_requested)

    def execute_fixture(self,kind):
        root=fresh(kind); helper_path=root/'never_imported_helper.py'
        helper_path.write_text('# Fixture only; module_at is mocked. No policy/model/device code.\n',encoding='utf-8')
        plan=dict(PLAN,output_root=str(root/'policy'),helper=bind(helper_path))
        plan_path=root/'PLAN.json'; save(plan_path,plan); pb=bind(plan_path)
        auth_path=root/'ADMISSION.json'; save(auth_path,dict(root_review_passed=True,plan_sha256=pb['sha256'],allowed_jobs=W.JOBS))
        report=Path(plan['output_root'])/'executions'/('jobs_'+digest(W.JOBS)[:16])
        paths={'S6D_RUN_ID':'fixture_run','S6D_JOB_ID':'fixture_job','S6D_CHILD_RUN_ID':'fixture_child',
            'S6D_HEARTBEAT_PATH':str(root/'heartbeat.json'),'S6D_COMPLETION_PATH':str(root/'COMPLETE.json'),
            'S6D_STOP_REQUEST_PATH':str(root/'STOP.json')}
        calls=[]
        def fake_execute(p,a,jobs):
            calls.append((p,a,jobs))
            if kind=='helper_failure':raise RuntimeError('synthetic helper failure')
            if kind=='missing_index':return
            if kind=='matching_stop':
                W.save(root/'STOP.json',W.identity())
                deadline=time.monotonic()+2
                while time.monotonic()<deadline:time.sleep(.005)
                raise RuntimeError('stop interrupt did not arrive')
            if kind=='changed_admission':save(auth_path,dict(root_review_passed=False,plan_sha256='changed',allowed_jobs=[]))
            for cell,row in zip(plan['cells'],MATRIX['rows']):
                save(report/'cells'/(cell['cell_id']+'.json'),dict(cell=cell,result=row['result'],raw_words_invariant=True))
            result=deepcopy(MATRIX); result['source_plan']=pb; save(report/'PREDICTION_INDEX.json',result)
        helper=SimpleNamespace(execute=fake_execute,digest=digest)
        # Only fixture bindings/import dispatch are substituted. Real wrapper control flow,
        # Observer, STOP interrupt, index validation and closure all execute unchanged.
        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ,paths))
            stack.enter_context(patch.object(W,'PLAN_SHA',pb['sha256']))
            stack.enter_context(patch.object(W,'HELPER_SHA',plan['helper']['sha256']))
            stack.enter_context(patch.object(W,'module_at',return_value=helper))
            if kind=='matching_stop_after_final_scan':
                original_publish=W.Observer.publish
                def stop_after_final_scan(obs,*args,**kwargs):
                    result=original_publish(obs,*args,**kwargs)
                    if kwargs.get('final') is True:W.save(root/'STOP.json',W.identity())
                    return result
                stack.enter_context(patch.object(W.Observer,'publish',stop_after_final_scan))
            result=W.execute(plan_path,auth_path)
        return root,result,calls

    def test_same_process_success_semantics_and_closed_observer(self):
        root,ok,calls=self.execute_fixture('normal')
        self.assertTrue(ok); self.assertEqual(len(calls),1)
        result=json.loads((root/'COMPLETE.json').read_text())
        self.assertTrue(result['protocol_observer_closed']); self.assertEqual(result['protocol_errors'],[])
        self.assertEqual(result['policy_cells'],3840); self.assertEqual(result['pid'],os.getpid())

    def test_helper_failure_cannot_write_success_completion(self):
        root,ok,calls=self.execute_fixture('helper_failure')
        self.assertFalse(ok); self.assertFalse((root/'COMPLETE.json').exists())
        self.assertEqual(json.loads((root/'WRAPPER_FAILURE.json').read_text())['status'],'FAILED')

    def test_missing_index_blocks_completion(self):
        root,ok,calls=self.execute_fixture('missing_index')
        self.assertFalse(ok); self.assertFalse((root/'COMPLETE.json').exists())

    def test_real_owner_stop_interrupt_is_caught_without_success(self):
        root,ok,calls=self.execute_fixture('matching_stop')
        self.assertFalse(ok); self.assertFalse((root/'COMPLETE.json').exists())
        result=json.loads((root/'WRAPPER_FAILURE.json').read_text())
        self.assertIn('KeyboardInterrupt',result['failure']); self.assertTrue(result['protocol_observer_closed'])

    def test_changed_admission_cannot_be_reported_as_success(self):
        root,ok,calls=self.execute_fixture('changed_admission')
        self.assertFalse(ok); self.assertFalse((root/'COMPLETE.json').exists())

    def test_stop_after_final_scan_cannot_write_success(self):
        root,ok,calls=self.execute_fixture('matching_stop_after_final_scan')
        self.assertFalse(ok); self.assertFalse((root/'COMPLETE.json').exists())
        self.assertTrue((root/'WRAPPER_FAILURE.json').exists())


def main():
    global W,OUT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wrapper',type=Path,default=Path(__file__).with_name('s6d_width_protocol_v1.py'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--tests',nargs='+',help='Optional exact unittest method names for a bounded targeted check')
    parser.add_argument('--reuse-matrix',type=Path,help='Read-only existing synthetic_matrix directory; never modified')
    args=parser.parse_args(); OUT=args.output.resolve()
    if OUT.exists():raise ValueError('Fresh fixture output required')
    OUT.mkdir(parents=True); source=bind(args.wrapper)
    spec=importlib.util.spec_from_file_location('independent_width_protocol',args.wrapper)
    W=importlib.util.module_from_spec(spec); spec.loader.exec_module(W)
    matrix_required=not args.tests or not all(name.startswith('test_atomic_save_') for name in args.tests)
    if matrix_required: make_matrix(args.reuse_matrix)
    with (OUT/'FIXTURE_LOG.txt').open('x',encoding='utf-8') as log:
        runner=unittest.TextTestRunner(stream=log,verbosity=2)
        suite=unittest.defaultTestLoader.loadTestsFromTestCase(WidthProtocolChecks)
        if args.tests:
            available={t._testMethodName:t for t in suite}
            if set(args.tests)-set(available):raise ValueError('Unknown fixture method')
            suite=unittest.TestSuite(available[name] for name in args.tests)
        result=runner.run(suite)
    wrapper_unchanged=bind(args.wrapper)==source
    unchanged=wrapper_unchanged
    reused_unchanged=None
    if matrix_required and args.reuse_matrix is not None:
        reused_unchanged=(bind(Path(args.reuse_matrix)/'PLAN.json')==PLAN_BINDING and
            all(Path(cell['output_path']).read_bytes()==b'{"synthetic_fixture_only": true}\n' for cell in PLAN['cells']))
        unchanged=unchanged and reused_unchanged
    receipt=dict(status='PASS_MODEL_FREE_ONLY' if result.wasSuccessful() and unchanged else 'ADVERSE_FIXTURES_PRESERVED',
        wrapper=source,wrapper_unchanged=wrapper_unchanged,tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),
        failed_tests=[t.id() for t,text in result.failures],error_tests=[t.id() for t,text in result.errors],
        fixture_code=bind(__file__),fixture_readme=bind(Path(__file__).with_name('README_S6D_WIDTH_PROTOCOL_CHECKS.md')),
        log=bind(OUT/'FIXTURE_LOG.txt'),synthetic_matrix_created=matrix_required and args.reuse_matrix is None,
        reused_synthetic_plan=PLAN_BINDING if matrix_required and args.reuse_matrix is not None else None,
        reused_synthetic_inputs_unchanged=reused_unchanged,
        model_calls=0,policy_replay_calls=0,device_calls=0,
        scope='Synthetic plans/receipts and fake helper only. Real wrapper semantic validation, same-process control, observer and owner STOP execute. No production helper module is imported.')
    save(OUT/'FIXTURE_RECEIPT.json',receipt)
    print(json.dumps({k:receipt[k] for k in ('status','tests','failures','errors','failed_tests')}))
    return 0 if result.wasSuccessful() and unchanged else 1


if __name__=='__main__':raise SystemExit(main())
