"""Synthetic closed-input admission checks; README_S6D_NATIVE176_SCORING_INPUTS_V1.md."""
import argparse
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
import traceback
import wave


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.drive.upper()!='G:' or a.output.exists():raise ValueError('Fresh G fixture output required')
    a.output.mkdir(parents=True);path=Path(__file__).with_name('s6d_native176_scoring_inputs_v1.py');spec=importlib.util.spec_from_file_location('native176_builder_tests',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    results=[]
    def check(name,call):
        try:call();results.append(dict(name=name,status='PASS'))
        except BaseException:results.append(dict(name=name,status='FAIL',error=traceback.format_exc()))
    def reject(call):
        try:call()
        except (ValueError,PermissionError):return
        raise AssertionError('Expected fail-closed rejection')
    queue=dict(run_id='synthetic',jobs=[dict(job_id='one'),dict(job_id='two')]);qr=dict(path='synthetic_queue',bytes=1,sha256='a'*64)
    def closed():
        checkpoint=dict(run_id='synthetic',queue_sha256=qr['sha256'],status='FINISH',active=None,completed={j:dict(status='DECLARED_ARTIFACTS_VERIFIED',exit_code=0,identity=dict(run_id='synthetic',job_id=j,child_run_id='child_'+j,pid=100+i,creation_time=10.+i)) for i,j in enumerate(('one','two'))})
        lock=dict(run_id='synthetic',queue_sha256=qr['sha256'],owner_nonce='a'*32,pid=90,creation_time=9.)
        closure=dict(run_id='synthetic',result=dict(run_id='synthetic',action='FINISH',done=2,total=2),owner_lock='RELEASED_TO_IMMUTABLE_CLOSED_RECEIPT',hardware_restoration_unresolved=False,keep_awake=dict(requested=True,owned=True,restored=True,status='RESTORED'),payload_census_closure=dict(closed=True,snapshot=dict(running=False,has_complete=True,pending=False,error=None,violation_latched=False)))
        return checkpoint,lock,closure,dict(pid=90,creation_time=9.)
    check('complete_synthetic_closure_passes',lambda:m.validate_closed(queue,qr,*closed()))
    def different_orders():
        rows=[dict(job_id='two'),dict(job_id='one')];joined=m.matched_queue_rows(rows,queue['jobs'])
        assert [r['job_id'] for r,j in joined]==['two','one'] and all(r['job_id']==j['job_id'] for r,j in joined)
        reject(lambda:m.matched_queue_rows(rows,[dict(job_id='one'),dict(job_id='one')]))
    check('distinct_frozen_scoring_execution_orders_join_by_ID',different_orders)
    for name,mutation in [
        ('active_job',lambda c:c[0].update(active=dict(job_id='two'))),
        ('missing_completion',lambda c:c[0]['completed'].pop('two')),
        ('WAIT_checkpoint',lambda c:c[0].update(status='WAIT')),
        ('unfinished_supervisor',lambda c:c[2]['result'].update(action='WAIT')),
        ('keepawake_failure',lambda c:c[2]['keep_awake'].update(restored=False)),
        ('unresolved_lease',lambda c:c[2].update(hardware_restoration_unresolved=True)),
        ('census_alive',lambda c:c[2]['payload_census_closure']['snapshot'].update(running=True)),
        ('census_error',lambda c:c[2]['payload_census_closure']['snapshot'].update(error='denied')),
        ('wrong_launch_creation',lambda c:c[3].update(creation_time=99.)),
        ('nonfinite_child_creation',lambda c:c[0]['completed']['one']['identity'].update(creation_time=float('nan'))),
    ]:
        def adverse(mutation=mutation):
            value=closed();mutation(value);reject(lambda:m.validate_closed(queue,qr,*value))
        check(name+'_blocks_approval',adverse)
    class Missing(Exception):pass
    def provider(value=None,error=None):
        def process(pid):
            if error:raise error('fixture')
            return SimpleNamespace(create_time=lambda:value)
        return SimpleNamespace(Process=process,NoSuchProcess=Missing)
    ids=[dict(role='one',pid=100,creation_time=10.)]
    check('actual_same_instance_cannot_be_absent',lambda:reject(lambda:m.prove_absent(ids,provider(10.))))
    check('reused_pid_distinguished',lambda:assert_equal(m.prove_absent(ids,provider(20.))['rows'][0]['status'],'ORIGINAL_INSTANCE_ABSENT_PID_REUSED'))
    check('missing_pid_is_absent',lambda:assert_equal(m.prove_absent(ids,provider(error=Missing))['rows'][0]['status'],'ORIGINAL_INSTANCE_ABSENT_PID_NOT_FOUND'))
    check('access_error_never_absence',lambda:reject(lambda:m.prove_absent(ids,provider(error=PermissionError))))
    def cached():
        f=a.output/'cache.json';m.save(f,dict(value=1));cache=m.Cache();ref=cache.binding(f);cache.check(ref);cache.load(f);assert cache.hash_reads==1
        f.write_text('{"value":2}\n',encoding='utf-8');reject(lambda:cache.binding(f))
    check('unique_hash_cache_detects_changed_input',cached)
    def pcm():
        f=a.output/'tiny.wav'
        with wave.open(str(f),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(bytes(32))
        cache=m.Cache();ref=cache.binding(f);cache.check(ref);assert cache.hash_reads==1 and cache.pcm[str(f.resolve())]['frames']==16
    check('WAV_and_PCM_share_one_file_read',pcm)
    none=dict(gallery_condition='NONE',manifest=None,profiles=[],available_identities=[],intended_identities=[])
    check('exact_NONE_gallery_control',lambda:assert_equal(m.gallery_row(None,[]),none))
    gallery=dict(path='fixture_gallery',bytes=1,sha256='b'*64);row=dict(manifest=gallery,profiles=[],fixture_only=True)
    check('original_bound_gallery_row',lambda:assert_equal(m.gallery_row(gallery,[row]),row))
    check('ambiguous_gallery_map_blocks',lambda:reject(lambda:m.gallery_row(gallery,[row,row])))
    def no_admission():
        f=a.output/'not_approved.json';m.save(f,dict(schema='s6d-native176-scoring-build-admission.v1',status='PROPOSED_ONLY'));cache=m.Cache();reject(lambda:m.build(f,cache.binding(f)['sha256']))
    check('unapproved_build_stops_before_state_or_process_read',no_admission)
    cache=m.Cache();prospective=cache.load(m.PROSPECTIVE);runner,evidence,scorer=m.pure_apis(cache,prospective)
    def old_completion():
        f=a.output/'COMPLETE.json';m.save(f,dict(run_id='synthetic',job_id='one',child_run_id='c',status='COMPLETE'))
        job=dict(completion_path=str(f),expected_artifacts=[dict(path=str(f),format='json',min_bytes=1,expected_fields={'status':'COMPLETE'})]);identity=dict(run_id='synthetic',job_id='one',child_run_id='c')
        assert runner['validate_completion'](job,identity)['completion']==cache.binding(f)
        reject(lambda:runner['validate_completion'](job,dict(identity,child_run_id='wrong')))
    check('unchanged_V4_completion_identity_predicates',old_completion)
    def dispatch():
        events=[dict(event_type='source_started',payload=dict(expected_samples=16,pipeline_sample_rate=16000)),dict(event_type='research_asr_tail_dispatch',payload=dict(source_start_sec=0.,source_end_sec=.001,samples=16)),dict(event_type='research_asr_drain',payload=dict(source_end_sec=.001,padding_is_observed_audio=False,synthetic_right_padding_sec=.66)),*[dict(event_type='research_scheduler_watermark',payload=dict(lane_closed=True,lane=lane)) for lane in ('asr','speaker')],dict(event_type='session_completed',payload={})]
        f=a.output/'dispatch.jsonl';f.write_text(''.join(json.dumps(x)+'\n' for x in events),encoding='utf-8');before=cache.hash_reads;proof=cache.dispatch(f,16,evidence['validate_dispatch']);cache.binding(f);assert proof['frames']==16 and cache.hash_reads==before+1
        reject(lambda:evidence['validate_dispatch'](events[:-1],16))
    check('unchanged_dispatch_guard_and_one_pass_hash',dispatch)
    source=m.Cache().binding(path);receipt=dict(status='PASS' if all(r['status']=='PASS' for r in results) else 'FAIL',source=source,fixture=m.Cache().binding(__file__),tests=results,passed=sum(r['status']=='PASS' for r in results),total=len(results),actual_native_outputs_read=False,actual_scoring=False,actual_PID_checks=False,actual_models=0,actual_devices=0,root_approval_created=False)
    m.save(a.output/'RECEIPT.json',receipt);print(json.dumps(dict(status=receipt['status'],passed=receipt['passed'],total=receipt['total'],receipt=m.Cache().binding(a.output/'RECEIPT.json'))));return 0 if receipt['status']=='PASS' else 1


def assert_equal(a,b):assert a==b,(a,b)
if __name__=='__main__':raise SystemExit(main())
