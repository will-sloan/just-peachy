"""CPU14 host-only replay/final history contracts. See README_DEVELOPER_REPLAY.md."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import sys
import uuid


def register(output_root):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=ctypes.c_void_p
    handle=kernel.GetCurrentProcess()
    kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    if not kernel.SetProcessAffinityMask(handle,16384):raise ctypes.WinError(ctypes.get_last_error())
    clocks=[ctypes.c_ulonglong() for _ in range(4)]
    kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not kernel.GetProcessTimes(handle,*(ctypes.byref(v) for v in clocks)):raise ctypes.WinError(ctypes.get_last_error())
    root=Path(output_root)/('hour-replay-checks-'+uuid.uuid4().hex)
    root.mkdir(parents=True,exist_ok=False)
    with (root/'REGISTERED_OWNER.json').open('x') as stream:
        json.dump(dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,
            affinity_mask=16384,creation_filetime=clocks[0].value,
            create_time=(clocks[0].value-116444736000000000)/10000000),stream)
        stream.flush();os.fsync(stream.fileno())
    return root


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-root',required=True)
    ap.add_argument('--retained-vendor',type=Path,required=True)
    ap.add_argument('--checks',nargs='+')
    args=ap.parse_args();root=register(args.output_root)
    sys.dont_write_bytecode=True
    import hashlib
    import importlib
    import threading
    import types
    import unittest
    import wave
    from unittest.mock import patch
    import numpy as np
    import developer_replay as replay
    import final_snapshot as final
    from profiles import SessionPolicy,RuntimeSelection
    from runtime_support import DiskBudget,encoded,publish,digest
    package=types.ModuleType('retained_hour_fixture');package.__path__=[str(args.retained_vendor)]
    sys.modules[package.__name__]=package
    scheduler_module=importlib.import_module(package.__name__+'.research_scheduler_v3')
    clock_module=importlib.import_module(package.__name__+'.research_s7_policy')

    class FastStop:
        def __init__(self,after=None):self.now=100.;self.calls=0;self.after=after;self.stopped=False
        def is_set(self):return self.stopped
        def set(self):self.stopped=True
        def wait(self,seconds):
            self.now+=seconds;self.calls+=1
            if self.after is not None and self.calls>self.after:self.stopped=True
            return self.stopped

    class Checks(unittest.TestCase):
        def fixture(self,name,frames=64003):
            path=root/(name+'.wav')
            values=((np.arange(frames,dtype=np.int64)%20001)-10000).astype('<i2')
            with wave.open(str(path),'wb') as f:f.setparams((1,2,16000,frames,'NONE','not compressed'));f.writeframes(values.tobytes())
            return path,values

        def test_exact_hour_continuous_offsets_small_blocks(self):
            path,values=self.fixture('hour')
            expected=values.astype(np.float32)/32768.
            stop=FastStop();events={'source_started':0,'source_repeat_boundary':0,'source_stopped':0}
            counters=dict(sent=0,maximum=0,finish=0,boundary=0)
            class Journal:
                def append(inner,audio):
                    start=counters['sent']%len(values)
                    np.testing.assert_array_equal(audio,expected[start:start+len(audio)])
                    counters['sent']+=len(audio);counters['maximum']=max(counters['maximum'],len(audio))
                def finish(inner,error):self.assertIsNone(error);counters['finish']+=1
            def callback(kind,row):
                self.assertNotEqual(kind,'fatal')
                if kind in events:events[kind]+=1
                if kind=='source_repeat_boundary':
                    counters['boundary']+=1
                    self.assertEqual(row['logical_start_sample'],counters['boundary']*len(values))
                    self.assertFalse(row['models_reset'])
            source=replay.RepeatedSavedSource(Journal(),path,callback,SessionPolicy(3600,True),stop,
                repeat_input_seconds=3600,expected_sha256=digest(path),append_batch_samples=320,clock=lambda:stop.now)
            source._run()
            self.assertIsNone(source.error);self.assertTrue(source.done.is_set())
            self.assertEqual(source.sent,57600000);self.assertEqual(counters['sent'],source.sent)
            self.assertEqual(counters['finish'],1);self.assertLessEqual(counters['maximum'],320)
            self.assertEqual(events['source_started'],1);self.assertEqual(events['source_stopped'],1)
            self.assertEqual(events['source_repeat_boundary'],(source.sent-1)//len(values))
            self.assertAlmostEqual(stop.now,3700.,places=6)

        def test_repeat_explicit_policy_hash_and_stop(self):
            selection=RuntimeSelection('nemotron','redimnet','saved','current_delayed')
            policy=SessionPolicy(3600,True)
            for seconds,source,sid in ((300,'x',None),(3600,None,'kept'),(True,'x',None)):
                with self.assertRaises(ValueError):replay.validate_repeat(selection,policy,source,sid,seconds)
            path,_=self.fixture('stop')
            with self.assertRaises(ValueError):replay.RepeatedSavedSource(None,path,None,policy,FastStop(),repeat_input_seconds=3600,expected_sha256='0'*64)
            received=[];finished=[];stop=FastStop(after=3)
            journal=types.SimpleNamespace(append=lambda x:received.append(len(x)),finish=finished.append)
            source=replay.RepeatedSavedSource(journal,path,lambda *args:None,policy,stop,
                repeat_input_seconds=3600,expected_sha256=digest(path),append_batch_samples=320,clock=lambda:stop.now)
            source._run();self.assertEqual(source.sent,960);self.assertEqual(received,[320]*3)
            self.assertEqual(finished,[None]);self.assertTrue(source.done.is_set())

        def test_hour_host_reservation_is_separate_and_bounded(self):
            import ast
            tree=ast.parse(Path(__file__).with_name('host_operations.py').read_text(encoding='utf-8'))
            node=next(item for item in tree.body if isinstance(item,ast.FunctionDef) and item.name=='output_copy_reservation')
            namespace={};exec(compile(ast.Module(body=[node],type_ignores=[]),'host-reservation','exec'),namespace)
            reserve=namespace['output_copy_reservation'];amount=2306682336
            payload=dict(schema='just-peachy.full-app-hour-admission.v1',reviewed=True,
                workflow='continuous-full-application-repeated-wav',repeat_input_seconds=3600,
                runtime_seconds=4680,maximum_output_bytes=amount,independent_pc_copy_bytes=amount)
            self.assertEqual(reserve('launch_full_app_soak_action.py',payload),amount)
            for changes in (dict(reviewed=False),dict(runtime_seconds=1500),dict(repeat_input_seconds=300),
                    dict(independent_pc_copy_bytes=amount-1),dict(maximum_output_bytes=3*1024**3+1,independent_pc_copy_bytes=3*1024**3+1)):
                with self.assertRaises(ValueError):reserve('launch_full_app_soak_action.py',dict(payload,**changes))
            with self.assertRaises(ValueError):reserve('launch_pipeline_qualification_action.py',payload)
            self.assertEqual(reserve('launch_gui_check_action.py',dict(workflow='capture-save-replay-discard',runtime_seconds=1500,maximum_output_bytes=567398992)),567398992)

        def test_external_backup_reservation_requires_actual_reviewed_overlay(self):
            import ast,base64
            tree=ast.parse(Path(__file__).with_name('host_operations.py').read_text(encoding='utf-8'))
            node=next(item for item in tree.body if isinstance(item,ast.FunctionDef) and item.name=='backup_copy_action_allowed')
            namespace=dict(base64=base64,hashlib=hashlib)
            exec(compile(ast.Module(body=[node],type_ignores=[]),'external-reservation','exec'),namespace)
            allowed=namespace['backup_copy_action_allowed']
            raw=Path(__file__).with_name('backup_external_common.py').read_bytes()
            payload=dict(maximum_output_bytes=16*1024**2,external_backup_common=dict(
                schema='just-peachy.external-backup-common.v1',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),base64=base64.b64encode(raw).decode()))
            self.assertTrue(allowed('launch_backup_external_action.py',payload))
            self.assertFalse(allowed('another_action.py',payload))
            for delta in (dict(bytes=len(raw)+1),dict(sha256='0'*64),dict(base64=base64.b64encode(raw+b'x').decode())):
                self.assertFalse(allowed('launch_backup_external_action.py',dict(payload,external_backup_common=dict(payload['external_backup_common'],**delta))))
            self.assertFalse(allowed('launch_backup_external_action.py',dict(payload,maximum_output_bytes=32*1024**2)))
            raw2=Path(__file__).with_name('backup_external_common_v2.py').read_bytes()
            payload2=dict(maximum_output_bytes=16*1024**2,external_backup_common=dict(
                schema='just-peachy.external-backup-common.v2',bytes=len(raw2),sha256=hashlib.sha256(raw2).hexdigest(),base64=base64.b64encode(raw2).decode()))
            self.assertTrue(allowed('launch_backup_external_action_v2.py',payload2))
            self.assertFalse(allowed('launch_backup_external_action.py',payload2))
            self.assertFalse(allowed('launch_backup_external_action_v2.py',payload))
            self.assertFalse(allowed('launch_backup_external_action_v2.py',dict(payload2,maximum_output_bytes=32*1024**2)))
            for delta in (dict(bytes=len(raw2)+1),dict(sha256='0'*64),dict(base64=base64.b64encode(raw2+b'x').decode())):
                self.assertFalse(allowed('launch_backup_external_action_v2.py',dict(payload2,external_backup_common=dict(payload2['external_backup_common'],**delta))))

        def test_full_app_admission_exact_budget_and_wrapper(self):
            import launch_raw_qualification_action as action
            import storage,profiles
            policy=SessionPolicy(3600,True,max_drain_seconds=600,max_backlog_seconds=120)
            selection=RuntimeSelection('nemotron','redimnet','saved','current_delayed')
            disk=storage.StoragePolicy();metadata=16*1024**2+3600*256*1024
            expected=disk.estimate_bytes(dict(duration_seconds=3600,sample_rate=16000,mode='processed',
                metadata_reserve_bytes=metadata))+metadata+disk.metadata_allowance_bytes+32*1024**2
            payload=dict(selection=selection.validate(),policy=policy.validate(),maximum_output_bytes=expected,
                independent_pc_copy_bytes=expected,workflow='continuous-full-application-repeated-wav',repeat_input_seconds=3600,runtime_seconds=4680)
            with patch.object(action,'load_pure',side_effect=lambda package,name:{'storage':storage,'profiles':profiles}[name]):
                plan=action.budget_plan(Path(__file__).parent,{},payload,'full_app_hour')
                for changes in (dict(repeat_input_seconds=300),dict(independent_pc_copy_bytes=expected-1),
                        dict(maximum_output_bytes=expected-1,independent_pc_copy_bytes=expected-1),dict(workflow='component')):
                    with self.assertRaises(ValueError):action.budget_plan(Path(__file__).parent,{},dict(payload,**changes),'full_app_hour')
            self.assertEqual(plan['runtime_seconds'],4680);self.assertEqual(plan['maximum_files'],2048)
            self.assertGreater(expected,2*1024**3);self.assertLess(expected,3*1024**3)
            source=action.wrapper_source(dict(kind='full_app_hour',budget=plan))
            compile(source,'<native-full-app-wrapper-not-executed>','exec')
            self.assertLess(source.index("put('OWNER.json',owner)"),source.index('scope_path.read_bytes()'))
            self.assertIn('WHOLE_UNIT_MEMORY.jsonl',source);self.assertIn('768*1024**2',source)
            publish(root/'FULL_APP_PLAN.json',plan)

        def dispatcher(self,count=4):
            identity=types.SimpleNamespace(snapshot=lambda:dict(identities=3))
            policy=scheduler_module.CausalSchedulerV3(None,identity)
            policy._closed=True
            policy._utterances={str(i):dict(utterance_id=str(i),text='retained text '+str(i),
                is_final=i%2==0,ordered=[3,2,1],signed=-0.0,history=[dict(label='Unknown')]) for i in range(count)}
            clock=clock_module.ObservedClock();clock.set_origin(123.)
            clock.history={str(i):dict(observed_first=float(i),history_extra=['all','fields']) for i in range(count)}
            worker=types.SimpleNamespace(closed=True,thread=types.SimpleNamespace(is_alive=lambda:False),
                error=None,completed=9,accepted=9,snapshot=lambda:dict(closed=True,accepted=9))
            dispatcher=object.__new__(clock_module.ObservedPolicyDispatcher)
            dispatcher.scheduler=policy;dispatcher.clock=clock;dispatcher.worker=worker
            return dispatcher

        def test_actual_retained_snapshot_exact_order_fields_and_revised(self):
            dispatcher=self.dispatcher()
            original=dispatcher.snapshot()
            original_mapping=dispatcher.scheduler._utterances
            folder=root/'snapshot';folder.mkdir()
            budget=DiskBudget(16*1024**2,reserve_bytes=0)
            adapter=final.ClosedSchedulerSnapshot(dispatcher,folder,budget)
            result=adapter.snapshot()
            self.assertIs(dispatcher.scheduler._utterances,original_mapping)
            self.assertEqual(list(adapter.rows()),original.pop('utterances'))
            actual={k:v for k,v in result.items() if k not in ('utterances_external','original_schema_version')}
            actual['schema_version']=result['original_schema_version']
            self.assertEqual(actual,original)
            engine=types.SimpleNamespace(_session_dir=folder,_telemetry={},_research_v3=True,
                _s6d_punctuated={'0':dict(raw_text='retained text 0',text='Retained text 0.')})
            final.write_revised_transcript(engine,adapter,budget)
            revised=list(final.iter_rows(folder,engine._telemetry['latest_labelled_transcript_external']))
            self.assertEqual([r['utterance_id'] for r in revised],['0','2'])
            self.assertEqual(revised[0]['display_text'],'Retained text 0.')
            self.assertEqual(revised[1]['history_extra'],['all','fields'])
            self.assertEqual(adapter.snapshot(),result)

        def test_full_history_never_copied_by_original_snapshot(self):
            dispatcher=self.dispatcher(4096)
            folder=root/'bounded';folder.mkdir()
            original_base=importlib.import_module(package.__name__+'.research_scheduler').CausalScheduler.snapshot
            counts=[]
            def checked_snapshot(policy):
                counts.append(len(policy._utterances))
                self.assertEqual(len(policy._utterances),0)
                return original_base(policy)
            with patch.object(importlib.import_module(package.__name__+'.research_scheduler').CausalScheduler,'snapshot',checked_snapshot):
                adapter=final.ClosedSchedulerSnapshot(dispatcher,folder,DiskBudget(16*1024**2,reserve_bytes=0))
                result=adapter.snapshot()
            self.assertEqual(counts,[0]);self.assertEqual(len(dispatcher.scheduler._utterances),4096)
            self.assertEqual(sum(1 for _ in adapter.rows()),4096)
            self.assertLess(len(encoded(result)),4096)

        def test_summary_preserves_exact_retained_fields_before_budgeted_write(self):
            import ast,time
            tree=ast.parse((args.retained_vendor/'runtime.py').read_text())
            node=next(item for owner in tree.body if isinstance(owner,ast.ClassDef)
                for item in owner.body if isinstance(item,ast.FunctionDef) and item.name=='_write_summary')
            namespace=dict(json=json,os=os,uuid=uuid,time=time)
            exec(compile(ast.Module(body=[node],type_ignores=[]),'<retained-pure-summary-method>','exec'),namespace)
            folder=root/'summary';folder.mkdir()
            config=types.SimpleNamespace(assets=[types.SimpleNamespace(component_id='fixture',sha256='a'*64)],
                identity_score_threshold=.1,identity_margin_threshold=.2,identity_minimum_evidence_sec=.3,clustering_threshold=.4)
            engine=types.SimpleNamespace(_session_dir=folder,_state='COMPLETED',config=config,
                telemetry=lambda:dict(scheduler={'utterances_external':{'sha256':'b'*64}}),
                _research_profile=types.SimpleNamespace(effective=lambda config:dict(complete='retained'),xvf=types.SimpleNamespace(mode='none')),
                _research_v3=True,_spatial_provider=types.SimpleNamespace(sha256='c'*64))
            namespace['_write_summary'](engine)
            original=json.loads((folder/'session_summary.json').read_bytes())
            budget=DiskBudget(1024**2,reserve_bytes=0)
            final.write_summary(engine,budget)
            self.assertEqual(json.loads((folder/'session_summary.json').read_bytes()),original)
            self.assertEqual(budget.accepted,(folder/'session_summary.json').stat().st_size)
            before=(folder/'session_summary.json').read_bytes()
            with self.assertRaises(BufferError):final.write_summary(engine,DiskBudget(1,reserve_bytes=0))
            self.assertEqual((folder/'session_summary.json').read_bytes(),before)

        def test_closed_guard_corruption_and_budget_failure(self):
            dispatcher=self.dispatcher();folder=root/'reject';folder.mkdir()
            adapter=final.ClosedSchedulerSnapshot(dispatcher,folder,DiskBudget(1024**2,reserve_bytes=0))
            dispatcher.worker.closed=False
            with self.assertRaises(RuntimeError):adapter.snapshot()
            self.assertEqual(list(folder.iterdir()),[])
            dispatcher.worker.closed=True
            reference=adapter.snapshot()['utterances_external']
            path=folder/(reference['path']+'.000000')
            data=path.read_bytes();path.write_bytes(data.replace(b'Unknown',b'Changed',1))
            with self.assertRaises(ValueError):list(adapter.rows())
            second=root/'budget';second.mkdir()
            mapping=dispatcher.scheduler._utterances
            with self.assertRaises(BufferError):final.ClosedSchedulerSnapshot(dispatcher,second,DiskBudget(8192,reserve_bytes=0)).snapshot()
            self.assertIs(dispatcher.scheduler._utterances,mapping)
            self.assertFalse((second/'scheduler-utterances.jsonl.index.json').exists())

    suite=unittest.TestSuite(Checks(name) for name in args.checks) if args.checks else unittest.defaultTestLoader.loadTestsFromTestCase(Checks)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    receipt=dict(path=str(root),tests=result.testsRun,errors=len(result.errors),failures=len(result.failures),
        native_executed=False,models_executed=False,synthetic_time=True)
    publish(root/'TEST_RESULT.json',receipt)
    print(encoded(receipt).decode())
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':raise SystemExit(main())
