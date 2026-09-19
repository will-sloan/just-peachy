"""No-device V4 capture/owner fixtures; README_S6D_CAPTURE_V4.md."""
from __future__ import annotations
import argparse
import ast
import json
import itertools
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import wave
import numpy as np
import s6d_capture_transport as T
import s6d_capture_owner_v4 as O


def rejected(fn):
    try:fn()
    except (ValueError,RuntimeError,AssertionError):return True
    return False


def checks():
    result=T.checks()['checks'];result=dict(result)
    event=threading.Event();event.set()
    class ForbiddenPath:
        def exists(self):raise AssertionError('Set event must short-circuit failed file I/O')
    result['shared_stop_event_precedes_file_IO']=O.stop_requested(ForbiddenPath(),event) is True
    event.clear()
    with tempfile.TemporaryDirectory() as td:
        result['clear_event_and_missing_file_no_stop']=not O.stop_requested(Path(td)/'missing',event)
    result['new_attempt_finite']=rejected(lambda:O.check_budget({'passes':[]},float('nan')))
    result['duration_ceiling']=rejected(lambda:O.check_budget({'passes':[]},961))
    result['failed_attempts_count']=rejected(lambda:O.check_budget({'passes':[dict(status='FAIL',charged_playback_s=1)]*480},1))
    result['failed_seconds_count']=rejected(lambda:O.check_budget({'passes':[dict(status='FAIL',charged_playback_s=21599)]},2))
    result['unresolved_started_blocks']=rejected(lambda:O.check_budget({'passes':[dict(status='STARTED',charged_playback_s=1)]},1))
    result['path_escape_rejected']=rejected(lambda:O.contained(Path('C:/fixture'),Path('C:/outside')))
    result['clip_before_integer_overflow']=rejected(lambda:T.quantize(np.full((100,4),1e300)))
    guarded,original=T.guarded_input(np.full((160,4),.05))
    result['guard_preserves_original_counts']=np.array_equal(guarded[16000:16160],original) and not np.any(guarded[:16000]) and not np.any(guarded[16160:])
    result['900_second_continuous_charge_includes_guards_padding']=T.timing(900)['charged_playback_seconds']==(904*48000+16383)/48000
    result['source_fractional_frame_rejected']=rejected(lambda:T.timing(.00001))
    policy=dict(schema='s6d-audio-acceptance.v1',raw_gain=1.,max_rail_samples_per_stream=0,rail_exceedance_action='LIMITED',missing_required_payload_action='LIMITED')
    leveldata=np.ones((100,6),np.int32)*100;leveldata[0,1]=8388606
    level=T.audio_gate(T.processed_qc(leveldata,'P_MAIN6'),policy,['auto_asr_raw','auto_pp_raw'])
    result['rail_is_stream_limited_no_gain_change']=level['status']=='LIMITED' and level['limited_streams']==['auto_pp_raw'] and not level['gain_changed']
    leveldata=np.zeros((100,6),np.int32);leveldata[:,0:2]=100
    result['focused_silence_not_automatic_drop']=T.audio_gate(T.processed_qc(leveldata,'P_MAIN6'),policy,['auto_asr_raw','auto_pp_raw'])['status']=='PASS_LEVEL_SCREEN'
    result['missing_required_auto_payload_limited']=T.audio_gate(T.processed_qc(np.zeros((100,6),np.int32),'P_MAIN6'),policy,['auto_asr_raw','auto_pp_raw'])['limited_streams']==['auto_asr_raw','auto_pp_raw']
    core_path=O.ROOT/'measurement_app/core.py'
    core_tree=ast.parse(core_path.read_text(encoding='utf-8-sig'))
    decoder_node=next(n for n in core_tree.body if isinstance(n,ast.FunctionDef) and n.name=='decode_packed')
    # Compile only the exact pure decoder AST; importing the application would
    # initialize PortAudio. No source edits or alternate decoder implementation.
    namespace={'np':np};exec(compile(ast.Module(body=[decoder_node],type_ignores=[]),str(core_path),'exec'),namespace)
    tagged=np.column_stack([np.arange(1000,dtype=np.int32)*2+i*2002 for i in range(6)])
    decoded,qc=namespace['decode_packed'](T.pack(tagged),24)
    result['actual_preserved_decoder_slot_order']=np.array_equal(decoded,tagged) and qc['marker_error_count']==0
    corrupted=T.pack(tagged);corrupted[400,0]^=1
    result['actual_decoder_flags_marker_corruption']=namespace['decode_packed'](corrupted,24)[1]['marker_error_count']>0
    with tempfile.TemporaryDirectory(prefix='s6d_capture_fixtures_') as tmp:
        temp=Path(tmp);report=temp/'report';report.mkdir()
        folder=report/'hardware_batches/b1';folder.mkdir(parents=True)
        O.save(folder/'owner_acquired.json',dict(pid=0,fixture=True),True)
        result['exited_pid_does_not_prove_restore']=rejected(lambda:O.prior_closure(report))
        O.save(folder/'restoration.json',dict(status='PASS',exact_recorded_configuration_match=True,telemetry_process_closed=True),True)
        result['unbound_restore_rejected']=rejected(lambda:O.prior_closure(report))
        O.save(report/'physical_ledger.json',dict(passes=[],batches={'b1':dict(owner=T.binding(folder/'owner_acquired.json'),restoration=T.binding(folder/'restoration.json'))}))
        result['exact_bound_restore_accepted']=O.prior_closure(report)['passes']==[]
        O.save(folder/'restoration.json',dict(status='FAIL'))
        result['altered_restore_rejected']=rejected(lambda:O.prior_closure(report))
        # Fake PortAudio objects exercise actual callback/disk writer code without
        # importing sounddevice, measurement_app or opening any OS audio handle.
        class CallbackStop(Exception):pass
        class CallbackAbort(Exception):pass
        captured=[]
        class FakeStream:
            samplerate=48000;latency=(.15,.15);blocksize=0;closed=False
            def __init__(self,**kwargs):self.kw=kwargs
            def __enter__(self):
                position=0
                for frames in itertools.chain((17,53,511),itertools.cycle((8192,16384))):
                    incoming=bytes((position+i)%256 for i in range(frames*6));out=bytearray(frames*6)
                    try:self.kw['callback'](incoming,out,frames,SimpleNamespace(inputBufferAdcTime=0.,outputBufferDacTime=0.,currentTime=0.),False)
                    except CallbackStop:
                        captured.append((incoming,bytes(out)));break
                    captured.append((incoming,bytes(out)));position+=frames*6
                self.kw['finished_callback']();return self
            def __exit__(self,*args):self.closed=True
            def abort(self):self.kw['finished_callback']()
            def close(self):self.closed=True
        fake=SimpleNamespace(CallbackStop=CallbackStop,CallbackAbort=CallbackAbort,RawStream=FakeStream,
            check_input_settings=lambda **k:None,check_output_settings=lambda **k:None)
        audio=temp/'capture';audio.mkdir();total=T.timing(.01)['native_carrier_frames'];payload=bytes(i%256 for i in range(total*6));packed=audio/'packed.pcm24';packed.write_bytes(payload)
        metadata=O.capture_to_disk(dict(duration_sec=.01),packed,audio,temp/'STOP_REQUEST.json',SimpleNamespace(healthy=lambda:True),fake,
                                   lambda:({'index':1},{'index':2}))
        result['callback_source_cursor_complete']=metadata['carrier_frames_submitted']==total and metadata['source_payload_frames_submitted']==160
        result['callback_writer_closed']=metadata['writer_closed'] and not metadata['callback_errors']
        produced=b''.join(out for _,out in captured)
        result['callback_partition_payload_exact']=produced[:len(payload)]==payload and produced[len(payload):]==T.terminal_packed_silence(total,len(produced)//6-total)
        result['terminal_padding_fully_charged']=metadata['terminal_padding_frames']<16384 and metadata['callback_playback_seconds']<=T.timing(.01)['charged_playback_seconds']
        with wave.open(str(audio/'native_packed.wav'),'rb') as wf:
            result['raw_input_frames_retained']=wf.getnframes()==metadata['captured_frames'] and wf.getsampwidth()==3 and wf.getframerate()==48000
            result['raw_input_bytes_exact']=wf.readframes(metadata['captured_frames'])==b''.join(src for src,_ in captured)
        audio_stop=temp/'capture_stop';audio_stop.mkdir();stop=temp/'STOP_REQUEST.json';stop.write_text('{}')
        def forbidden_audio(**kwargs):raise AssertionError('Existing STOP must not open audio')
        fake.RawStream=forbidden_audio
        stopped=O.capture_to_disk(dict(duration_sec=.01),packed,audio_stop,stop,SimpleNamespace(healthy=lambda:True),fake,lambda:({'index':1},{'index':2}))
        result['existing_STOP_prevents_audio_open']=stopped['captured_frames']==0 and stopped['audio_handles_closed'] and stopped['writer_closed'] and any('STOP' in e for e in stopped['callback_errors'])
        event_audio=temp/'capture_event';event_audio.mkdir();shared_stop=threading.Event();event_output=[]
        class EventStopStream(FakeStream):
            def __enter__(self):
                shared_stop.set();out=bytearray(17*6)
                try:self.kw['callback'](bytes(17*6),out,17,SimpleNamespace(inputBufferAdcTime=0.,outputBufferDacTime=0.,currentTime=0.),False)
                except CallbackAbort:pass
                event_output.append(bytes(out));self.kw['finished_callback']();return self
        fake.RawStream=EventStopStream
        event_meta=O.capture_to_disk(dict(duration_sec=.01),packed,event_audio,temp/'no_stop_file.json',SimpleNamespace(healthy=lambda:True),fake,
            lambda:({'index':1},{'index':2}),external_stop_event=shared_stop)
        result['callback_event_stop_without_file']=event_meta['carrier_frames_submitted']==0 and any('in-memory STOP' in e for e in event_meta['callback_errors'])
        result['callback_stop_fills_packed_silence']=event_output==[T.terminal_packed_silence(0,17)]
        result['event_stop_audio_and_writer_closed']=event_meta['audio_handles_closed'] and event_meta['writer_closed']
        failure_audio=temp/'capture_metadata_failure';failure_audio.mkdir()
        class UnclosedStream(FakeStream):
            closed=False
            def __enter__(self):self.kw['finished_callback']();return self
            def __exit__(self,*args):raise OSError('Fixture context close failure')
            def abort(self):raise OSError('Fixture abort failure')
            def close(self):raise OSError('Fixture handle remains open')
        fake.RawStream=UnclosedStream
        real_save=O.save
        def failed_metadata_write(path,*args,**kwargs):
            if Path(path).name=='capture_metadata.json':raise OSError('Fixture metadata write failed after close failure')
            return real_save(path,*args,**kwargs)
        owner_visible=dict(audio_open_attempted=False,audio_handles_closed=True);write_raised=False
        O.save=failed_metadata_write
        try:
            O.capture_to_disk(dict(duration_sec=.01),packed,failure_audio,temp/'absent_stop.json',SimpleNamespace(healthy=lambda:True),fake,
                lambda:({'index':1},{'index':2}),audio_state=owner_visible)
        except OSError:write_raised=True
        finally:O.save=real_save
        result['metadata_failure_retains_unclosed_owner_state']=write_raised and owner_visible['audio_open_attempted'] and owner_visible['audio_handles_closed'] is False
        result['metadata_failure_withholds_restoration_despite_USB_closed']=not O.restoration_permitted(owner_visible,True)
    tree=ast.parse(Path(O.__file__).read_text())
    top_imports=[n for n in tree.body if isinstance(n,(ast.Import,ast.ImportFrom))]
    text=' '.join(ast.unparse(n) for n in top_imports)
    result['no_import_time_vendor_audio_module']=not any(s in text for s in ('sounddevice','measurement_app','s3_hardware','s4_restore','s6d_telemetry'))
    result['read_only_native_imports']=not any(s in (Path(O.__file__).parent/'s6d_native/S6DQueuedTelemetry.cs').read_text() for s in ('control_write_command','control_write_command_async'))
    assert all(result.values()),result
    return dict(schema='s6d-capture-fixtures.v1',status='PASS_MODEL_FREE_NOT_PHYSICAL_QUALIFICATION',checks=result,
        passed=sum(result.values()),total=len(result),hardware_calls=0,vendor_DLL_calls=0,real_audio_streams=0,
        sources=[T.binding(Path(__file__)),T.binding(O.__file__),T.binding(T.__file__),T.binding(core_path)])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path);a=p.parse_args();value=checks()
    if a.output:O.save(a.output,value,True)
    print(json.dumps(value,indent=2))
