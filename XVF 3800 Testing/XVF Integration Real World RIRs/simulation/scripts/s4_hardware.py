"""Single-owner finite S4 capture and exact restoration; see README_S4.md."""
import argparse, msvcrt, socket, sys, threading, time, traceback
from s4_common import *
sys.path.insert(0,str(ROOT))
import measurement_app
import numpy as np
import soundfile as sf
import sounddevice as sd
from measurement_app.core import Control, HOST, xvf_endpoints, decode_packed, save_counts, pack_pcm24, unpack_pcm24
from s3_hardware import STATIC, OBSERVE_ONLY, FROZEN, values, set_verified, restore_values, reset
from s4_transport import prepare, payload_check, carrier_chunk
from s4_telemetry import create_telemetry_logger
from s4_restore import restore_exposed

RECIPES={
    'baseline':{},
    'limiter_quarter_power':{'PP_LIMITPLIMIT':[.1175]},
    'limiter_and_agc_headroom':{'PP_LIMITPLIMIT':[.1175],'PP_AGCDESIREDLEVEL':[.001125],'PP_AGCMAXGAIN':[62.5],'PP_AGCGAIN':[62.5]}}

def capture(seconds,payload_counts):
    inp,out=xvf_endpoints()
    for io,dev in [('input',inp),('output',out)]:
        getattr(sd,'check_'+io+'_settings')(device=dev['index'],channels=2,dtype='int24',samplerate=48000)
    total=round(seconds*48000);assert payload_counts.shape==(total,2)
    payload=pack_pcm24(payload_counts);chunks=[];times=[];flags=[];errors=[];position=0;done=threading.Event()
    def callback(indata,outdata,frames,ti,status):
        nonlocal position
        arrival=time.perf_counter_ns()
        try:
            data,take=carrier_chunk(payload,position,frames,total);assert len(data)==len(outdata)
            outdata[:]=data;chunks.append(bytes(indata[:take*6]))
            times.append({'first_native_frame':position,'frames':take,'callback_capacity_frames':frames,
                'host_callback_monotonic_ns':arrival,'host_copy_complete_monotonic_ns':time.perf_counter_ns(),
                'input_adc_time':ti.inputBufferAdcTime,'output_dac_time':ti.outputBufferDacTime,'stream_current_time':ti.currentTime})
            if status:flags.append({'native_frame':position,'flags':str(status)})
            position+=take
            if position>=total:raise sd.CallbackStop
        except sd.CallbackStop:raise
        except BaseException as e:errors.append(repr(e));raise sd.CallbackAbort
    start=time.perf_counter_ns();utc=now()
    with sd.RawStream(samplerate=48000,channels=2,dtype='int24',device=(inp['index'],out['index']),blocksize=0,
        latency=.15,dither_off=True,clip_off=True,callback=callback,finished_callback=done.set) as stream:
        actual={'samplerate':stream.samplerate,'latency':list(stream.latency),'blocksize':stream.blocksize}
        while not done.wait(.1):
            if time.perf_counter_ns()-start>(seconds+15)*1e9:errors.append('Finite capture timeout');stream.abort();break
    raw=unpack_pcm24(b''.join(chunks));end=time.perf_counter_ns()
    return raw,{'requested_seconds':seconds,'captured_frames':len(raw),'container_bits':24,'native_rate_hz':48000,
        'requested_stream_latency_s':.15,'input_device':inp,'output_device':out,'actual_stream':actual,
        'callback_flags':flags,'callback_errors':errors,'start_utc':utc,'start_monotonic_ns':start,'end_monotonic_ns':end,
        'callback_times':times,'timestamps_calibrated_to_acoustics':False,
        'timing_scope':'QPC callback receipt and copy completion are host availability, not DSP sample time. ADC/DAC driver epochs are not assumed host epochs.'}

def code_bindings():
    paths=[SIM/'scripts'/n for n in ['s4_hardware.py','s4_transport.py','s4_telemetry.py','s4_common.py','s4_restore.py','s3_hardware.py']]
    paths+=sorted((SIM/'scripts/s4_native').glob('*'))
    return [bind(p) for p in paths if p.is_file()]

