"""Bounded native protocol fixtures; see README_S6D_NATIVE_CONFIRMATION_PROTOCOL_V2.md."""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import wave
import s6d_runner_native_confirmation_v2 as W
import s6d_native_evidence_v1 as E
import s6d_native_evidence_checks_v1 as G

HELPER_SOURCE='''"""Synthetic protocol fixture only; see adjacent README_SYNTHETIC_HELPER.md."""
import json,os
from pathlib import Path
def run_one(manifest_path,job_id,checkpoint=None):
    m=json.loads(Path(manifest_path).read_text());j=next(x for x in m['jobs'] if x['job_id']==job_id)
    o=Path(j['output']);s=o/'sessions'/'synthetic';s.mkdir(parents=True)
    r=json.loads(json.dumps(j['fixture']['result']));r.update(job=j,manifest=j['fixture']['manifest_binding'],helper=m['helper'],session_dir=str(s),pid=os.getpid(),process_create_time=j['fixture']['creation_time'])
    class Engine:
        state='COMPLETED'
        def stop(self):pass
    if checkpoint:checkpoint(engine=Engine(),telemetry=r['telemetry'],job=j,output=o)
    f=json.loads(json.dumps(j['fixture']['final']));samples=16000
    if j['fixture']['mode']=='prefix':
        samples=8000;r['telemetry'].update(source_duration_sec=.5,asr_cursor_sec=.5,speaker_cursor_sec=.5,paired_audio_samples=8000,identity_audio_samples=8000)
        f.update(source_samples=8000,identity_samples=8000)
    (s/'audio_spool.pcm16').write_bytes(bytes(samples*2));(s/'identity_audio_spool.pcm16').write_bytes(bytes(samples*2))
    (s/'session_finalization_v3.json').write_text(json.dumps(f))
    rows=j['fixture']['events'];(o/'consumer_events.jsonl').write_text(''.join(json.dumps(x)+'\\n' for x in rows))
    r['manifest']=dict(path=str(Path(manifest_path).resolve()),bytes=Path(manifest_path).stat().st_size,sha256=__import__('hashlib').sha256(Path(manifest_path).read_bytes()).hexdigest())
    (o/'RESULT.json').write_text(json.dumps(r));return r
'''


def put(path,value):
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False)
    return E.binding(path)


class FakeProcess:
    def __init__(self):self.cpus=list(range(16));self.pid=PID
    def create_time(self):return CREATED
    def cpu_affinity(self,value=None):
        if value is not None:self.cpus=list(value)
        return list(self.cpus)


