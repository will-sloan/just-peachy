"""Single-owner bounded S3 replay; explicit speaker gate and finally restoration."""
import argparse, json, msvcrt, re, shutil, socket, sys, threading, time, traceback
from pathlib import Path
from s0_common import ROOT, SIM, HashCache, save, now
sys.path.insert(0,str(ROOT))
import measurement_app
import numpy as np
import soundfile as sf
import sounddevice as sd
from measurement_app.core import Control, HOST, capture_native, decode_packed, save_counts, refresh_audio_backend, xvf_endpoints
from measurement_app.queued_telemetry import create_telemetry_logger

# Curated documented value setters; NOT an executable dump or generated command list.
# Duplicate mux aliases, GPIO drivers/selectors, special filter access, DFU, burn,
# counters and read-only/adaptive telemetry are deliberately absent.
STATIC='''SHF_BYPASS AEC_FIXEDBEAMSAZIMUTH_VALUES AEC_FIXEDBEAMSELEVATION_VALUES AEC_FIXEDBEAMSGATING
AEC_HPFONOFF AEC_AECSILENCELEVEL AEC_AECEMPHASISONOFF AEC_FAR_EXTGAIN AEC_PCD_COUPLINGI AEC_PCD_MINTHR
AEC_PCD_MAXTHR AEC_ASROUTONOFF AEC_ASROUTGAIN AEC_FIXEDBEAMSONOFF AEC_FIXEDBEAMNOISETHR
AUDIO_MGR_MIC_GAIN AUDIO_MGR_REF_GAIN I2S_INPUT_PACKED AUDIO_MGR_SELECTED_CHANNELS AUDIO_MGR_OP_PACKED
AUDIO_MGR_OP_UPSAMPLE AUDIO_MGR_OP_ALL AUDIO_MGR_FAR_END_DSP_ENABLE AUDIO_MGR_SYS_DELAY I2S_DAC_DSP_ENABLE
PP_AGCONOFF PP_AGCMAXGAIN PP_AGCDESIREDLEVEL PP_AGCGAIN PP_AGCTIME PP_AGCFASTTIME PP_AGCALPHAFASTGAIN
PP_AGCALPHASLOW PP_AGCALPHAFAST PP_LIMITONOFF PP_LIMITPLIMIT PP_MIN_NS PP_MIN_NN PP_ECHOONOFF PP_GAMMA_E
PP_GAMMA_ETAIL PP_GAMMA_ENL PP_NLATTENONOFF PP_NLAEC_MODE PP_MGSCALE PP_FMIN_SPEINDEX PP_DTSENSITIVE
PP_ATTNS_MODE PP_ATTNS_NOMINAL PP_ATTNS_SLOPE'''.split()
OBSERVE_ONLY=['GPI_INDEX','GPI_EVENT_CONFIG','GPI_ACTIVE_LEVEL','GPO_PORT_PIN_INDEX','GPO_PIN_ACTIVE_LEVEL','GPO_PIN_PWM_DUTY','GPO_PIN_FLASH_MASK']
FROZEN={'AUDIO_MGR_MIC_GAIN':[1],'AUDIO_MGR_REF_GAIN':[1],'AUDIO_MGR_SYS_DELAY':[0],
    'AEC_ASROUTONOFF':[1],'AEC_ASROUTGAIN':[1],'SHF_BYPASS':[0],
    'AUDIO_MGR_OP_UPSAMPLE':[1,1],'AUDIO_MGR_OP_ALL':[3,0,3,2,7,3,3,1,3,3,6,3],
    'AUDIO_MGR_OP_PACKED':[1,1],'I2S_INPUT_PACKED':[1]}

def values(c,name):
    lines=[l for l in c.query(name).splitlines() if l.startswith(name+' ')]
    if len(lines)!=1:raise RuntimeError('Ambiguous control reply '+name)
    toks=re.sub(r'\([^)]*\)','',lines[0][len(name):]).split();result=[]
    for t in toks:
        enum=re.search(r'\[(\d+)\]',t)
        if enum:result.append(int(enum[1]))
        else:
            try:result.append(int(t))
            except ValueError:result.append(float(t))
    if not all(np.isfinite(result)):raise RuntimeError('Nonfinite configuration '+name)
    return result

