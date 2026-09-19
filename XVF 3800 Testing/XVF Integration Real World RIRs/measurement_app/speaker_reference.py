"""One-time source-reference sweep, separate from routine XVF measurements."""
from pathlib import Path
import math
import shutil
import threading
import time
import traceback
import numpy as np
import soundfile as sf
from .core import BASE,Control,devices,now,write_json,freeze,playback_endpoint_problem,sha
from .reference import ReferenceCapture,validate_reference
from .excitation import get_excitation,ASSETS
from .playback import separate_playback,START_DELAY_S


def validate_speaker_reference(body):
    if body.get('schema_version')!=3:raise ValueError('Reload the current recorder')
    ref=validate_reference(body.get('reference',{}))
    if not ref['enabled']:raise ValueError('Select the reference microphone for this setup recording')
    distance=body.get('reference',{}).get('distance_to_speaker_m')
    if isinstance(distance,bool) or not isinstance(distance,(int,float)) or not math.isfinite(distance) or distance<=0:
        raise ValueError('Enter the reference capsule to speaker distance in metres')
    if not str(ref.get('placement_note') or '').strip():raise ValueError('Describe the reference microphone placement and orientation')
    ref['distance_to_speaker_m']=distance
    if not isinstance(body.get('setup',{}),dict):raise ValueError('Setup must be an object')
    speaker=body.get('setup',{}).get('speaker',{})
    if not isinstance(speaker,dict) or speaker.get('connection')!='wired':
        raise ValueError('Use one wired speaker for the reference recording and select Wired in speaker settings')
    gain=body.get('playback_gain_db')
    if isinstance(gain,bool) or not isinstance(gain,(int,float)) or not math.isfinite(gain) or not -60<=gain<=0:
        raise ValueError('Set a playback level between -60 and 0 dB')
    inventory=devices();index=body.get('playback_device_index')
    if isinstance(index,bool) or not isinstance(index,int):raise ValueError('Select an explicit speaker output')
    output=next((d for d in inventory if d.get('index')==index),None)
    if output is None:raise ValueError('Selected speaker output is unavailable')
    issue=playback_endpoint_problem(output,inventory)
    if issue:raise ValueError(issue)
    if body.get('playback_device_name')!=output['name']:raise ValueError('Speaker output changed; refresh devices')
    channel=body.get('playback_channel','left')
    if channel not in ['left','right']:raise ValueError('Select one playback channel')
    if channel=='right' and (output['max_output_channels']<2 or 'XVF' in output['name'].upper()):raise ValueError('Use the left channel for this output')
    get_excitation(body.get('excitation_id'))
    return {**body,'reference':ref,'mode':'speaker_reference','domain':'reference','recorded_utc':now(),
        'speaker_output':output,'source_correction_applied':False,'routine_xvf_capture':False}


