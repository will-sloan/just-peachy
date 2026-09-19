"""Independent source/fixture review; see README_TEST_S6C_LONG_B36_DIAGNOSTICS_ROOT_V1.md."""
from __future__ import annotations
import ast, hashlib, importlib.util, json, sys, tempfile
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
TARGET=HERE/'s6c_long_b36_diagnostics_v1.py'
PIN='f84dd4d2a45969db7b74acc94ec8a8a0b7e1ace396da205bfa2cf870835650a2'

def main():
    raw=TARGET.read_bytes();assert hashlib.sha256(raw).hexdigest()==PIN
    spec=importlib.util.spec_from_file_location('_b36_long_root_review',TARGET)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    rows,proof=m.checks();checks=[]
    def ok(name,fn):fn();checks.append(dict(name=name,status='PASS'))
    def no(name,fn):
        try:fn()
        except (ValueError,KeyError,TypeError,AssertionError):checks.append(dict(name=name,status='PASS_REJECTED'));return
        raise AssertionError(name+' accepted')
    api,pure=m.pure_api();original=ast.parse((HERE/'s6c_historical_paced_analysis_v1.py').read_bytes())
    nodes={n.name:n for n in original.body if isinstance(n,ast.FunctionDef)}
    for n in m.PURE_NAMES:
        assert pure[n]==hashlib.sha256(ast.dump(nodes[n],include_attributes=False).encode()).hexdigest()
    ok('exact five original observation functions',lambda:m.require(len(pure)==5 and pure==proof,'AST'))
    ok('no imported native APP',lambda:m.require(not any(k.startswith('edge_speech_pipeline') for k in sys.modules),'APP'))
    job=dict(input=dict(path=str(HERE/'synthetic_only.wav')),assets=[dict(component_id='fixture',sha256='a'*64)],profile=dict(profile_id='B36'))
    telemetry=dict(source_duration_sec=m.DURATION,asr_cursor_sec=m.DURATION,audio_frames_dropped=0,portaudio_input_overflows=0,raw_capture_reserve_failures=0,
        scheduler=dict(schema_version='edge-scheduler-snapshot.v2',closed=True,pending_events=0,watermarks=dict(asr='closed',speaker='closed')))
    summary=dict(state='COMPLETED',assets=[dict(component_id='fixture',sha256='a'*64)],research=dict(profile=job['profile'],telemetry_sha256=None,effective_config=dict(input_gain=1.)),telemetry=telemetry)
    emission=dict(source_started=dict(payload=dict(mode='wav',path=job['input']['path'],pipeline_sample_rate=16000,channels=1)))
    ok('actual complete original summary scope',lambda:m.validate_summary(summary,dict(summary=summary),job,emission))
    for key,value in [('audio_frames_dropped',1),('portaudio_input_overflows',True),('asr_cursor_sec',m.DURATION-.1)]:
        v=deepcopy(summary);v['telemetry'][key]=value
        no('summary '+key,lambda v=v:m.validate_summary(v,dict(summary=v),job,emission))
    for key,value in [('closed',False),('pending_events',1),('watermarks',dict(asr='closed',speaker='open'))]:
        v=deepcopy(summary);v['telemetry']['scheduler'][key]=value
        no('scheduler '+key,lambda v=v:m.validate_summary(v,dict(summary=v),job,emission))
    v=deepcopy(summary);v['research']['telemetry_sha256']='unexpected'
    no('unexpected historical cue',lambda:m.validate_summary(v,dict(summary=v),job,emission))
    v=deepcopy(emission);v['source_started']['payload']['path']=str(HERE/'wrong.wav')
    no('source path substitution',lambda:m.validate_summary(summary,dict(summary=summary),job,v))
    with tempfile.TemporaryDirectory() as td:
        td=Path(td);live=td/'LIVE.json';rejected=td/'bad.json';rejected.write_bytes(b'{bad')
        bb=m.binding(rejected,b'{bad')
        ev=[dict(event='optional_live_json_missing',sample_value=None,path=str(live)),dict(event='live_snapshot_failed',raw_binding=bb)]
        snap=dict(live_calls=2,live_calls_by_path={str(live):2},missing_live_json_calls=1,missing_live_json_by_path={str(live):1},failed_calls=1,captured_snapshots=1,captured_bytes=4)
        reads=[]
        def read(b):reads.append(b);return m.read_small(b['path'],b)
        ok('separate observer read and periodic denominators',lambda:m.require(m.observer(ev,snap,live,3,read)['event_counts']['optional_live_json_missing']==1,'observer'))
        assert reads==[bb]
        no('observer calls exceed actual periodic rows',lambda:m.observer(ev,snap,live,1,read))
        no('retained anomaly bytes mismatch',lambda:m.observer(ev,snap|dict(captured_bytes=3),live,3,read))
        wrong=deepcopy(snap);wrong['live_calls_by_path']={str(td/'other.json'):2}
        no('unrelated observed path',lambda:m.observer(ev,wrong,live,3,read))
        with patch.object(m,'REPORT',td):
            (td/'PACED_QUIET_OWNER.json').write_text('{}')
            no('any active quiet lease refuses reporting',m.no_quiet)
    ts=lambda sec:f'2026-09-10T00:00:{sec:02d}+00:00'
    e=lambda kind,wall,cursor,payload:dict(event_type=kind,wall_time_utc=ts(wall),source_time_sec=cursor,payload=payload)
    events=[e('source_started',10,0.,{}),e('transcript_partial',11,5.,dict(text='',speaker='Speaker_1')),e('research_asr_observation',9,4.,{}),e('session_completed',12,6.,{})]
    display=[dict(event_type='transcript_partial',source_time_sec=5.,emitted_wall_time_utc=ts(11),payload=dict(text='',speaker='Speaker_1'))]
    r=api['emitted_observations'](events,display,dict(source_started_wall_time_utc=ts(10)))
    ok('all event positions preserve reverse clock and negative source offset',lambda:m.require(r['wall_order_reversals']==[3] and r['rows'][0]['event_line']==2 and r['rows'][0]['emission_minus_source_cursor_sec']==-4. and r['rows'][0]['payload']['text']=='','clock'))
    samples=[dict(phase='periodic',elapsed_sec=0.,tree=dict(processes=[dict(pid=1,creation_time=2.,cpu_seconds=4.)],tree_complete=True),live=None),dict(phase='periodic',elapsed_sec=2.,tree=dict(processes=[dict(pid=1,creation_time=2.,cpu_seconds=5.)],tree_complete=False),live=dict(telemetry=dict(source_duration_sec=10.,asr_cursor_sec=8.)))]
    p=api['process_observations'](samples,{(1,2.)})
    ok('CPU lifetime and missing telemetry preserved separately',lambda:m.require(p['sampled_cpu_counter_sum_sec']==5. and p['backlog']['asr_cursor_sec']['missing']==1 and p['backlog']['speaker_cursor_sec']['missing']==2 and p['incomplete_tree_samples']==1,'process'))
    no('unowned sample cannot be admitted',lambda:api['process_observations'](samples,{(2,3.)}))
    no('backward monotonic process sampling rejected',lambda:api['process_observations'](list(reversed(samples)),{(1,2.)}))
    owner_sources=m.own_sources()
    out=Path(sys.argv[1]).resolve()
    receipt=dict(status='PASS_INDEPENDENT_SOURCE_AND_SYNTHETIC_REVIEW',created_utc=m.utc(),target_sha256=PIN,owner_check_count=len(rows),independent_check_count=len(checks),checks=checks,source_bindings=owner_sources,
        reviewer_source=m.binding(__file__,Path(__file__).read_bytes()),reviewer_readme=m.binding(HERE/'README_TEST_S6C_LONG_B36_DIAGNOSTICS_ROOT_V1.md',(HERE/'README_TEST_S6C_LONG_B36_DIAGNOSTICS_ROOT_V1.md').read_bytes()),pure_function_ast_sha256=pure,new_neural_calls=0,native_sessions_read=0,actual_metadata_admission=False,pcm_or_models_read=False,
        scope='Independent source reading against original B36 native output construction, exact pure AST preservation, owner fixtures plus distinct summary/observer/clock/process negatives. No claim of completed continuous execution or actual output parity before a session closes.')
    print(json.dumps(m.save(out,receipt)))

if __name__=='__main__':main()