def set_verified(c,name,desired):
    c.query(name,*desired);actual=values(c,name)
    if actual!=desired:raise RuntimeError(f'{name} exact readback {actual} != {desired}')

def restore_values(c,desired):
    observed={};changed=[]
    # Reapply only values proven different; avoids unnecessary lossy coefficient conversions.
    for name,v in desired.items():
        actual=values(c,name)
        if actual!=v:set_verified(c,name,v);actual=values(c,name);changed.append(name)
        observed[name]=actual
    return {'observed':observed,'set_commands':changed,'exact_match':observed==desired}

def reset(c,bits,change_width=False,isolate_packed=False):
    name='USB_BIT_DEPTH' if change_width else 'TEST_CORE_BURN';args=[bits,bits] if change_width else [0]
    error=None
    try:c.query(name,*args)
    except Exception as e:error=repr(e) # device re-enumeration can terminate its reply
    start=time.monotonic();last=None
    while time.monotonic()-start<25:
        time.sleep(.5)
        try:
            if values(c,'VERSION')==[3,2,1] and values(c,'USB_BIT_DEPTH')==[bits,bits]:
                if isolate_packed:set_verified(c,'I2S_INPUT_PACKED',[1])
                refresh_audio_backend();inp,out=xvf_endpoints()
                return {'reset_command':name,'arguments':args,'command_error':error,'ready_after_s':time.monotonic()-start,'endpoints':[inp,out]}
        except Exception as e:last=repr(e)
    raise RuntimeError('Reset/re-enumeration failed: '+str(last))

def payload_check(decoded,expected):
    x=expected[:,2:];y=decoded[:,:4]
    # Use one common anchor/offset for all four microphones; no gain fitting.
    anchor=int(np.argmax(np.abs(x[:,0])));anchor=min(anchor,len(x)-64)
    matches=[]
    for at in np.flatnonzero(y[:,0]==x[anchor,0]):
        if at+64<=len(y) and np.array_equal(y[at:at+64],x[anchor:anchor+64]):matches.append(int(at)-anchor)
    if len(matches)!=1:return {'status':'FAIL','reason':'No unique exact four-channel anchor','matching_offsets':matches[:20]}
    offset=matches[0];a=max(0,offset);b=min(len(y),len(x)+offset);xx=x[a-offset:b-offset];yy=y[a:b]
    nonzero=np.flatnonzero(np.any(x!=0,axis=1));complete=(not len(nonzero)) or (a-offset<=nonzero[0] and b-offset>nonzero[-1])
    mismatch=(xx!=yy);diff=yy.astype(np.int64)-xx.astype(np.int64)
    return {'status':'PASS' if not mismatch.any() and complete else 'FAIL','capture_minus_source_offset_samples':offset,
        'compared_frames':len(xx),'compared_mic_samples':int(xx.size),'payload_mismatches':int(mismatch.sum()),
        'per_mic_mismatches':mismatch.sum(axis=0).tolist(),'per_mic_max_abs_error_counts':np.max(np.abs(diff),axis=0).tolist(),
        'per_mic_rms_error_counts':np.sqrt(np.mean(diff.astype(float)**2,axis=0)).tolist(),
        'all_nonzero_source_payload_captured':bool(complete),'pairwise_delay_change_samples':[0]*6 if not mismatch.any() else None,
        'pairwise_delay_scope':'Exact four-channel sample equality implies every pair retains the expected delay; no independent alignment performed.',
        'missing_duplicate_active_payload_samples':0 if not mismatch.any() and complete else None,
        'boundary_source_frames_omitted':len(x)-len(xx),'uncompared_frames_policy':'Only boundary padding; active payload must be complete.'}

