from pathlib import Path
import json,threading,time,traceback,math,shutil,uuid
from .core import *
from .excitation import get_excitation,ASSETS
from .telemetry import TelemetryLogger,DEFAULT_FIELDS,ALL_FIELDS
from .queued_telemetry import create_telemetry_logger
from .markers import marker_qc
from .playback import separate_playback
from .reference import ReferenceCapture,validate_reference

def validate_request(r,require_metadata=False):
    if not isinstance(r,dict):raise ValueError('Expected a measurement request')
    r=json.loads(json.dumps(r,allow_nan=False))
    if r.get('mode') not in ['record','measure']:raise ValueError('mode must be record or measure')
    default_domain='amplified' if r.get('schema_version')==3 else 'raw'
    if r.get('domain',default_domain) not in ['raw','amplified','both']:raise ValueError('Invalid microphone domain')
    seconds=float(r.get('duration_seconds',30))
    if not math.isfinite(seconds) or not 5<=seconds<=300:raise ValueError('Recording duration must be 5–300 seconds')
    gain=float(r.get('playback_gain_db',-18))
    if not math.isfinite(gain) or not -60<=gain<=0:raise ValueError('Playback gain must be between -60 and 0 dB')
    if r.get('playback_channel','left') not in ['left','right']:raise ValueError('Select one playback channel')
    if not isinstance(r.get('setup',{}),dict):raise ValueError('Setup must be an object')
    if require_metadata or r.get('schema_version') in [2,3]:
        from .trial import validate_setup
        r['setup']=validate_setup(r.get('setup',{}),required=r['mode']=='measure')
    r['reference']=validate_reference(r.get('reference',{}))
    if r['mode']=='measure':
        krk_campaign=r.get('setup',{}).get('hardware_context',{}).get('revision')=='krk-emm6-2026-09-06'
        if krk_campaign and r['setup'].get('speaker',{}).get('connection')!='wired':
            raise ValueError('KRK campaign measurements require wired playback')
        get_excitation(r.get('excitation_id'))
        idx=r.get('playback_device_index')
        if isinstance(idx,bool) or not isinstance(idx,int):raise ValueError('Select an explicit playback endpoint')
        inventory=devices();ds={d['index']:d for d in inventory}
        if idx not in ds or ds[idx]['max_output_channels']<1:raise ValueError('Selected playback endpoint unavailable')
        if krk_campaign and re.search(r'bluetooth|bthhfenum|a2dp|airpods',ds[idx]['name'],re.I):
            raise ValueError('Select the wired KRK output, not a Bluetooth endpoint')
        problem=playback_endpoint_problem(ds[idx],inventory)
        if problem:raise ValueError(problem)
        if r.get('playback_channel','left')=='right':
            if ds[idx]['max_output_channels']<2:raise ValueError('Selected mono endpoint has no right channel')
            if re.search(r'xvf|xmos',ds[idx]['name'],re.I):raise ValueError('XVF playback uses left; right is reserved for the continuity check')
        if r.get('playback_device_name') and r['playback_device_name']!=ds[idx]['name']:raise ValueError('Playback device changed; refresh the endpoint list')
    r.update(duration_seconds=seconds,playback_gain_db=gain,domain=r.get('domain',default_domain),setup=r.get('setup',{}))
    return r

def sentinel_qc(decoded,source):
    y=decoded[:,0];anchor=32000
    if len(source)<anchor+64:return {'status':'UNAVAILABLE','reason':'short interrupted recording'}
    matches=np.flatnonzero(y==source[anchor]);lag=None
    for i in matches:
        if i+64<=len(y) and np.array_equal(y[i:i+64],source[anchor:anchor+64]):
            if lag is not None:return {'status':'FAIL','reason':'ambiguous alignment'}
            lag=anchor-int(i)
    if lag is None:return {'status':'FAIL','reason':'known sequence not found'}
    a=max(0,-lag);b=min(len(y),len(source)-lag)
    xx=source[a+lag:b+lag];yy=y[a:b]
    mismatch=int(np.count_nonzero(xx!=yy))
    start,end=16000,len(source)-16000
    active_complete=a+lag<=start and b+lag>=end
    return {'status':'PASS' if mismatch==0 and active_complete else 'FAIL','source_minus_capture_sample_offset':lag,
      'compared_samples':len(xx),'mismatches':mismatch,'active_source_seconds':(end-start)/16000,
      'complete_active_source_captured':active_complete,
      'scope':'Known 16k collection-group continuity; no calibrated acoustic latency or device telemetry timestamps'}