def acquire_speaker_reference(request,folder,stop,update):
    folder=Path(folder)
    if (folder/'SHA256SUMS.txt').exists():raise FileExistsError('Speaker reference already frozen')
    write_json(folder/'request.json',request)
    (folder/'source').mkdir()
    for name in ['speaker_reference.py','reference.py','core.py','playback.py','excitation.py']:
        shutil.copy2(BASE/'measurement_app'/name,folder/'source'/name)
    ref=None;thread=None;play={};receipt={'enabled':True,'status':'FAIL','stream_closed':True};error=None
    try:
        stimulus=get_excitation(request['excitation_id']);wave,rate=sf.read(stimulus['path'],dtype='float64')
        if rate!=48000 or wave.ndim!=1:raise RuntimeError('Expected verified mono 48 kHz excitation')
        shutil.copy2(stimulus['path'],folder/'excitation_original.wav');shutil.copy2(ASSETS/'signal_timing.json',folder/'signal_timing.json')
        sf.write(folder/'electrical_source_selected.wav',wave*10**(request['playback_gain_db']/20),rate,subtype='FLOAT')
        write_json(folder/'source_reference_contract.json',{'source_original_sha256':sha(stimulus['path']),
            'digital_gain_db':request['playback_gain_db'],'reference_clock_shared_with_playback':False,
            'frequency_response_correction_applied':False,'speaker_correction_generated':False,
            'purpose':'Initial speaker/source characterization; reference microphone is not required for later XVF trials',
            'analysis_requirement':'Separate direct speaker response from calibration-room reflections before deriving a bounded correction'})
        if 'XVF' in request['speaker_output']['name'].upper():
            control=Control(folder/'commands');identity=control.identify();write_json(folder/'xvf_output_identity.json',identity)
            if control.values('I2S_DAC_DSP_ENABLE')!=[0]:raise RuntimeError('XVF LINE OUT requires the normal reference-DAC route I2S_DAC_DSP_ENABLE 0')
            selector=control.values('GPO_PORT_PIN_INDEX')
            try:
                control.set('GPO_PORT_PIN_INDEX',[0,3])
                if control.values('GPO_PIN_ACTIVE_LEVEL')!=[1] or control.values('GPO_PIN_PWM_DUTY')!=[100] or control.values('GPO_PIN_FLASH_MASK')!=[4294967295]:
                    raise RuntimeError('XVF LINE OUT is not enabled; restore normal output before the speaker reference')
            finally:
                if selector[0]==0 and selector[1] in range(3,8):control.set('GPO_PORT_PIN_INDEX',selector)
        duration=len(wave)/rate+5
        ref=ReferenceCapture(folder/'reference',{**request['reference'],'duration_seconds':duration+10},stop)
        ref.start()
        if not ref.wait_ready(timeout=3):raise RuntimeError('No reference microphone frames before playback')
        update(state='recording',progress=0,message='Recording the one-time speaker reference; routine XVF captures will not require this microphone')
        thread=threading.Thread(target=separate_playback,args=(request['playback_device_index'],wave,request['playback_gain_db'],request.get('playback_channel','left'),stop,play),daemon=True)
        thread.start();began=time.monotonic()
        while time.monotonic()-began<duration:
            if stop.wait(.1):break
            update(progress=min((time.monotonic()-began)/duration,.99))
            if play.get('error'):raise RuntimeError(play['error'])
    except BaseException as exc:error=repr(exc);(folder/'error_trace.txt').write_text(traceback.format_exc(),encoding='utf-8')
    finally:
        if thread:
            if thread.is_alive():stop.set()
            thread.join(3)
        if ref:
            try:receipt={'enabled':True,**ref.finish()}
            except BaseException as exc:receipt={'enabled':True,'status':'FAIL','stream_closed':False,'error':repr(exc)};error=error or repr(exc)
    closed=receipt.get('stream_closed',False) and (thread is None or not thread.is_alive()) and not play.get('cleanup_errors')
    playback_ok=bool(play.get('completed') and play.get('drained') and not play.get('error') and not play.get('underflows') and play.get('source_frame_continuity',{}).get('contiguous') and not any(set(e.get('status_flags',[]))-{'priming_output'} for e in play.get('callback_status_events',[])))
    reference_coverage=bool(play.get('start_monotonic_ns') is not None and play.get('end_monotonic_ns') is not None
        and receipt.get('start_monotonic_ns',float('inf'))<=play['start_monotonic_ns']
        and receipt.get('end_monotonic_ns',0)>=play['end_monotonic_ns'])
    minimum_frames=math.ceil((len(wave)/rate+START_DELAY_S)*48000) if 'wave' in locals() else None
    reference_length=minimum_frames is not None and receipt.get('frames',0)>=minimum_frames
    good=bool(closed and receipt.get('status')=='PASS' and playback_ok and reference_coverage and reference_length and not stop.is_set() and error is None)
    result={'kind':'speaker_reference','run_id':folder.name,'status':'REVIEW' if good else 'RETAKE' if stop.is_set() else 'INVESTIGATE',
        'message':'Speaker-reference recording archived with source settings and calibration evidence. Keep it for later comparison; no speaker correction or deconvolution is required now.' if good else 'Speaker-reference recording needs attention: '+str(error or play.get('error') or receipt.get('error') or 'capture/playback incomplete'),
        'capture_integrity_pass':good,'scientific_measurement_qualified':False,'source_correction_generated':False,
        'reference':receipt,'checks':{'reference_capture':receipt.get('status')=='PASS','playback':playback_ok,
            'reference_host_interval_coverage':reference_coverage,'reference_minimum_frame_count':reference_length,'all_writers_stopped':bool(closed)},
        'minimum_reference_frames':minimum_frames,'timing_scope':'Independent audio clocks; host coverage and frame count are not an acoustic timing or drift qualification',
        'hardware_logger_still_active':not closed,'error':error,'stopped':stop.is_set(),'recorded_utc':request['recorded_utc']}
    write_json(folder/'playback.json',play);write_json(folder/'result.json',result)
    (folder/'REPORT.txt').write_text('One-time speaker reference '+folder.name+'\n\n'+result['status']+'\n'+result['message']+
        '\n\nReference WAVs: reference/\nSource waveform: excitation_original.wav\nNo automatic speaker equalization, deconvolution or room correction applied.\n',encoding='utf-8')
    if closed:result['seal']=freeze(folder)
    return result