class Heartbeat:
    def __init__(self,report):self.report=report;self.stage='initializing';self.case=None;self.start=time.monotonic();self.stop=threading.Event();self.write_lock=threading.Lock()
    def update(self,stage,case=None):self.stage=stage;self.case=case;self.emit()
    def emit(self):
        r={'observed_utc':now(),'stage':self.stage,'case_id':self.case,'elapsed_s':time.monotonic()-self.start,'eta_s':None,'eta_reason':'Configuration/analysis duration not calibrated'}
        with self.write_lock:save(self.report/'hardware_status.json',r)
        print(json.dumps(r),flush=True)
    def loop(self):
        while not self.stop.wait(15):self.emit()

def run(report,safety,attempt,case_plan='core'):
    report=Path(report);ack=json.loads(Path(safety).read_text())
    if ack.get('all_analog_monitors_off_or_disconnected') is not True or not ack.get('user_confirmation_text'):raise RuntimeError('Explicit speaker safety confirmation required')
    inputs=json.loads((report/'inputs_manifest.json').read_text());assert all(c['passed'] for c in inputs['offline_checks'])
    if attempt not in ['initial','retry1']:raise ValueError('At most one diagnosed retry')
    if attempt=='retry1' and not (report/'retry_diagnosis.json').exists():raise RuntimeError('Document diagnosed fix before the single retry')
    if case_plan=='conversation_pair' and attempt!='retry1':raise RuntimeError('Conversation-only plan reserved for the diagnosed retry')
    out=report/('hardware_'+attempt);out.mkdir(exist_ok=False)
    beat=Heartbeat(report);thread=threading.Thread(target=beat.loop,daemon=True);thread.start()
    cache=HashCache();lock=None;owned=False;mutated=False;c=None;initial=None;telem=None;telem_result=None;folder=None;result=None
    restoration={'status':'NOT_NEEDED','hardware_lease_released':False};summary={'started_utc':now(),'attempt':attempt,'cases':[],'speaker_safety':ack,'error':None,'physical_playback_s':0}
    try:
        for name in ['s3_hardware.py','s3_checks.py','s3_prepare.py','README_S3.md']:
            source=SIM/'scripts'/name;(out/'source').mkdir(exist_ok=True);shutil.copy2(source,out/'source'/name)
        save(out/'code_bindings.json',[cache.bind(p) for p in (out/'source').iterdir()])
        assert shutil.disk_usage(report).free>=50*2**30,'50 GiB reserve not met'
        for port in [8765,8766,8767]:
            with socket.socket() as s:
                s.settimeout(.3)
                if s.connect_ex(('127.0.0.1',port))==0:raise RuntimeError(f'Recorder server present on {port}')
        lock=(ROOT/'measurement_app/hardware.lock').open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);owned=True
        beat.update('snapshot_live_configuration');c=Control(out/'owner_commands');identity=c.identify()
        initial={'identity':identity,'settings':{n:values(c,n) for n in STATIC},'observe_only':{n:values(c,n) for n in OBSERVE_ONLY},'usb_bits':identity['USB_BIT_DEPTH']}
        assert initial['usb_bits'] in [[16,16],[24,24]]
        (out/'before_params.txt').write_text(c.query('--dump-params'),encoding='utf-8');save(out/'initial_state.json',initial)
        # Persist original values before the first reset/mutation.
        mutated=True;bits=24;beat.update('prepare_USB24')
        setup_reset=reset(c,bits,change_width=initial['usb_bits']!=[24,24],isolate_packed=attempt=='retry1');save(out/'usb24_preparation.json',setup_reset)
        inp,outdev=xvf_endpoints()
        try:
            sd.check_input_settings(device=inp['index'],channels=2,dtype='int24',samplerate=48000)
            sd.check_output_settings(device=outdev['index'],channels=2,dtype='int24',samplerate=48000)
        except Exception as e:
            save(out/'usb24_negotiation_failure.json',{'error':repr(e),'fallback':'documented PCM16 precision-limited trial'})
            bits=16;reset(c,bits,change_width=True)
        summary['transport_bits']=bits;summary['payload_bits']=bits-1
        plan=[('T1_tagged','T1_tagged'),('T2_front','T2_front'),('T2_left','T2_left'),('T2_right','T2_right'),('T3_ABA_repeat1','T3_ABA'),('T3_ABA_repeat2','T3_ABA')]
        if case_plan=='conversation_pair':plan=plan[-2:]
        summary['case_plan']=case_plan
        for idx,(case_id,input_id) in enumerate(plan):
            if shutil.disk_usage(report).free<50*2**30:raise RuntimeError('Storage reserve crossed')
            case=next(v for v in inputs['cases'] if v['case_id']==input_id);folder=out/case_id;folder.mkdir()
            cc=Control(folder/'commands');beat.update('reset_and_freeze_configuration',case_id)
            reset_receipt=reset(cc,bits,isolate_packed=attempt=='retry1')
            desired_baseline=dict(initial['settings'])
            if attempt=='retry1':
                desired_baseline['I2S_INPUT_PACKED']=[1]
                desired_baseline['PP_AGCGAIN']=initial['settings']['PP_AGCMAXGAIN']
            inherited=restore_values(cc,desired_baseline)
            for n,v in FROZEN.items():set_verified(cc,n,v)
            if attempt=='retry1':set_verified(cc,'PP_AGCGAIN',initial['settings']['PP_AGCMAXGAIN'])
            config={n:values(cc,n) for n in STATIC}
            assert all(config[n]==v for n,v in FROZEN.items())
            assert {n:values(cc,n) for n in OBSERVE_ONLY}==initial['observe_only'],'Reset changed ancillary selected GPIO/GPI configuration; no GPIO setters authorized here'
            save(folder/'configuration.json',{'settings':config,'usb_bits':values(cc,'USB_BIT_DEPTH'),'reset':reset_receipt,'baseline_reapply':inherited,
                'mux_argument_order':['L_PK0','L_PK1','L_PK2','R_PK0','R_PK1','R_PK2'],
                'decoded_output_order':['Category3_MIC0','Category3_MIC1','Category3_MIC2','Category3_MIC3','O0_ASR_auto','O1_postprocessed_auto'],
                'input_logical_order':['zero_far_end','zero_ignored','MIC0','MIC1','MIC2','MIC3'],'ASR_fixed_gain':1,
                'pre_audio_adaptive_observations':{n:values(cc,n) for n in ['AEC_AZIMUTH_VALUES','AEC_SPENERGY_VALUES','PP_AGCGAIN','AEC_AECCONVERGED']},
                'initialization_policy':'Early packed-input isolation and AGC initialized to existing maximum, no AGC tuning' if attempt=='retry1' else 'Original inherited configuration'})
            fmt=case['formats'][str(bits)]
            for item in [fmt['packed'],fmt['expected']]:
                if cache.bind(Path(item['path']),item['sha256'])['status']!='BOUND':raise RuntimeError('Prepared input hash mismatch: '+item['path'])
            payload,fs=sf.read(fmt['packed']['path'],dtype='int32',always_2d=True);payload=payload>>(32-bits)
            expected=np.load(fmt['expected']['path']);assert fs==48000 and payload.shape==(round(case['duration_s']*48000),2)
            result={'case_id':case_id,'input_id':input_id,'status':'STARTING','duration_requested_s':case['duration_s'],'input_sha256':fmt['packed']['sha256'],'attempt_index':idx}
            save(folder/'case_result.json',result)
            telem=create_telemetry_logger(HOST,folder/'telemetry',duration_s=case['duration_s']+12);telem_result=None
            raw=None;meta=None
            try:
                telem.start()
                if not telem.wait_ready(10):raise RuntimeError('Persistent telemetry not ready; no playback started')
                beat.update('physical_replay',case_id)
                raw,meta=capture_native(case['duration_s'],bits=bits,output_counts=payload)
                summary['physical_playback_s']+=meta['captured_frames']/48000
            finally:
                telem.stop('S3_case_audio_closed');telem_result=telem.wait(20)
                if raw is not None:save_counts(folder/'native_packed.wav',raw,48000,bits)
                if meta is not None:save(folder/'capture_metadata.json',meta)
                if telem_result is None:raise RuntimeError('Telemetry owner did not finish; restoration cannot yet access device')
                save(folder/'telemetry_summary.json',telem_result)
            beat.update('input_integrity_gate',case_id)
            decoded,qc=decode_packed(raw,bits);save_counts(folder/'decoded_six.wav',decoded,16000,bits)
            save_counts(folder/'O0.wav',decoded[:,4],16000,bits);save_counts(folder/'O1.wav',decoded[:,5],16000,bits)
            check=payload_check(decoded,expected)
            flags=meta['callback_flags'];nonpriming=[f for f in flags if f['flags'].strip().lower()!='priming output']
            result.update(status='PASS' if check['status']=='PASS' and not qc['marker_error_count'] and not nonpriming and not meta['callback_errors'] else 'FAIL',
                payload=check,framing=qc,callback_flags=flags,callback_errors=meta['callback_errors'],telemetry_status=telem_result['status'],
                capture_frames=meta['captured_frames'],capture_duration_s=meta['captured_frames']/48000)
            save(folder/'case_result.json',result);summary['cases'].append(result);save(out/'hardware_summary.json',summary)
            telem=None
            if result['status']!='PASS':raise RuntimeError('Physical input integrity failed; remaining cases not played: '+case_id)
        summary['status']='BOUNDED_CASES_CAPTURED'
    except BaseException as e:
        summary['status']='BLOCKED';summary['error']=repr(e);(out/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
        if result is not None and result.get('status')=='STARTING':
            result.update(status='FAIL',error=repr(e));save(folder/'case_result.json',result);summary['cases'].append(result)
    finally:
        beat.update('close_handles_and_restore')
        if telem is not None and telem_result is None:
            telem.stop('S3_final_cleanup');telem_result=telem.wait(20)
        safe=telem is None or telem_result is not None
        if mutated and initial and safe:
            try:
                set_verified(c,'I2S_INPUT_PACKED',[0])
                original_bits=initial['usb_bits'][0]
                reset_receipt=reset(c,original_bits,change_width=values(c,'USB_BIT_DEPTH')!=initial['usb_bits'])
                receipt=restore_values(c,initial['settings'])
                after={'identity':c.identify(),'settings':{n:values(c,n) for n in STATIC},'observe_only':{n:values(c,n) for n in OBSERVE_ONLY}}
                (out/'after_params.txt').write_text(c.query('--dump-params'),encoding='utf-8')
                same=after['settings']==initial['settings'] and after['observe_only']==initial['observe_only'] and after['identity']==initial['identity']
                restoration={'status':'PASS' if same else 'FAIL','exact_recorded_configuration_match':same,'readback':after,'reset':reset_receipt,'reapply':receipt,
                    'scope':'Exact exposed static configuration and selected ancillary getters; adaptive beam/AEC/AGC history and counters cannot be restored and were reset as authorized.',
                    'packed_input_disabled':after['identity']['I2S_INPUT_PACKED']==[0],'audio_handles_closed':True,'telemetry_process_closed':safe}
            except BaseException as e:restoration={'status':'FAIL','error':repr(e),'recovery_source':str(out/'initial_state.json'),'warning':'Do not play or resume; inspect current USB width and restore documented settings from initial_state.json with streams closed.'}
        elif mutated:restoration={'status':'FAIL','error':'Telemetry still active; no competing control commands issued'}
        if owned:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        if lock:lock.close()
        restoration['hardware_lease_released']=True;save(out/'restoration.json',restoration)
        summary['ended_utc']=now();summary['elapsed_s']=time.monotonic()-beat.start;summary['restoration_status']=restoration['status']
        save(out/'hardware_summary.json',summary);cache.flush();beat.stop.set();thread.join(2);beat.update('finished_'+summary.get('status','UNKNOWN'))
        print(json.dumps({'status':summary.get('status'),'error':summary['error'],'cases':len(summary['cases']),'playback_s':summary['physical_playback_s'],'restoration':restoration['status']},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',required=True);p.add_argument('--speaker-safety-receipt',required=True);p.add_argument('--attempt',choices=['initial','retry1'],default='initial');p.add_argument('--case-plan',choices=['core','conversation_pair'],default='core');a=p.parse_args();run(a.report,a.speaker_safety_receipt,a.attempt,a.case_plan)