class Checks(unittest.TestCase):
    def setup_job(self,mode='normal'):
        d=OUT/self._testMethodName;d.mkdir();audio=d/'synthetic_zero.wav'
        with wave.open(str(audio),'wb') as f:f.setparams((1,2,16000,0,'NONE',''));f.writeframes(bytes(32000))
        helper=d/'synthetic_native_helper.py';helper.write_text(HELPER_SOURCE,encoding='utf-8')
        (d/'README_SYNTHETIC_HELPER.md').write_text('Synthetic fixture helper: no models, UI, devices or actual native session. Inputs are fixture-only manifest JSON and job ID; outputs are one second of zero PCM journals, fake complete/prefix telemetry and JSON receipts. Do not invoke directly; run the maintained protocol fixture command in README_S6D_NATIVE_CONFIRMATION_PROTOCOL_V2.md. This is protocol validation data, never scientific evidence.\n',encoding='utf-8')
        r,j,f,proofs,closure=G.good();r.pop('job');j.update(job_id='SYNTHETIC',expected_identity_frames=16000,audio=E.binding(audio),
            audio_pcm_sha256=hashlib.sha256(bytes(32000)).hexdigest(),settings=None,gallery=None,output=str(d/'native'),
            fixture=dict(mode=mode,result=r,final=f,events=G.dispatch(),creation_time=CREATED,manifest_binding={}))
        m=dict(schema='s6d-native-pilot.v1',jobs=[j],helper=E.binding(helper),assets=[],execution_files=[],support_files=[],
            evidence_helper=E.binding(E.__file__),protocol_sources=dict(runner=W.binding(W.RUNNER_PATH),evidence=E.binding(E.__file__)),
            protocol_wrapper=W.binding(W.__file__),limits=dict(cpu_affinity=[12,13,14,15]))
        mb=put(d/'MANIFEST.json',m)
        env=dict(S6D_RUN_ID='20260913T195357Z',S6D_JOB_ID='SYNTHETIC',S6D_CHILD_RUN_ID='fixture',
                 S6D_HEARTBEAT_PATH=str(d/'HEARTBEAT.json'),S6D_COMPLETION_PATH=str(d/'COMPLETION.json'),S6D_STOP_REQUEST_PATH=str(d/'STOP.json'))
        return d,m,mb,env

    def execute_job(self,mode='normal',mutator=None):
        d,m,mb,env=self.setup_job(mode)
        if mutator:
            mutator(m);mb=put(d/'CHANGED_MANIFEST.json',m)
        with patch.dict(os.environ,env),patch.object(W.psutil,'Process',FakeProcess):
            result=W.execute(m['helper']['path'],m['helper']['sha256'],mb['path'],mb['sha256'],'SYNTHETIC',heartbeat_interval=.1)
        return d,result

    def test_full_source_positive_control(self):
        d,result=self.execute_job();self.assertEqual(result['status'],'COMPLETE')
        self.assertTrue(result['full_source_evidence_validated']);self.assertTrue(result['protocol_observer_closed'])
        self.assertEqual(result['protocol_observer_errors'],[]);self.assertEqual(result['affinity_verified'],[12,13,14,15])
        self.assertTrue((d/'COMPLETION.json').exists());self.assertEqual(json.loads((d/'native'/'FULL_SOURCE_AUDIT.json').read_text())['status'],'PASS_OFFLINE_EVIDENCE')

    def test_stopped_prefix_inner_complete_is_rejected(self):
        d,result=self.execute_job('prefix');self.assertEqual(result['status'],'FAILED');self.assertFalse((d/'COMPLETION.json').exists())
        self.assertEqual(json.loads((d/'native'/'RESULT.json').read_text())['status'],'COMPLETE')
        self.assertEqual(json.loads((d/'native'/'FULL_SOURCE_AUDIT.json').read_text())['status'],'REJECTED')

    def test_missing_pcm_predeclaration_prevents_native_initialize(self):
        with self.assertRaisesRegex(ValueError,'PCM SHA256'):self.execute_job(mutator=lambda m:m['jobs'][0].pop('audio_pcm_sha256'))
        self.assertFalse((OUT/self._testMethodName/'native').exists())

    def test_actual_pcm_mismatch_prevents_native_initialize(self):
        d,result=self.execute_job(mutator=lambda m:m['jobs'][0].update(audio_pcm_sha256='b'*64))
        self.assertEqual(result['status'],'FAILED');self.assertFalse((d/'native').exists());self.assertFalse((d/'COMPLETION.json').exists())

    def test_unavailable_or_failed_affinity_rejected(self):
        class P:
            def cpu_affinity(self,value=None):return [0,1,2,3]
        with self.assertRaises(ValueError):W.admit_affinity(P(),dict(limits=dict(cpu_affinity=[12,13,14,15])))
        class Readback:
            count=0
            def cpu_affinity(self,value=None):
                self.count+=1
                return list(range(16)) if self.count==1 else [12]
        with self.assertRaisesRegex(ValueError,'readback'):W.admit_affinity(Readback(),dict(limits=dict(cpu_affinity=[12,13,14,15])))

    def test_late_observer_error_prevents_completion(self):
        close=W.ProtocolBridge.close
        def bad_close(bridge):close(bridge);bridge.observer_errors.append('synthetic late observer failure')
        with patch.object(W.ProtocolBridge,'close',bad_close):d,result=self.execute_job()
        self.assertEqual(result['status'],'FAILED');self.assertFalse((d/'COMPLETION.json').exists())

    def test_matching_stop_at_final_publish_prevents_completion(self):
        publish=W.publish_exclusive
        def stop_then_publish(path,value,checkpoint):
            if Path(path).name=='COMPLETION.json':
                put(Path(os.environ['S6D_STOP_REQUEST_PATH']),{k:value[k] for k in ('run_id','job_id','child_run_id','pid','creation_time')})
            return publish(path,value,checkpoint)
        with patch.object(W,'publish_exclusive',stop_then_publish):d,result=self.execute_job()
        self.assertEqual(result['status'],'FAILED');self.assertTrue(result['stop_requested']);self.assertFalse((d/'COMPLETION.json').exists())

    def test_foreign_stop_ignored_but_incomplete_stop_blocks(self):
        d=OUT/self._testMethodName;d.mkdir();owner=dict(run_id='r',job_id='j',child_run_id='c',pid=PID,creation_time=CREATED)
        stop=d/'STOP.json';put(stop,dict(owner,pid=PID+1))
        bridge=W.ProtocolBridge(owner,d/'HB.json',stop,dict(job_id='j',output=str(d),audio_duration_sec=1.))
        bridge.guard();stop.write_text('{')
        with self.assertRaises(ValueError):bridge.guard()

    def test_persistent_completion_replace_failure_leaves_no_completion(self):
        d=OUT/self._testMethodName;d.mkdir();path=d/'COMPLETION.json'
        with patch.object(W.os,'rename',side_effect=PermissionError('synthetic sharing failure')),patch.object(W.time,'sleep',lambda t:None):
            with self.assertRaises(PermissionError):W.publish_exclusive(path,dict(status='COMPLETE'),lambda:None)
        self.assertFalse(path.exists());self.assertTrue(path.with_name('.COMPLETION.json.pending').exists())

    def tk_rows(self):
        d=OUT/self._testMethodName;d.mkdir();s=d/'sessions'/'S';s.mkdir(parents=True)
        rows=[dict(event_type='source_started',payload=dict(publication_sequence=1,pilot_publication_monotonic_sec=100.)),
              dict(event_type='s6d_text_ready',payload=dict(publication_sequence=2,pilot_publication_monotonic_sec=101.,utterance_id='u')),
              dict(event_type='s6d_display',payload=dict(publication_sequence=3,pilot_publication_monotonic_sec=101.01,utterance_id='u'))]
        (d/'consumer_events.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
        sha=hashlib.sha256(b''.join(json.dumps(r,sort_keys=True,separators=(',',':'),allow_nan=False).encode()+b'\n' for r in rows)).hexdigest()
        cb=put(d/'OWNED_RESOURCE_CLOSURE.json',dict(resources_closed=True,cleanup_errors=[],setup_or_loop_error=None,root_destroyed=True,consumer_closed=True,gallery_spy_restored=True,render_files_closed=True,startup_thread_alive=False,observer_thread_alive=False))
        inbox=POLICY.EventInbox(8)
        for row in rows:inbox.put(SimpleNamespace(event_type=row['event_type'],payload=dict(row['payload'])))
        while not inbox.empty():inbox.get()
        q=inbox.snapshot();self.assertNotIn('accepted',q)
        result=dict(owned_resource_closure=cb,gui_tested=True,session_dir=str(s),source_event_count=3,source_event_order_sha256=sha,native_T0_semantic_comparisons=1,
                    views=[dict(name='T0',input_count=3,input_order_sha256=sha,consumer_closed=True,forwarded=3,queue=q)])
        job=dict(output=str(d),views=[dict(name='T0')]);p=d/'views'/'T0';p.mkdir(parents=True)
        payload=dict(session_id='S',utterance_id='u',source_native_publication_sequence=2,source_native_publication_monotonic_sec=101.,causal_view_input_count=2)
        row=dict(payload,view_id='T0',widget_text='Alice: hello',widget_text_sha256=hashlib.sha256(b'Alice: hello').hexdigest(),
                 source_started_monotonic_sec=100.,display_payload=payload,event_publication_monotonic_sec=101.1,
                 widget_update_started_monotonic_sec=101.2,widget_update_finished_monotonic_sec=101.3,actual_callback_monotonic_sec=101.4)
        render=p/'s6d_gui_render.jsonl';render.write_text(json.dumps(row)+'\n');return result,job,render,row

    def test_bound_tk_positive_control(self):
        result,job,_,_=self.tk_rows();self.assertEqual(W.tk_evidence(result,job,E)['views'],1)

    def test_tk_wrong_causal_trigger_rejected(self):
        result,job,render,row=self.tk_rows();row['causal_view_input_count']=99;render.write_text(json.dumps(row)+'\n')
        with self.assertRaisesRegex(ValueError,'trigger'):W.tk_evidence(result,job,E)

    def test_tk_undrained_view_rejected(self):
        result,job,_,_=self.tk_rows();result['views'][0]['queue']['depth']=1
        with self.assertRaisesRegex(ValueError,'drain'):W.tk_evidence(result,job,E)

    def test_tk_empty_render_journal_rejected(self):
        result,job,render,_=self.tk_rows();render.write_text('')
        with self.assertRaisesRegex(ValueError,'Truncated'):W.tk_evidence(result,job,E)

    def test_tk_unrelated_utterance_trigger_rejected(self):
        result,job,render,row=self.tk_rows();row['display_payload']['utterance_id']='other';render.write_text(json.dumps(row)+'\n')
        with self.assertRaisesRegex(ValueError,'trigger'):W.tk_evidence(result,job,E)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();OUT=a.output.resolve()
    if OUT.drive.upper()!='G:':raise ValueError('All fixture output must stay on G')
    OUT.mkdir(parents=True,exist_ok=False);PID=os.getpid();CREATED=W.psutil.Process().create_time()
    policy_path=W.RUNNER_PATH.parents[2]/'source_epochs/application_direction_gui_v3/edge_speech_pipeline/research_s6d.py'
    POLICY=W.import_exact(policy_path,'959fbdb407ff650b84962f4f2773254074698ef0224668b4812891d3a8d98218','confirmation_fixture_actual_policy')
    with (OUT/'TESTS.log').open('x',encoding='utf-8') as f:r=unittest.TextTestRunner(stream=f,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    receipt=dict(status='PASS' if r.wasSuccessful() else 'FAIL',tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),
                 wrapper=E.binding(W.__file__),fixture=E.binding(__file__),runner=E.binding(W.RUNNER_PATH),evidence=E.binding(E.__file__),actual_view_inbox_source=E.binding(policy_path),log=E.binding(OUT/'TESTS.log'),
                 actual_native_runs=0,model_calls=0,ui_calls=0,device_calls=0,actual_affinity_changes=0,synthetic_protocol_only=True)
    put(OUT/'RECEIPT.json',receipt);print(json.dumps(receipt));raise SystemExit(not r.wasSuccessful())