def verified_restoration(path):
    original=read(path)
    if original['status']=='PASS':return
    recovered_path=path.with_name('restoration_recovery.json')
    assert recovered_path.exists(),'Prior unsafe restoration: '+str(path)
    recovered=read(recovered_path);initial=read(path.with_name('initial_state.json'))
    assert recovered['status']=='PASS' and recovered.get('exact_recorded_configuration_match') is True
    bind(path,recovered['original_failure_binding']['sha256'])
    assert recovered['original_failure']==original
    assert all(recovered.get(k) is True for k in ['hardware_lease_released','audio_handles_closed','telemetry_process_closed','packed_input_disabled'])
    assert all(recovered['readback'][k]==initial[k] for k in ['settings','identity','observe_only'])

def run(batch,case_ids,recipe,final=False):
    ack=read(REPORT/'speaker_safety_receipt.json');assert ack['all_analog_monitors_off_or_disconnected'] and ack['user_confirmation_text']
    assert read(REPORT/'transport_regressions.json')['status']=='PASS'
    manifest=read(BANK/'SCENE_MANIFEST.json');assert manifest['validation']['status']=='PASS'
    scenes={s['case_id']:s for s in manifest['scenes']}
    if case_ids==['transport_regression']:
        # The exact S3 tagged fixture is a regression only; it is not a new canonical scene.
        s3=read(SIM/'reports/S3/20260908T214914Z/inputs_manifest.json')
        old=next(s for s in s3['cases'] if s['case_id']=='T1_tagged')
        scenes['transport_regression']={'case_id':'transport_regression','duration_s':old['duration_s'],'historical_formats':old['formats']['24'],'segments':[],
            'canonical_audio':old['float_vector']}
    if final:
        policy=read(REPORT/'OUTPUT_LEVEL_POLICY.json');assert policy['frozen'] and policy['hardware_recipe']==recipe
        assert read(REPORT/'INITIALIZATION_POLICY.json')['frozen']
    assert recipe in RECIPES
    out=REPORT/'hardware'/batch;out.mkdir(parents=True,exist_ok=True)
    if (out/'restoration.json').exists():verified_restoration(out/'restoration.json')
    bindings=code_bindings();code_key=hashlib.sha256(json.dumps([(b['path'],b['sha256']) for b in bindings],sort_keys=True).encode()).hexdigest()
    signature={'code_key':code_key,'recipe':recipe,'final_recipe_capture':final,'scene_manifest_sha256':bind(BANK/'SCENE_MANIFEST.json')['sha256']}
    if (out/'batch_contract.json').exists():assert read(out/'batch_contract.json')==signature,'Incompatible existing batch, preserve and use a new attempt name'
    save(out/'batch_contract.json',signature);save(out/'code_bindings.json',bindings)
    # Keep every executed owner/helper version alongside its binding, so later
    # software fixes cannot erase the code that produced an earlier attempt.
    for b in bindings:
        src=Path(b['path']);dest=out/'source_snapshot'/src.relative_to(SIM/'scripts')
        dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists():shutil.copy2(src,dest)
        bind(dest,b['sha256'])
    pending=[]
    for cid in case_ids:
        assert cid in scenes
        path=out/cid/'case_result.json'
        if path.exists():
            result=read(path)
            if result.get('status')=='PASS' and result.get('code_key')==code_key and result.get('input_scene_sha256')==scenes[cid]['canonical_audio']['sha256']:
                continue
            raise RuntimeError('Existing incomplete/failed attempt retained; diagnose and choose a distinct batch name: '+cid)
        pending.append(cid)
    if not pending:print('All requested compatible captures already complete');return
    # Fail closed after any prior bad restore or corrupt payload. No blind retry.
    for prior in (REPORT/'hardware').glob('*/restoration.json'):verified_restoration(prior)
    for prior in (REPORT/'hardware').glob('*/*/case_result.json'):
        r=read(prior)
        if r.get('status')=='FAIL' and r.get('payload',{}).get('status')=='FAIL':raise RuntimeError('Prior corrupt transport blocks hardware: '+str(prior))
    summary={'batch':batch,'recipe':recipe,'final_recipe_capture':final,'started_utc':now(),'cases':[],'error':None}
    lock=None;owned=False;mutated=False;initial=None;c=None;telem=None;telem_result=None;folder=None;result=None
    restoration={'status':'NOT_NEEDED'}
    with Progress('hardware_'+batch,len(pending)) as progress:
        try:
            check_storage()
            for port in [8765,8766,8767]:
                with socket.socket() as sock:
                    sock.settimeout(.2)
                    if sock.connect_ex(('127.0.0.1',port))==0:raise RuntimeError('Recorder server owns port '+str(port))
            lock=(ROOT/'measurement_app/hardware.lock').open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);owned=True
            c=Control(out/'owner_commands');identity=c.identify()
            initial={'identity':identity,'settings':{n:values(c,n) for n in STATIC},'observe_only':{n:values(c,n) for n in OBSERVE_ONLY},'usb_bits':identity['USB_BIT_DEPTH']}
            assert initial['usb_bits'] in [[16,16],[24,24]];save(out/'initial_state.json',initial)
            baseline_path=REPORT/'HARDWARE_BASELINE.json'
            if baseline_path.exists():baseline=read(baseline_path)
            else:baseline=initial;save(baseline_path,baseline)
            assert baseline['settings']['PP_LIMITPLIMIT']==[.47] and baseline['settings']['PP_AGCDESIREDLEVEL']==[.0045]
            mutated=True;save(out/'usb24_preparation.json',reset(c,24,change_width=initial['usb_bits']!=[24,24],isolate_packed=True))
            for cid in pending:
                check_storage();scene=scenes[cid];folder=out/cid;folder.mkdir()
                ledger=read(REPORT/'physical_ledger.json') if (REPORT/'physical_ledger.json').exists() else {'passes':[]}
                charged=sum(r['charged_playback_s'] for r in ledger['passes'])
                assert len(ledger['passes'])<40 and charged+scene['duration_s']<=2700,'Physical budget reached'
                progress.case=cid;progress.detail='Reset, early packed isolation, static configuration';progress.emit()
                cc=Control(folder/'commands');reset_receipt=reset(cc,24,isolate_packed=True)
                desired=dict(baseline['settings']);desired.update(FROZEN);desired['PP_AGCGAIN']=[125];desired.update(RECIPES[recipe])
                inherited=restore_values(cc,desired)
                # Last setter establishes the same documented current AGC starting value after configuration.
                set_verified(cc,'PP_AGCGAIN',desired['PP_AGCGAIN'])
                config={n:values(cc,n) for n in STATIC};assert config==desired
                assert {n:values(cc,n) for n in OBSERVE_ONLY}==initial['observe_only']
                save(folder/'configuration.json',{'settings':config,'usb_bits':values(cc,'USB_BIT_DEPTH'),'reset':reset_receipt,'baseline_reapply':inherited,
                    'recipe':recipe,'pre_audio_adaptive_observations':{n:values(cc,n) for n in ['AEC_AZIMUTH_VALUES','AEC_SPENERGY_VALUES','PP_AGCGAIN','AEC_AECCONVERGED']},
                    'hidden_state_identical_proven':False,'input_logical_order':['zero_far_end','zero_ignored','MIC0','MIC1','MIC2','MIC3'],
                    'decoded_output_order':['MIC0','MIC1','MIC2','MIC3','O0_ASR_auto','O1_postprocessed_auto']})
                fmt=scene.get('historical_formats') or prepare(scene)
                for item in [fmt['packed'],fmt['expected']]:bind(item['path'],item['sha256'])
                packed,rate=sf.read(fmt['packed']['path'],dtype='int32',always_2d=True);packed>>=8;expected=np.load(fmt['expected']['path']);assert rate==48000
                result={'case_id':cid,'batch':batch,'recipe':recipe,'status':'STARTING','duration_s':scene['duration_s'],
                    'code_key':code_key,'input_scene_sha256':scene['canonical_audio']['sha256'],'packed_input':fmt,'final_recipe_capture':final}
                save(folder/'case_result.json',result)
                telem=create_telemetry_logger(HOST,folder/'telemetry',duration_s=scene['duration_s']+15,rate_hz_per_field=20);telem_result=None
                raw=None;meta=None
                try:
                    telem.start()
                    if not telem.wait_ready(10):raise RuntimeError('All three telemetry fields not ready; no playback')
                    ledger['passes'].append({'batch':batch,'case_id':cid,'started_utc':now(),'charged_playback_s':scene['duration_s'],'status':'STARTED'})
                    save(REPORT/'physical_ledger.json',ledger)
                    progress.detail='Physical packed replay, XVF endpoints only';progress.emit()
                    raw,meta=capture(scene['duration_s'],packed)
                finally:
                    telem.stop('S4_case_audio_closed');telem_result=telem.wait(20)
                    if raw is not None:save_counts(folder/'native_packed.wav',raw,48000,24)
                    if meta is not None:save(folder/'capture_metadata.json',meta)
                    if telem_result is None:raise RuntimeError('Persistent control owner did not close; no competing restoration commands')
                    save(folder/'telemetry_summary.json',telem_result)
                decoded,qc=decode_packed(raw,24);save_counts(folder/'decoded_six.wav',decoded,16000,24)
                save_counts(folder/'O0.wav',decoded[:,4],16000,24);save_counts(folder/'O1.wav',decoded[:,5],16000,24)
                check=payload_check(decoded,expected);flags=[f for f in meta['callback_flags'] if f['flags'].strip().lower()!='priming output']
                audio_passed=check['status']=='PASS' and not qc['marker_error_count'] and not flags and not meta['callback_errors']
                passed=audio_passed and telem_result.get('status')=='PASS'
                result.update(status='PASS' if passed else 'FAIL',payload=check,framing=qc,callback_flags=meta['callback_flags'],callback_errors=meta['callback_errors'],
                    telemetry_status=telem_result.get('status'),audio_integrity_status='PASS' if audio_passed else 'FAIL',capture_duration_s=meta['captured_frames']/48000,
                    output_audio={n:bind(folder/(n+'.wav')) for n in ['O0','O1']},finished_utc=now())
                save(folder/'case_result.json',result);summary['cases'].append(result);save(out/'hardware_summary.json',summary)
                ledger['passes'][-1].update(status=result['status'],captured_frames=meta['captured_frames']);save(REPORT/'physical_ledger.json',ledger)
                telem=None;progress.done+=1;progress.detail='Payload/framing gate '+result['status'];progress.emit()
                if not passed:raise RuntimeError('Transport, driver or mandatory telemetry gate failed: '+cid)
            summary['status']='CAPTURED'
        except BaseException as e:
            summary['status']='BLOCKED';summary['error']=repr(e);(out/'failure.txt').write_text(traceback.format_exc(),encoding='utf-8')
            if result and result['status']=='STARTING':result.update(status='FAIL',error=repr(e));save(folder/'case_result.json',result)
        finally:
            progress.detail='Close handles and restore exact starting exposed state';progress.emit()
            if telem is not None and telem_result is None:telem.stop('S4_final_cleanup');telem_result=telem.wait(20)
            safe=telem is None or telem_result is not None
            if mutated and initial and safe:
                try:
                    set_verified(c,'I2S_INPUT_PACKED',[0])
                    rr=reset(c,initial['usb_bits'][0],change_width=values(c,'USB_BIT_DEPTH')!=initial['usb_bits'])
                    reapplied=restore_exposed(c,initial['settings'])
                    after={'identity':c.identify(),'settings':{n:values(c,n) for n in STATIC},'observe_only':{n:values(c,n) for n in OBSERVE_ONLY}}
                    same=after['identity']==initial['identity'] and after['settings']==initial['settings'] and after['observe_only']==initial['observe_only']
                    restoration={'status':'PASS' if same else 'FAIL','exact_recorded_configuration_match':same,'readback':after,'reset':rr,'reapply':reapplied,
                        'scope':'Exposed static and selected ancillary state only. Adaptive history/counters cannot be restored and were reset.',
                        'packed_input_disabled':after['identity']['I2S_INPUT_PACKED']==[0],'audio_handles_closed':True,'telemetry_process_closed':safe}
                except BaseException as e:restoration={'status':'FAIL','error':repr(e),'recovery_source':str(out/'initial_state.json')}
            elif mutated:restoration={'status':'FAIL','error':'Telemetry owner still active; restoration commands withheld'}
            if owned:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
            if lock:lock.close()
            restoration['hardware_lease_released']=True;save(out/'restoration.json',restoration)
            summary.update(ended_utc=now(),elapsed_s=time.monotonic()-progress.start,restoration_status=restoration['status']);save(out/'hardware_summary.json',summary)
    print(json.dumps({'status':summary.get('status'),'error':summary['error'],'cases':len(summary['cases']),'restoration':restoration['status']},indent=2))
    if summary.get('status')!='CAPTURED' or restoration['status']!='PASS':raise RuntimeError('S4 hardware batch blocked; inspect saved evidence')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--batch',required=True);p.add_argument('--cases',nargs='+',required=True);p.add_argument('--recipe',choices=list(RECIPES),default='baseline');p.add_argument('--final',action='store_true')
    a=p.parse_args();run(a.batch,a.cases,a.recipe,a.final)
