"""Synthetic wrapper ownership/limit/exit checks; see README_PACKAGE.md."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import sys
import types
import unittest
from unittest import mock
import uuid


def register(output_root):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    handle = kernel.GetCurrentProcess()
    kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    if not kernel.SetProcessAffinityMask(handle, 16384):
        raise ctypes.WinError(ctypes.get_last_error())
    clocks = [ctypes.c_ulonglong() for _ in range(4)]
    kernel.GetProcessTimes.argtypes = [ctypes.c_void_p] + [ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not kernel.GetProcessTimes(handle, *(ctypes.byref(value) for value in clocks)):
        raise ctypes.WinError(ctypes.get_last_error())
    root = Path(output_root)/('native-scope-checks-'+uuid.uuid4().hex)
    root.mkdir(parents=True, exist_ok=False)
    with (root/'REGISTERED_OWNER.json').open('x') as stream:
        json.dump(dict(schema='just-peachy.host-registered-owner.v1', pid=os.getpid(), cpu=14,
            affinity_mask=16384, creation_filetime=clocks[0].value,
            create_time=(clocks[0].value-116444736000000000)/10000000), stream)
        stream.flush(); os.fsync(stream.fileno())
    return root


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-root', required=True)
    ap.add_argument('--checks',nargs='+',help='Explicit focused unittest method names; omitted runs this small suite')
    ap.add_argument('--event-corpus',type=Path,help='Optional explicit closed private JSONL corpus; never enumerates audio')
    args = ap.parse_args()
    root = register(args.output_root)
    sys.dont_write_bytecode = True
    import native_scope as module

    class Checks(unittest.TestCase):
        def test_inventory_hash_and_unlisted_module_rejected(self):
            directory=root/'inventory'; directory.mkdir()
            raw=b'"""fixture, never imported"""\n'
            (directory/'launcher.py').write_bytes(raw)
            manifest=module.encoded(dict(schema='just-peachy.v29.package.v1',files=[dict(
                path='launcher.py',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())]))
            (directory/'PACKAGE_MANIFEST.json').write_bytes(manifest)
            pin=hashlib.sha256(manifest).hexdigest()
            module.verified_inventory(directory,pin)
            (directory/'unexpected.py').write_text('# never imported\n')
            with self.assertRaises(ValueError):
                module.verified_inventory(directory,pin)

        def test_inside_returns_headless_failure_and_forwards_long_policy(self):
            directory=root/'service'; directory.mkdir()
            owner=dict(pid=123,start_ticks=456,boot_id='fixture')
            receipt=dict(unit='fixture.service',owner=owner,main_pid=123,
                invocation_id='abc',control_group='/user.slice/fixture')
            module.write(directory/'UNIT_OWNERSHIP.json',receipt)
            arguments=types.SimpleNamespace(inside=str(directory),unit='fixture.service',
                binding='fixture/BINDING.json',data_root='fixture/data',manifest_sha256='f'*64,
                entrypoint='launcher.py',
                maximum_session_seconds=3600,max_drain_seconds=240,max_backlog_seconds=120,developer_soak=True)
            forwarded=[]
            fake=types.SimpleNamespace(main=lambda: forwarded.extend(sys.argv) or 7)
            real_read=Path.read_text
            def read(path,*args,**kwargs):
                return '0::/user.slice/fixture\n' if str(path).replace('\\','/')=='/proc/self/cgroup' else real_read(path,*args,**kwargs)
            with mock.patch.object(module,'bootstrap',return_value=owner), mock.patch.object(module,'verified_binding',return_value={}), \
                 mock.patch.object(module,'properties',return_value=dict(ControlGroup='/user.slice/fixture',InvocationID='abc',MainPID='123')), \
                 mock.patch.dict(os.environ,{'INVOCATION_ID':'abc'}), mock.patch.dict(sys.modules,{'launcher':fake}), \
                 mock.patch.object(Path,'read_text',read), mock.patch.object(sys,'argv',[]):
                self.assertEqual(module.inside(arguments,['--headless']),7)
            self.assertIn('--developer-soak',forwarded)
            self.assertEqual(forwarded[forwarded.index('--maximum-session-seconds')+1],'3600')
            self.assertEqual(json.loads((directory/'SERVICE_EXIT.json').read_bytes())['exit_code'],7)

        def test_frontend_file_hard_limit_allows_finite_worker_derivation(self):
            limits=[]
            resource=types.SimpleNamespace(RLIMIT_AS=1,RLIMIT_STACK=2,RLIMIT_FSIZE=3,RLIMIT_CORE=4,
                setrlimit=lambda kind,value:limits.append((kind,value)),getrlimit=lambda kind:dict(limits)[kind])
            with mock.patch.dict(sys.modules,{'resource':resource}), \
                 mock.patch.dict(os.environ,{'MALLOC_ARENA_MAX':'1','MALLOC_MMAP_THRESHOLD_':'131072','MALLOC_TRIM_THRESHOLD_':'131072'}), \
                 mock.patch.object(module.platform,'system',return_value='Linux'), \
                 mock.patch.object(module.platform,'machine',return_value='aarch64'), \
                 mock.patch.object(module.os,'sched_setaffinity',create=True), \
                 mock.patch.object(module.shutil,'disk_usage',return_value=types.SimpleNamespace(free=12*1024**3)), \
                 mock.patch.object(module,'identity',return_value=dict(pid=123,start_ticks=456,boot_id='fixture')):
                module.bootstrap(root/'limits',inside_service=True)
            self.assertIn((3,(32*1024**2,7*1024**3)),limits)
            self.assertIn((1,(256*1024**2,768*1024**2)),limits)
            envelope=json.loads((root/'limits/ENVELOPE.json').read_bytes())
            self.assertEqual(envelope['allocator_environment'],{'MALLOC_ARENA_MAX':'1','MALLOC_MMAP_THRESHOLD_':'131072','MALLOC_TRIM_THRESHOLD_':'131072'})

        def test_session_room_requires_complete_policy_and_closure(self):
            import release_authorization as authorization
            path=root/'room.json';module.write(path,dict(deadline_monotonic=1000))
            policy=types.SimpleNamespace(total_deadline_seconds=500)
            self.assertEqual(authorization.require_service_room(path,policy,now=350),650)
            with self.assertRaises(PermissionError):authorization.require_service_room(path,policy,now=351)

        def test_production_reusable_selection_and_policy_gates(self):
            import release_authorization as authorization
            from profiles import RuntimeSelection
            selection=RuntimeSelection().validate()
            receipt=dict(allowed_selections=[selection],limits=dict(maximum_session_seconds=300,
                maximum_developer_seconds=7200,max_drain_seconds=600,max_backlog_seconds=600))
            policy=dict(developer_soak=False,maximum_session_seconds=300,max_drain_seconds=100,max_backlog_seconds=100)
            selected=types.SimpleNamespace(validate=lambda:dict(selection))
            selected_policy=types.SimpleNamespace(validate=lambda:dict(policy))
            with mock.patch.object(authorization,'authorization',return_value=('production',receipt)):
                for _ in range(5):
                    result=authorization.authorize_session(dict(candidate_content_sha256='a'*64),selected,selected_policy)
                    self.assertFalse(result['native_qualified'])
                policy['maximum_session_seconds']=301
                with self.assertRaises(PermissionError):authorization.authorize_session({},selected,selected_policy)
                policy['maximum_session_seconds']=300;selection['input_source']='saved'
                receipt['allowed_selections']=[dict(selection,input_source='live')]
                with self.assertRaises(PermissionError):authorization.authorize_session({},selected,selected_policy)

        def test_bounded_receipt_refuses_oversized_input(self):
            import release_authorization as authorization
            path=root/'oversized.json';path.write_bytes(b' '*33)
            with self.assertRaises(ValueError):authorization.bounded_json(path,32)

        def test_production_receipt_does_not_read_boot_or_expiry(self):
            import release_authorization as authorization
            from profiles import RuntimeSelection
            directory=root/'production';directory.mkdir()
            binding=dict(target=str(directory),candidate_content_sha256='a'*64,installed_manifest_sha256='b'*64,
                native_launch_enabled=True,authorization_kind='production')
            acceptance=dict(schema='just-peachy.v29.production-acceptance.v1',accepted=True,reviewer='fixture',
                accepted_unix=1,target=str(directory),candidate_content_sha256='a'*64,installed_manifest_sha256='b'*64,
                previous_desktop_sha256='c'*64,allowed_selections=[RuntimeSelection().validate()],
                limits=dict(maximum_session_seconds=300,maximum_developer_seconds=3600,max_drain_seconds=120,max_backlog_seconds=120),
                assets=[dict(path='/home/peachyprototype/JustPeachy/fixture',resolved='/home/peachyprototype/JustPeachy/fixture',bytes=1,sha256='d'*64)],
                full_backup=dict(scope='selected-release-and-user-data',root='reviewed-root',manifest_path='reviewed-manifest',
                    completion_path='reviewed-completion',manifest_sha256='e'*64,completion_sha256='f'*64))
            module.write(directory/'PRODUCTION_ACCEPTANCE.json',acceptance)
            binding['production_acceptance_sha256']=hashlib.sha256((directory/'PRODUCTION_ACCEPTANCE.json').read_bytes()).hexdigest()
            with mock.patch.object(Path,'read_text',side_effect=AssertionError('Production must not read boot')):
                for _ in range(3):self.assertEqual(authorization.authorization(binding)[0],'production')

        def test_event_shared_allocation_preserves_large_probability_records(self):
            from runtime_support import DiskBudget, SegmentedText
            work=root/'event-budget';work.mkdir()
            allowance=28573696  # Actual 45-second build06 reservation, unchanged.
            budget=DiskBudget(allowance*5//6,reserve_bytes=0)
            writers=[SegmentedText(work/name,maximum_bytes=budget.maximum,
                budget=budget,segment_bytes=1024**2) for name in ('events','clocks','captions')]
            row=[0.123456789012345,0.987654321098765,0.1,0.2,0.3,0.4,0.5,0.6]
            payload=dict(schema_version='fixture',event_type='n2_diarization_frames',
                source_time_sec=21.22,payload=dict(frame_start=0,probabilities=[row]*8000,
                    original_metadata=dict(ordered_channels=8,reason='exact full field recovery')))
            raw=json.dumps(payload,ensure_ascii=False,separators=(',',':'))+'\n'
            self.assertTrue(393200 < len(raw.encode()) < 1024**2)
            hashes=[hashlib.sha256() for _ in writers]
            try:
                for _ in range(16):
                    writers[0].write(raw);hashes[0].update(raw.encode())
                    # A drained queue isolates disk allocation from queue pressure.
                    writers[0].queue.join()
                for index in (1,2):
                    record=json.dumps(dict(kind='fixture',index=index))+'\n'
                    writers[index].write(record);hashes[index].update(record.encode())
            finally:
                for writer in writers:writer.close()
            self.assertGreater(writers[0].accepted,allowance//6)
            self.assertLess(budget.accepted,budget.maximum)
            self.assertEqual(budget.accepted,sum(writer.accepted for writer in writers))
            for index,writer in enumerate(writers):
                actual=hashlib.sha256()
                for segment in sorted(work.glob(writer.path.name+'.[0-9]*')):
                    self.assertLessEqual(segment.stat().st_size,1024**2)
                    with segment.open('rb') as stream:
                        for line in stream:
                            actual.update(line)
                            if index==0:self.assertEqual(json.loads(line),payload)
                self.assertEqual(actual.hexdigest(),hashes[index].hexdigest())
                self.assertEqual(writer.pending,0)
                self.assertEqual(writer.completed,writer.accepted)

        def test_event_aggregate_exhaustion_is_explicit_and_cursor_stays(self):
            from runtime_support import DiskBudget, SegmentedText
            work=root/'event-budget-refusal';work.mkdir()
            budget=DiskBudget(100,reserve_bytes=0)
            first=SegmentedText(work/'events',maximum_bytes=100,budget=budget)
            second=SegmentedText(work/'trace',maximum_bytes=100,budget=budget)
            first.write('x'*60);first.queue.join()
            with self.assertRaisesRegex(BufferError,'Aggregate metadata'):
                second.write('y'*41)
            self.assertEqual(second.accepted,0);self.assertEqual(second.pending,0)
            self.assertEqual(budget.accepted,60)
            self.assertEqual(second.refusal['boundary'],'aggregate_disk_bytes')
            first.close()
            with self.assertRaises(RuntimeError):second.close()
            receipt=json.loads((work/'trace.index.json').read_bytes())
            self.assertFalse(receipt['complete']);self.assertEqual(receipt['refusal']['incoming_bytes'],41)
            self.assertEqual((work/'events.000000').read_bytes(),b'x'*60)

        def test_event_logical_record_bound_remains_finite(self):
            from runtime_support import DiskBudget, SegmentedText
            work=root/'event-record-refusal';work.mkdir()
            writer=SegmentedText(work/'events',maximum_bytes=4*1024**2,
                budget=DiskBudget(4*1024**2,reserve_bytes=0))
            with self.assertRaisesRegex(BufferError,'logical_record'):
                writer.write('x'*(1024**2+1))
            self.assertEqual(writer.accepted,0);self.assertEqual(writer.budget.accepted,0)
            with self.assertRaises(RuntimeError):writer.close()

        def test_compact_display_exact_nested_roundtrip_and_sequence(self):
            from event_compaction import Codec
            import copy
            base=dict(event_type='s6d_display',payload=dict(session_id='one',
                rows=[dict(id=index,text='unchanged '*30,probability=0.123456789012345) for index in range(40)],
                deleted='old',signed_zero=0.0),time=1.0)
            changed=copy.deepcopy(base);changed['time']=2.0
            changed['payload']['rows'][3]['text']='renamed ✓';changed['payload']['rows'].append(dict(id=40,text='new'))
            changed['payload'].pop('deleted');changed['payload']['signed_zero']=-0.0
            third=copy.deepcopy(changed);third['payload']['rows']=third['payload']['rows'][:20]
            producer=Codec();consumer=Codec();records=[]
            for event in (base,changed,third):
                raw,state=producer.prepare(json.dumps(event).encode());producer.commit(state)
                records.append(json.loads(raw));decoded=consumer.decode(records[-1])
                self.assertEqual(module.encoded(decoded),module.encoded(event))
                decoded['payload']['rows'].clear() # Consumer mutation cannot alter the next patch base.
            self.assertEqual(producer.patches,2);self.assertEqual(consumer.patches,2)
            self.assertEqual(producer.maximum_state_bytes,consumer.maximum_state_bytes)
            self.assertLess(producer.maximum_state_bytes,1024**2)
            for alteration in (dict(seq=4),dict(base_seq=3),dict(base_sha256='0'*64),dict(event_sha256='0'*64)):
                broken=Codec();broken.decode(records[0])
                with self.assertRaises(ValueError):broken.decode(dict(records[1],**alteration))

        def test_compact_display_session_change_and_admission_failure_do_not_alias(self):
            from event_compaction import Codec, CompactEventText
            from runtime_support import DiskBudget
            codec=Codec()
            for session in ('one','two','one'):
                event=dict(event_type='s6d_display',payload=dict(session_id=session,text='x'*1000))
                raw,state=codec.prepare(json.dumps(event).encode())
                self.assertEqual(json.loads(raw)['encoding'],'full');codec.commit(state)
            work=root/'compact-refusal';work.mkdir()
            writer=CompactEventText(work/'events',maximum_bytes=8192,budget=DiskBudget(8192,reserve_bytes=0))
            good=json.dumps(dict(event_type='s6d_display',payload=dict(session_id='one',text='small')))+'\n'
            writer.write(good);writer.sink.queue.join()
            before=writer.codec.metrics()
            with self.assertRaises(ValueError):writer.write('x'*(1024**2+1))
            self.assertEqual(writer.codec.sequence,before['records'])
            self.assertEqual(writer.codec.logical_digest.hexdigest(),before['logical_sha256'])
            with self.assertRaises(RuntimeError):writer.close()
            self.assertFalse(json.loads((work/'events.compaction.json').read_bytes())['complete'])

        def test_compact_private_closed_corpus_roundtrip(self):
            if args.event_corpus is None:self.skipTest('Explicit private corpus path not provided')
            from event_compaction import CompactEventText, iter_events
            from runtime_support import DiskBudget
            source=args.event_corpus
            self.assertFalse(source.is_symlink());self.assertLessEqual(source.stat().st_size,16*1024**2)
            source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
            work=root/'private-roundtrip';work.mkdir()
            path=work/'events.jsonl';maximum=32*1024**2
            writer=CompactEventText(path,maximum_bytes=maximum,budget=DiskBudget(maximum,reserve_bytes=0),
                segment_bytes=1024**2)
            records=0;probability_records=0;original_logical=hashlib.sha256()
            with source.open('rb') as stream:
                for line in stream:
                    event=json.loads(line);original_logical.update(module.encoded(event)+b'\n')
                    writer.write(line.decode());writer.sink.queue.join();records+=1
            writer.close()
            with source.open('rb') as stream:
                for restored in iter_events(path,maximum_bytes=maximum,maximum_records=100000):
                    original=json.loads(next(stream))
                    self.assertEqual(module.encoded(restored),module.encoded(original))
                    if original.get('event_type')=='n2_diarization_frames':
                        probability_records+=1
                        self.assertEqual(restored['payload'],original['payload'])
                self.assertEqual(stream.read(),b'')
            receipt=json.loads((work/'events.jsonl.compaction.json').read_bytes())
            self.assertEqual(receipt['logical_sha256'],original_logical.hexdigest())
            self.assertEqual(receipt['records'],records);self.assertGreater(receipt['patches'],0)
            self.assertLess(writer.sink.completed,source.stat().st_size)
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),source_hash)
            module.write(work/'ROUNDTRIP.json',dict(source=str(source),source_sha256=source_hash,
                source_bytes=source.stat().st_size,stored_bytes=writer.sink.completed,
                logical_records=records,probability_records=probability_records,
                exact_all_event_fields=True,**writer.codec.metrics()))

        def test_compact_failed_closure_receipt_cannot_be_retried_as_success(self):
            import event_compaction as compact
            from runtime_support import DiskBudget
            work=root/'compact-receipt-failure';work.mkdir();path=work/'events.jsonl'
            writer=compact.CompactEventText(path,maximum_bytes=8192,budget=DiskBudget(8192,reserve_bytes=0))
            writer.write(json.dumps(dict(event_type='s6d_display',payload=dict(session_id='one',text='fixture')))+'\n')
            with mock.patch.object(compact,'publish',side_effect=OSError('injected receipt failure')):
                with self.assertRaisesRegex(OSError,'injected receipt'):writer.close()
            self.assertFalse(writer.thread.is_alive());self.assertIsNone(writer.codec.previous)
            with self.assertRaises(RuntimeError):writer.close()
            with self.assertRaisesRegex(ValueError,'receipt missing'):
                list(compact.iter_events(path,maximum_bytes=8192,maximum_records=10))

        def test_compact_synthetic_hour_has_one_cache_and_complete_timeline(self):
            from event_compaction import CompactEventText, iter_events
            from runtime_support import DiskBudget
            work=root/'compact-hour';work.mkdir();path=work/'events.jsonl'
            maximum=16*1024**2
            writer=CompactEventText(path,maximum_bytes=maximum,budget=DiskBudget(maximum,reserve_bytes=0),
                segment_bytes=65536)
            rows=[dict(id=index,text='retained visible words '*4) for index in range(80)]
            try:
                for second in range(3601):
                    row=dict(event_type='s6d_display',source_time_sec=second,
                        payload=dict(session_id='hour-fixture',rows=rows,cursor=second))
                    writer.write(json.dumps(row)+'\n');writer.sink.queue.join()
                    self.assertEqual(writer.codec.metrics()['cached_displays'],1)
                    self.assertLess(writer.codec.previous_bytes,16384)
            finally:writer.close()
            restored=0
            for restored,event in enumerate(iter_events(path,maximum_bytes=maximum,maximum_records=4000),1):
                self.assertEqual(event['source_time_sec'],restored-1)
                self.assertEqual(event['payload']['rows'],rows)
            self.assertEqual(restored,3601)
            self.assertEqual(writer.codec.patches,3600)
            self.assertLess(writer.sink.completed,writer.codec.logical_bytes//4)

        def test_production_does_not_collapse_experimental_algorithms(self):
            import release_authorization as authorization
            from profiles import RuntimeSelection
            baseline=RuntimeSelection('nemotron','redimnet','saved','current_delayed',True)
            changed=RuntimeSelection('nemotron','redimnet','saved','current_delayed',True,
                embedding_schedule='sparse_clean_turn',speaker_attribution='single_d1_late_labels')
            self.assertNotEqual(authorization.selection_key(baseline),authorization.selection_key(changed))
            receipt=dict(allowed_selections=[authorization.selection_key(baseline)],limits={})
            with mock.patch.object(authorization,'authorization',return_value=('production',receipt)):
                with self.assertRaises(PermissionError):
                    authorization.authorize_session({},changed,types.SimpleNamespace(validate=lambda:{}))

        def test_production_optional_refiner_requires_explicit_new_key(self):
            import release_authorization as authorization
            from profiles import RuntimeSelection
            value=authorization.selection_key(RuntimeSelection('pyannote','redimnet','saved',None,True))
            self.assertIs(value['optional_d1_refiner'],False)
            missing=dict(value);missing.pop('optional_d1_refiner')
            with self.assertRaisesRegex(ValueError,'Complete explicit'):authorization.selection_key(missing)
            optional=dict(value,optional_d1_refiner=True)
            self.assertNotEqual(authorization.selection_key(optional),value)
            receipt=dict(allowed_selections=[value],limits={})
            with mock.patch.object(authorization,'authorization',return_value=('production',receipt)):
                with self.assertRaises(PermissionError):
                    authorization.authorize_session({},types.SimpleNamespace(validate=lambda:optional),
                        types.SimpleNamespace(validate=lambda:{}))

        def test_missing_static_local_import_rejected(self):
            import prepare_package as builder
            with self.assertRaises(ValueError):
                builder.verify_local_imports({'worker.py':b'from late_labels import LabelWriter\n'},
                    {'worker','late_labels'})
            builder.verify_local_imports({'worker.py':b'from late_labels import LabelWriter\n',
                'late_labels.py':b'class LabelWriter: pass\n'},{'worker','late_labels'})

        def test_hour_soak_one_state_and_complete_output_reservation(self):
            import launch_soak_action as soak
            import profiles
            import native_benchmark
            payload=dict(developer_soak=True,wall_paced=True,duration_seconds=3600,repeat_seconds=3600,
                experimental=False,maximum_output_bytes=256*1024**2,independent_pc_copy_bytes=256*1024**2,
                profile='current_delayed',drain_seconds=600,backlog_seconds=600,block_samples=3200)
            policy,plan,required=soak.derive_plan(payload,profiles,native_benchmark,dict(source_samples=715200))
            self.assertEqual(plan['target_samples'],57600000)
            self.assertFalse(plan['reset_between_repetitions'])
            self.assertEqual(plan['maximum_output_bytes'],161081376)
            self.assertLessEqual(required,256*1024**2)
            self.assertGreater(policy.total_deadline_seconds,3600+600)
            compile(soak.WRAPPER,'<unexecuted-soak-wrapper>','exec')
            payload['block_samples']=1600
            with self.assertRaises(ValueError):soak.derive_plan(payload,profiles,native_benchmark,dict(source_samples=715200))

        def test_hour_soak_requires_independent_copy_and_explicit_repetition(self):
            import launch_soak_action as soak
            import profiles
            import native_benchmark
            payload=dict(developer_soak=True,wall_paced=True,duration_seconds=3600,repeat_seconds=3600,
                experimental=False,maximum_output_bytes=256*1024**2,independent_pc_copy_bytes=8*1024**2,
                profile='current_delayed',drain_seconds=600,backlog_seconds=600,block_samples=3200)
            with self.assertRaises(ValueError):soak.derive_plan(payload,profiles,native_benchmark,dict(source_samples=715200))
            payload['independent_pc_copy_bytes']=256*1024**2;payload['repeat_seconds']=3599
            with self.assertRaises(ValueError):soak.derive_plan(payload,profiles,native_benchmark,dict(source_samples=715200))

        def test_soak_native_variant_pair_and_profile(self):
            import launch_soak_action as soak
            path='/home/peachyprototype/JustPeachy/research/nemotron-20260928/live-runtime-tests-20261003/native-threads2-build-01/RUNTIME_VARIANT.json'
            pin='3fdb0a0699e06a0608ca6cf5676676e3416bf291398271ebd3fd9a5bca41bc57'
            payload=dict(profile='chunk52',experimental=True,native_variant=path,native_variant_sha256=pin)
            self.assertEqual(soak.native_variant_args(payload),['--native-variant',path,'--native-variant-sha256',pin])
            self.assertEqual(soak.native_variant_args({}),[])
            for changes in (dict(native_variant_sha256=None),dict(profile='current_delayed'),
                dict(experimental=False),dict(native_variant=path.replace('/RUNTIME_VARIANT.json','/../RUNTIME_VARIANT.json'))):
                with self.assertRaises(ValueError):soak.native_variant_args(dict(payload,**changes))

        def test_motion_close_requires_true_and_dead_thread(self):
            from installed_engine import InstalledSession
            session=object.__new__(InstalledSession);called=[]
            motion=types.SimpleNamespace(close=lambda:called.append('close') or False,
                thread=types.SimpleNamespace(is_alive=lambda:True))
            session.motion=motion
            with self.assertRaises(RuntimeError):session._close_motion()
            self.assertIs(session.motion,motion)
            motion.close=lambda:called.append('close') or True
            with self.assertRaises(RuntimeError):session._close_motion()
            motion.thread.is_alive=lambda:False
            session._close_motion();session._close_motion()
            self.assertIsNone(session.motion);self.assertEqual(called,['close','close','close'])

        def test_prelaunch_cleanup_drains_real_writers_once(self):
            import ast
            import datetime
            import threading
            import time
            from installed_engine import InstalledSession
            from runtime_support import SegmentedText
            # Execute only the pinned stdlib finalizer methods, never import a
            # native installed model graph. This checks the actual retained API.
            base=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/field-artifact-install-v2-evidence/target/deployment/releases/b01-offline-20260930-v12')
            name='vendor/edge_speech_pipeline/runtime.py'
            manifest=json.loads((base/'RELEASE_MANIFEST.json').read_bytes())
            raw=(base/name).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),next(r['sha256'] for r in manifest['files'] if r['path']==name))
            tree=ast.parse(raw)
            methods=[node for item in tree.body if isinstance(item,ast.ClassDef)
                for node in item.body if isinstance(node,ast.FunctionDef)
                and node.name in ('_watch_session','wait_for_completion')]
            self.assertEqual(len(methods),2)
            namespace=dict(threading=threading,time=time,json=json,os=os,datetime=datetime.datetime,
                timezone=datetime.timezone,uuid=uuid,MicrophoneSource=type('UnusedMicrophone',(),{}))
            exec(compile(ast.Module(body=methods,type_ignores=[]),name,'exec'),namespace)
            work=root/'startup-failure';work.mkdir();calls=[]
            writers=[SegmentedText(work/name,maximum_bytes=65536) for name in ('events','transcript','readable','trace')]
            for writer in writers:
                for index in range(24):writer.write(json.dumps(dict(index=index))+'\n')
            class Engine:
                state=property(lambda self:self._state)
                def _fail(self,reason):
                    self._state='FAILED';self._journal.finish(reason)
                def _watch_session(self):
                    calls.append('finalize')
                    try:namespace['_watch_session'](self)
                    finally:self._s7_trace.close()
                def wait_for_completion(self,timeout):return namespace['wait_for_completion'](self,timeout)
            engine=Engine();journal=types.SimpleNamespace(finished=False,committed_samples=0)
            journal.finish=lambda reason:setattr(journal,'finished',True)
            engine.__dict__.update(_session_dir=work,_finalization_thread=None,_finalization_error=None,
                _threads=[],_state='LOADING',_journal=journal,_identity_journal=journal,_source=None,
                _research_v2=False,_research_v3=True,_scheduler=None,_s6d_punctuation=None,_s6d_writer=None,
                _research_profile=types.SimpleNamespace(runtime=types.SimpleNamespace(lane_drain_timeout_sec=2)),
                _telemetry={},_bundle_acquired=False,_event_handle=writers[0],_transcript_handle=writers[1],
                _readable_transcript_handle=writers[2],_s7_trace=writers[3],text_writers=writers[:3],
                _write_summary=lambda:calls.append('summary'),_source_time=lambda:0)
            session=object.__new__(InstalledSession)
            session.engine=engine;session.source=None;session.motion=None;session.attribution_writer=None
            session.failure='injected saved-source validation failure before launch'
            session.policy=types.SimpleNamespace(cleanup_seconds=2)
            session.models=types.SimpleNamespace(close=lambda:calls.append('models'))
            session.close();session.close()
            self.assertEqual(calls.count('finalize'),1)
            self.assertLess(calls.index('finalize'),calls.index('models'))
            for writer in writers:
                self.assertFalse(writer.thread.is_alive())
                receipt=json.loads(writer.path.with_name(writer.path.name+'.index.json').read_bytes())
                self.assertTrue(receipt['complete'])
                self.assertEqual(receipt['accepted_bytes'],receipt['completed_bytes'])
            receipt=json.loads((work/'session_finalization_v3.json').read_bytes())
            self.assertTrue(receipt['event_and_transcript_handles_closed'])

        def test_prelaunch_cleanup_timeout_retains_model_until_reaped(self):
            import threading
            from installed_engine import InstalledSession
            release=threading.Event();entered=threading.Event();calls=[]
            def watch():entered.set();release.wait(2)
            engine=types.SimpleNamespace(_session_dir=root,_finalization_thread=None,_threads=[],
                state='FAILED',_journal=None,_watch_session=watch,_finalization_error=None,
                wait_for_completion=lambda timeout:None)
            session=object.__new__(InstalledSession)
            session.engine=engine;session.source=None;session.motion=None;session.attribution_writer=None
            session.failure='injected prewarm failure';session.policy=types.SimpleNamespace(cleanup_seconds=.01)
            session.models=types.SimpleNamespace(close=lambda:calls.append('models'))
            try:
                with self.assertRaisesRegex(RuntimeError,'still-running workers'):session.close()
                self.assertTrue(entered.is_set());self.assertEqual(calls,[])
            finally:
                release.set();engine._finalization_thread.join(2)
            session.close();self.assertEqual(calls,['models'])

        def test_production_assets_match_pinned_content_addressed_catalog(self):
            import release_authorization as authorization
            from profiles import RuntimeSelection
            base=root/'asset-fixture';(base/'config').mkdir(parents=True)
            models=base/'models';digest='a'*64
            asset=dict(deployment_relative_path='models/asr/encoder.onnx',sha256=digest)
            catalog=[dict(asset,component_id='fixture_encoder',filename='actual-encoder.onnx')]
            contract=dict(models_root=str(models),extra_assets=[])
            for name,value in [('assets.json',catalog),('field_contract.json',contract)]:module.write(base/'config'/name,value)
            manifest=dict(files=[dict(path='config/'+name,sha256=hashlib.sha256((base/'config'/name).read_bytes()).hexdigest())
                for name in ('assets.json','field_contract.json')])
            module.write(base/'RELEASE_MANIFEST.json',manifest)
            descriptor=dict(runtime_document={},runtime_profile=dict(definition=dict(composition=dict(components=dict(asr=dict(assets=[asset]))))))
            path=base/'baseline.json';module.write(path,descriptor)
            pin=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            binding=dict(installed_release=str(base),installed_manifest_sha256=hashlib.sha256((base/'RELEASE_MANIFEST.json').read_bytes()).hexdigest(),
                profiles=dict(baseline=pin),python='pinned-python')
            selection=RuntimeSelection('pyannote','redimnet','saved',None)
            required,_=authorization.required_assets(binding,selection)
            self.assertEqual(required[str(models/digest/'actual-encoder.onnx')],digest)
            self.assertNotIn(str(models/'asr/encoder.onnx'),required)
            catalog_raw=(base/'config/assets.json').read_bytes()
            (base/'config/assets.json').write_bytes(catalog_raw+b' ')
            with self.assertRaisesRegex(ValueError,'catalog changed'):authorization.required_assets(binding,selection)
            (base/'config/assets.json').write_bytes(catalog_raw)
            asset['sha256']='b'*64
            path.write_bytes(module.encoded(descriptor));pin['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError,'differs from pinned'):authorization.required_assets(binding,selection)

        def test_raw_template_requires_source_batch_pin(self):
            import time
            directory=root/'raw-template';directory.mkdir()
            path=directory/'template.json';binding_path=directory/'BINDING.json'
            module.write(binding_path,dict(target=str(directory)))
            value=dict(schema='just-peachy.raw-qualification-template.v1',reviewed=True,duration_seconds=5,
                target=str(directory),binding_sha256=hashlib.sha256(binding_path.read_bytes()).hexdigest(),
                package_manifest_sha256='a'*64,boot_id='fixture',expires_unix=time.time()+60)
            for name in ('installed_source','raw_capture','source_batch'):
                (directory/(name+'.py')).write_bytes(name.encode())
                value[name+'_sha256']=hashlib.sha256(name.encode()).hexdigest()
            args=types.SimpleNamespace(entrypoint='raw_qualification.py',raw_admission_template=str(path),
                binding=str(binding_path),manifest_sha256='a'*64)
            def save():
                path.write_bytes(module.encoded(value));args.raw_admission_template_sha256=hashlib.sha256(path.read_bytes()).hexdigest()
            save()
            with mock.patch.object(module,'identity',return_value=dict(boot_id='fixture')):
                self.assertEqual(module.raw_template(args,dict(target=str(directory))),value)
                del value['source_batch_sha256'];save()
                with self.assertRaisesRegex(ValueError,'module pin changed'):module.raw_template(args,dict(target=str(directory)))

        def test_frozen_build_options_bind_variant_and_batch(self):
            import prepare_package as builder
            path='/home/peachyprototype/JustPeachy/research/nemotron-20260928/live-runtime-tests-20261003/native-threads2-build-01/RUNTIME_VARIANT.json'
            pin='3fdb0a0699e06a0608ca6cf5676676e3416bf291398271ebd3fd9a5bca41bc57'
            options=builder.select_options(None,100,path,pin)
            self.assertEqual(options['native_variants'],dict(chunk52_threads2=dict(path=path,sha256=pin)))
            self.assertEqual(builder.select_options(options),options)
            self.assertIsNone(builder.select_options(None))
            with self.assertRaisesRegex(ValueError,'cannot change'):builder.select_options(options,0)
            with self.assertRaisesRegex(ValueError,'cannot change'):builder.select_options(options,native_variant=path,native_variant_sha256='b'*64)
            with self.assertRaisesRegex(ValueError,'pair'):builder.select_options(None,native_variant=path)
            with self.assertRaises(ValueError):builder.select_options(None,100,'/tmp/unreviewed.so',pin)

        def test_batch_binding_declares_retained_block_geometry(self):
            import prepare_package as builder
            original=dict(device='retained',evidence_dir='old')
            options=builder.select_options(None,100)
            self.assertEqual(builder.live_configuration(original,options),dict(device='retained',evidence_dir=None,block_frames=480))
            self.assertNotIn('block_frames',original)
            self.assertNotIn('block_frames',builder.live_configuration(original,None))
            for frames in (160,480.0,True):
                with self.assertRaisesRegex(ValueError,'480-frame'):builder.live_configuration(dict(original,block_frames=frames),options)

        def test_model_memory_failure_keeps_original_error_and_reaps_sampler(self):
            import threading
            from model_load_trace import ModelLoadTrace
            observed=threading.Event();counter=[]
            def snapshot():
                counter.append(1)
                if len(counter)>1:observed.set()
                return dict(rss_bytes=100,virtual_peak_bytes=700,pss_bytes=80,available_ram_bytes=1600)
            trace=ModelLoadTrace(root/'model-memory.jsonl',snapshot=snapshot,interval=.01)
            failure=RuntimeError('injected unchanged native loader failure')
            def load():
                self.assertTrue(observed.wait(1));raise failure
            try:
                with self.assertRaises(RuntimeError) as caught:trace.call('asr',load)
                self.assertIs(caught.exception,failure);self.assertIsNone(trace.active)
            finally:trace.close()
            rows=[json.loads(line) for line in trace.path.read_text().splitlines()]
            self.assertEqual(rows[0]['event'],'before');self.assertEqual(rows[-1]['event'],'failed')
            self.assertIn('during',[row['event'] for row in rows])
            self.assertEqual(rows[-1]['memory']['virtual_peak_bytes'],700)
            self.assertEqual(rows[-1]['sampling_errors'],[])

        def test_model_memory_capacity_refuses_before_model_call(self):
            from model_load_trace import ModelLoadTrace
            calls=[]
            trace=ModelLoadTrace(root/'model-memory-cap.jsonl',maximum_bytes=4096,snapshot=lambda:dict(pad='x'*5000))
            try:
                with self.assertRaisesRegex(RuntimeError,'finite allocation'):trace.call('asr',lambda:calls.append('loaded'))
                self.assertEqual(calls,[])
            finally:trace.close()

        def test_production_variant_keeps_embedding_and_pins_exact_provenance(self):
            import release_authorization as authorization
            import native_variant
            from profiles import RuntimeSelection
            chosen=RuntimeSelection('nemotron','titanet','saved','chunk52',True).validate()
            chosen['nemotron_profile']='chunk52_threads2'
            selection=types.SimpleNamespace(validate=lambda:chosen)
            path='/home/peachyprototype/JustPeachy/research/nemotron-20260928/live-runtime-tests-20261003/native-threads2-build-01/RUNTIME_VARIANT.json'
            binding=dict(native_variants=dict(chunk52_threads2=dict(path=path,sha256='a'*64)))
            document=dict(embedding_namespace={'onnx_sha256':'b'*64},titanet_manifest='same-manifest',
                nemotron_model='old-model',native_runtime_files=[dict(path='old-library',sha256='c'*64)])
            native=dict(nemotron_model='exact-model',nemotron_model_sha256='d'*64,nemotron_library='exact-library',
                nemotron_library_sha256='e'*64,native_runtime_files=[dict(path='exact-library',sha256='e'*64)],
                streaming_profile='native_cm5_chunk52',native_device=dict(kind='cpu',gpu_index=-1))
            verified=types.SimpleNamespace(document=lambda:native,build_result_sha256='1'*64,
                source_variant_sha256='2'*64,core_sha256='3'*64,component_review_sha256='4'*64)
            with mock.patch.object(native_variant,'verify_native_variant',return_value=verified) as verifier:
                merged,required=authorization.variant_asset_document(binding,selection,document)
                verifier.assert_called_once_with(path,'a'*64,selection)
            self.assertEqual(merged['embedding_namespace'],document['embedding_namespace'])
            self.assertEqual(merged['titanet_manifest'],'same-manifest')
            self.assertEqual(merged['native_runtime_files'],native['native_runtime_files'])
            self.assertEqual(document['nemotron_model'],'old-model')
            self.assertEqual(required[path],'a'*64)
            self.assertEqual(required[str(Path(path).parent/'BUILD_RESULT.json')],'1'*64)
            self.assertEqual(required[str(native_variant.COMPONENT_REVIEW)],'4'*64)
            with self.assertRaisesRegex(ValueError,'descriptor binding'):authorization.variant_asset_document({},selection,document)

        def test_motion_closes_while_stuck_speech_model_remains_owned(self):
            from installed_engine import InstalledSession
            session=object.__new__(InstalledSession);calls=[]
            session.source=types.SimpleNamespace(stop=lambda:calls.append('source-stop'))
            session.motion=types.SimpleNamespace(close=lambda:calls.append('imu-close') or True,
                thread=types.SimpleNamespace(is_alive=lambda:False))
            session.models=types.SimpleNamespace(close=lambda:calls.append('model-close'))
            session.engine=types.SimpleNamespace(_finalization_thread=None,
                _threads=[types.SimpleNamespace(name='owned-native-lane',is_alive=lambda:True)])
            session.failure=None;session.attribution_writer=None
            with self.assertRaises(RuntimeError):session.close()
            self.assertEqual(calls,['source-stop','imu-close'])
            self.assertIsNone(session.motion)

    suite=(unittest.TestSuite(Checks(name) for name in args.checks) if args.checks
           else unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    receipt=dict(evidence=str(root),tests=result.testsRun,errors=len(result.errors),failures=len(result.failures),
        native_executed=False,systemd_executed=False)
    module.write(root/'TEST_RESULT.json',receipt)
    print(module.encoded(receipt).decode())
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':
    raise SystemExit(main())