def choose_outcome(mode,checks,error=None,stopped=False,marker_status=None,failure_details=None):
    """Separate acquisition failures from acoustic candidate review, without I/O."""
    if mode not in ['record','measure']:raise ValueError('Unknown capture mode')
    failed=[name for name,value in checks.items() if not value] if checks else ['capture_checks_unavailable']
    integrity=bool(checks) and not failed and error is None and not stopped
    details={name:str(value) for name,value in (failure_details or {}).items() if value is not None}
    if stopped:
        status='RETAKE';message='Recording stopped. Partial evidence retained; start a new take for a complete recording.'
    elif failed or error is not None:
        status='INVESTIGATE'
        parts=['Capture checks failed: '+', '.join(name.replace('_',' ') for name in failed)+'.'] if failed else []
        if error is not None:parts.append('Capture error: '+str(error)+'.')
        parts.extend(name.replace('_',' ')+': '+value for name,value in details.items())
        message=' '.join(parts)+' Evidence retained; resolve these failures before repeating.'
    elif mode=='measure' and marker_status=='RETAKE':
        status='RETAKE';message='Acoustic marker checks failed despite clean digital capture. Check the played source, level and marker report before repeating.'
    elif mode=='record':
        status='PASS';message='Recording complete: microphone audio and direction/energy logs passed capture checks. Direction accuracy and acoustic calibration remain unqualified.'
    else:
        status='REVIEW';message='Measurement capture passed integrity checks. Review acoustic markers, source calibration and geometry before using it for RIR analysis.'
    return {'status':status,'message':message,'capture_integrity_pass':integrity,'failed_checks':failed,'failure_details':details}

def acquire(request,folder,stop,update):
    req=validate_request(request)
    if req['domain']=='both':raise ValueError('Both domains require acquire_trial: two consecutive passes')
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=False)
    write_json(folder/'request.json',req)
    for name in ['__init__.py','server.py','trial.py','core.py','acquisition.py','reference.py','reference_calibration.py','speaker_reference.py','telemetry.py','queued_telemetry.py','excitation.py','markers.py','playback.py','static/index.html','static/app.js','static/style.css']:
        (folder/'source'/name).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(BASE/'measurement_app'/name,folder/'source'/name)
    c=Control(folder/'commands');initial={};dac={};restored={};telem=None;play_thread=None;play={};error=None;raw=None;meta=None;result={}
    changed=False;gpo_changed=False;telemetry_result=None
    reference=None;reference_result={'enabled':False}
    try:
        identity=c.identify();write_json(folder/'identity.json',identity)
        if req.get('schema_version',0)>=3:
            expected_gain_delay={'AUDIO_MGR_MIC_GAIN':[10],'AUDIO_MGR_SYS_DELAY':[-32]}
            observed_gain_delay={name:identity.get(name) for name in expected_gain_delay}
            write_json(folder/'capture_gain_delay_lock.json',{'expected':expected_gain_delay,'observed':observed_gain_delay,
                'policy':'Verify fixed live-capture configuration; never silently change it. HIL replay has a separate unity/zero contract.'})
            if observed_gain_delay!=expected_gain_delay:
                raise RuntimeError('Capture gain/delay changed. This campaign requires microphone gain 10 and SYS_DELAY -32. Resolve the configuration before recording; no automatic change was made.')
        bits=identity['USB_BIT_DEPTH'][0]
        if bits not in [16,24] or identity['USB_BIT_DEPTH']!=[bits,bits]:raise RuntimeError('Equal 16/16 or24/24 USB widths required; prepare24bit for precision')
        if req['mode']=='measure' and bits!=24:raise RuntimeError('Measurement requires USB24. Stop the recorder and run Prepare-XVF-24bit.cmd, then reopen it and refresh devices.')
        (folder/'before_params.txt').write_text(c.query('--dump-params'),encoding='utf-8')
        initial={n:c.values(n) for n in ['AUDIO_MGR_OP_ALL','AUDIO_MGR_OP_PACKED','AUDIO_MGR_OP_UPSAMPLE','GPO_PORT_PIN_INDEX']}
        write_json(folder/'initial_state.json',initial)
        if stop.is_set():raise RuntimeError('Stopped during preflight')
        c.set('GPO_PORT_PIN_INDEX',[0,4])
        physical={n:c.values(n) for n in ['GPO_PIN_ACTIVE_LEVEL','GPO_PIN_PWM_DUTY','GPO_PIN_FLASH_MASK']}
        write_json(folder/'physical_array_selection.json',physical)
        if physical!={'GPO_PIN_ACTIVE_LEVEL':[1],'GPO_PIN_PWM_DUTY':[0],'GPO_PIN_FLASH_MASK':[4294967295]}:
            raise RuntimeError('Hardware array selection does not match normal linear configuration')
        category=1 if req['domain']=='raw' else 3
        route=[10,1,category,0,category,2,6,3,category,1,category,3]
        excitation=get_excitation(req['excitation_id']) if req['mode']=='measure' else None
        wave=None;seconds=req['duration_seconds'];inp,out=xvf_endpoints()
        same_clock=bool(excitation and req['playback_device_index']==out['index'])
        if excitation:
            wave,rate=sf.read(excitation['path'],dtype='float64');assert rate==48000 and wave.ndim==1
            seconds=len(wave)/48000+5
            shutil.copy2(excitation['path'],folder/'excitation_original.wav')
            shutil.copy2(ASSETS/'signal_timing.json',folder/'signal_timing.json')
        frames=int(round(seconds*48000));frames-=frames%3
        sequence=np.zeros(frames//3,dtype=np.int32)
        sequence[16000:-16000]=np.random.default_rng(3800321).integers(-(1<<(bits-3)),1<<(bits-3),size=len(sequence)-32000,dtype=np.int32)&np.int32(-2)
        payload=np.zeros((frames,2),dtype=np.int32);payload[:,1]=np.repeat(sequence,3)
        if same_clock:
            if c.values('I2S_DAC_DSP_ENABLE')!=[0]:raise RuntimeError('XVF LINE OUT measurement requires documented reference-DAC routing I2S_DAC_DSP_ENABLE0')
            c.set('GPO_PORT_PIN_INDEX',[0,3])
            if c.values('GPO_PIN_ACTIVE_LEVEL')!=[1] or c.values('GPO_PIN_PWM_DUTY')!=[100] or c.values('GPO_PIN_FLASH_MASK')!=[4294967295]:
                raise RuntimeError('XVF analog DAC is not in normal enabled state')
            at=72000;left=np.rint(wave*10**(req['playback_gain_db']/20)*(2**(bits-1))).astype(np.int32)
            payload[at:at+len(left),0]=left
            play.update(route='XVF_LINE_OUT',same_clock_as_capture=True,first_native_output_frame=at,
               acoustic_cabinets_verified=False,channel_note='Left reference duplicated on both DAC sockets; connect onlyONEEdifierRCA input.',
               waveform_frames=len(left),gain_db=req['playback_gain_db'])
        else:
            # Right native USB is the continuity signal; keep the unused analog DAC quiet.
            gpo_changed=True;c.set('GPO_PORT_PIN_INDEX',[0,3])
            dac={n:c.values(n) for n in ['GPO_PIN_ACTIVE_LEVEL','GPO_PIN_PWM_DUTY','GPO_PIN_FLASH_MASK']}
            write_json(folder/'dac_initial.json',dac)
            if dac['GPO_PIN_ACTIVE_LEVEL']!=[1]:raise RuntimeError('Unexpected DAC reset polarity')
            c.query('GPO_PIN_VAL',0,3,0)
            if c.values('GPO_PIN_PWM_DUTY')!=[0]:raise RuntimeError('DAC reset readback failed')
            play.update(route='SEPARATE_AUDIO_DEVICE' if excitation else 'SILENT_RECORD_ONLY',same_clock_as_capture=False)
        changed=True;c.set('AUDIO_MGR_OP_UPSAMPLE',[1,1]);c.set('AUDIO_MGR_OP_ALL',route);c.set('AUDIO_MGR_OP_PACKED',[1,1])
        write_json(folder/'capture_configuration.json',{'domain':req['domain'],'category':category,'container_bits':bits,
          'channel_order':['digital_continuity','processed_auto']+[f'{req["domain"]}_MIC{i}' for i in range(4)],
          'mux':route,'microphone_gain':identity['AUDIO_MGR_MIC_GAIN'],'system_delay_samples':identity['AUDIO_MGR_SYS_DELAY'],
          'speaker_relative_calibration_only':True,'same_clock_playback':same_clock,'source_position_from_user':req['setup'],
          'continuity_reference_scope':'Official3.2.1 has one AEC reference: USB LEFT. Unpacked USB RIGHT remains separate and is the continuity signal. DAC DSP0 duplicatesLEFT; separate-output tests hold DAC reset.'})
        np.save(folder/'continuity_source_16k.npy',sequence);save_counts(folder/'usb_playback.wav',payload,48000,bits)
        def received(row): update(last_telemetry=row)
        fields=ALL_FIELDS if req.get('include_selected_angles') else DEFAULT_FIELDS
        if stop.is_set():raise RuntimeError('Stopped before capture')
        telem=create_telemetry_logger(HOST,folder/'telemetry',fields=fields,duration_s=seconds+15,on_row=received).start()
        ready_deadline=time.monotonic()+8
        while not all(n in telem.latest for n in fields):
            if stop.is_set() or telem.result is not None or time.monotonic()>ready_deadline:raise RuntimeError('Telemetry failed to become ready before audio')
            time.sleep(.025)
        if req['reference']['enabled']:
            reference=ReferenceCapture(folder/'reference',{**req['reference'],'duration_seconds':min(seconds+25,330)},stop)
            reference.start()
            if not reference.wait_ready(timeout=3):raise RuntimeError('Reference microphone produced no frames before XVF capture')
        def started():
            nonlocal play_thread
            if excitation and not same_clock:
                play_thread=threading.Thread(target=separate_playback,args=(req['playback_device_index'],wave,req['playback_gain_db'],req.get('playback_channel','left'),stop,play),daemon=True);play_thread.start()
        update(state='recording',message='Recording all four microphones and native telemetry',progress=0,
          device={'version':'3.2.1','build':'ua-io48-lin','usb_bit_depth':[bits,bits],'native_sample_rate_hz':48000,
                  'microphone_sample_rate_hz':16000,'payload_bits':bits-1,'mic_gain':identity['AUDIO_MGR_MIC_GAIN'][0],
                  'system_delay_samples':identity['AUDIO_MGR_SYS_DELAY'][0]})
        raw,meta=capture_native(seconds,bits,payload,stop,on_started=started,progress=lambda p:update(progress=p))
        save_counts(folder/'native_packed.wav',raw,48000,bits)
        write_json(folder/'capture.json',meta)
    except BaseException as e:error=repr(e);(folder/'error_trace.txt').write_text(traceback.format_exc(),encoding='utf-8')
    finally:
        if reference:
            try:reference_result={'enabled':True,**reference.finish()}
            except BaseException as e:
                reference_result={'enabled':True,'status':'FAIL','stream_closed':False,'error':repr(e)}
                error=(error or '')+' Reference shutdown: '+repr(e)
        if telem:
            telem.stop('audio_capture_ended');telemetry_result=telem.wait(20)
            if telemetry_result is None:error=(error or '')+' telemetry did not stop'
        if play_thread:
            if play_thread.is_alive():stop.set()
            play_thread.join(3)
            if play_thread.is_alive():error=(error or '')+' playback did not stop'
        update(state='restoring',message='Restoring audio routes and saving evidence')
        safe_control=(telem is None or telemetry_result is not None) and (play_thread is None or not play_thread.is_alive()) and (reference is None or reference_result.get('stream_closed',False))
        if not safe_control:restored['control_restoration_deferred']='Telemetry, playback or reference writer still active; no further device control or evidence freeze permitted'
        if changed and safe_control:
            for n in ['AUDIO_MGR_OP_PACKED','AUDIO_MGR_OP_ALL','AUDIO_MGR_OP_UPSAMPLE']:
                try:c.set(n,initial[n]);restored[n]=True
                except BaseException as e:restored[n]=repr(e)
        if gpo_changed and safe_control:
            try:
                c.set('GPO_PORT_PIN_INDEX',[0,3])
                for n,v in dac.items():c.set(n,v)
                restored['DAC']=True
            except BaseException as e:restored['DAC']=repr(e)
        if initial and safe_control:
            index=initial['GPO_PORT_PIN_INDEX']
            if index[0]==0 and index[1] in range(3,8):
                try:c.set('GPO_PORT_PIN_INDEX',index);restored['GPO_selector']=True
                except BaseException as e:restored['GPO_selector']=repr(e)
            else:
                write_json(folder/'inspection_selector_note.json',{'original_selector':index,'restored':False,
                  'reason':'Boot default selector0,0 is outside the documented writable pin3..7 range. Diagnostic selector left at last inspected pin; does not drive any output.'})
        if safe_control and meta is not None:
            try:
                after_bits=c.values('USB_BIT_DEPTH');write_json(folder/'usb_width_after_capture.json',{'observed':after_bits,'expected':[bits,bits]})
                if after_bits!=[bits,bits]:error=(error or '')+' USB sample width changed'
                if req.get('schema_version',0)>=3:
                    after_gain_delay={name:c.values(name) for name in expected_gain_delay}
                    write_json(folder/'gain_delay_after_capture.json',{'observed':after_gain_delay,'expected':expected_gain_delay})
                    if after_gain_delay!=expected_gain_delay:error=(error or '')+' Fixed microphone gain/delay changed during capture'
            except BaseException as e:error=(error or '')+' Width readback: '+repr(e)
        write_json(folder/'restoration.json',restored);write_json(folder/'playback.json',play)
        write_json(folder/'reference_result.json',reference_result)
    update(state='analysing',message='Checking audio, continuity, telemetry and metadata')
    qc={};checks={}
    try:
        if raw is not None and len(raw):
            decoded,qc=decode_packed(raw,bits);save_counts(folder/'decoded_six_channels.wav',decoded,16000,bits)
            save_counts(folder/'microphones_4ch.wav',decoded[:,2:],16000,bits)
            save_counts(folder/'processed_auto.wav',decoded[:,1],16000,bits)
            for i in range(4):save_counts(folder/f'MIC{i}.wav',decoded[:,i+2],16000,bits)
            qc['microphones']=signal_stats(decoded[:,2:],bits);qc['processed']=signal_stats(decoded[:,1:2],bits)
            qc['continuity']=sentinel_qc(decoded,sequence)
            coverage={}
            if telem:
                for field in fields:
                    times=[r.get('host_response_end_monotonic_ns',r['host_line_arrival_monotonic_ns']) for r in telem.rows if r['command']==field]
                    coverage[field]={'count':len(times),'first_relative_to_audio_start_s':(times[0]-meta['start_monotonic_ns'])/1e9 if times else None,
                       'last_relative_to_audio_end_s':(times[-1]-meta['end_monotonic_ns'])/1e9 if times else None,
                       'coverage_brackets_host_audio_interval':bool(times and times[0]<=meta['start_monotonic_ns'] and times[-1]>=meta['end_monotonic_ns']-.05)}
            qc['telemetry_coverage']=coverage
            checks={'all_microphones_nonzero':all(v>0 for v in qc['microphones']['nonzero_samples']),
                'all_microphones_vary':all(v>0 for v in qc['microphones']['peak_to_peak_counts']),
                'no_zero_one_second_microphone_windows':not any(qc['microphones']['fully_zero_one_second_windows']),
                'microphones_unclipped':not any(qc['microphones']['rail_samples']),
                'packing_markers':qc['marker_error_count']==0,'known_sequence':qc['continuity']['status']=='PASS',
                'audio_callback_clean':not meta['callback_flags'] and not meta['callback_errors'],
                'telemetry':bool(telemetry_result and telemetry_result['status']=='PASS'),
                'telemetry_host_interval_coverage':bool(coverage) and all(v['coverage_brackets_host_audio_interval'] for v in coverage.values()),
                'restoration':bool(restored) and all(v is True for v in restored.values()),
                'playback':not excitation or same_clock or bool(play.get('completed') and play.get('drained') and not play.get('error') and not play.get('underflows') and play.get('source_frame_continuity',{}).get('contiguous') and not any(set(e.get('status_flags',[]))-{'priming_output'} for e in play.get('callback_status_events',[])))}
            if req['reference']['enabled']:
                reference_coverage=bool(reference_result.get('start_monotonic_ns',float('inf'))<=meta['start_monotonic_ns'] and reference_result.get('end_monotonic_ns',0)>=meta['end_monotonic_ns'])
                qc['reference']={'capture':reference_result,'host_interval_coverage':reference_coverage,
                    'sample_synchronized_with_xvf':False,'note':'Independent audio clock; host coverage is not a sample alignment or drift qualification'}
                checks['reference_capture']=reference_result.get('status')=='PASS' and reference_result.get('stream_closed',False)
                checks['reference_host_interval_coverage']=reference_coverage
            if excitation:
                offset=(1.5 if same_clock else (play.get('start_monotonic_ns',meta['start_monotonic_ns'])-meta['start_monotonic_ns'])/1e9)-qc['startup_frames_excluded']/48000
                qc['acoustic_markers']=marker_qc(decoded[:,2:],excitation,offset)
            write_json(folder/'quality.json',qc)
    except BaseException as e:error=(error or '')+' QC: '+repr(e)
    outcome=choose_outcome(req['mode'],checks,error,stop.is_set(),qc.get('acoustic_markers',{}).get('status'),{'playback':play.get('error')})
    passed=outcome['capture_integrity_pass'];status=outcome['status']
    result={'run_id':folder.name,'status':status,'capture_integrity_pass':passed,'scientific_measurement_qualified':False,
      'checks':checks,'error':error,'stopped':stop.is_set(),'quality':qc,'telemetry':telemetry_result,
      'reference':reference_result,
      'message':outcome['message'],'failed_checks':outcome['failed_checks'],'failure_details':outcome['failure_details'],
      'limits':['No absolute SPL calibration','Native angles not transformed into measured room coordinates',
        'Host telemetry times are not device sample timestamps','Acoustic marker candidates require review; no final RIR deconvolution'],
      'same_clock_playback':play.get('same_clock_as_capture',False),'hardware_logger_still_active':not safe_control,
      'acoustic_marker_review':qc.get('acoustic_markers',{}).get('status')}
    write_json(folder/'result.json',result)
    summary=f'''XVF measurement {folder.name}\n\nStatus: {status}\n\n{result['message']}\n\nFour-channel audio: microphones_4ch.wav (16 kHz, {locals().get('bits','unknown')}-bit container).\nOriginal packed carrier: native_packed.wav. See request.json for source, room, pose and dial settings.\n\nScientific measurement qualified: false. Capture integrity pass: {passed}.\n\nChecks:\n'''+''.join(f'- {k}: {v}\n' for k,v in checks.items())+'\nLimits:\n'+''.join(f'- {v}\n' for v in result['limits'])
    (folder/'REPORT.txt').write_text(summary,encoding='utf-8')
    if safe_control:
        seal=freeze(folder);result['seal']=seal
    return result
