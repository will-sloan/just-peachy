"""Execute/resume only the selected S1 twelve; one coordinator writes receipts."""
import os
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[key]='1'
import argparse, concurrent.futures, hashlib, json, multiprocessing, shutil, sys, threading, time, traceback
from pathlib import Path
import numpy as np
import psutil
import soundfile as sf
from s0_common import SIM,ROOT,HashCache,read,save,now
from s1_signal import *

def canonical_json_hash(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def tidy(value):
    if isinstance(value,np.ndarray):return value.tolist()
    if isinstance(value,np.generic):return value.item()
    if isinstance(value,dict):return {k:tidy(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [tidy(v) for v in value]
    return value

def process(row,cfg):
    start=time.monotonic();p=Path(row['absolute_run_path'])/'02_raw/pass_01_amplified'
    y,fs=sf.read(p/'microphones_4ch.wav',dtype='float64',always_2d=True)
    if fs!=FS or y.shape!=(350647,4) or not np.isfinite(y).all():raise ValueError('Canonical WAV data contract failed')
    source=source_at_16k(p/'excitation_original.wav',cfg)
    timing_sidecar=read(p/'signal_timing.json');playback=read(p/'playback.json');request=read(Path(row['absolute_run_path'])/'request.json')
    expected=timing_sidecar['signals'][request['excitation_id']]
    if expected['sweep_onset_sec']!=3 or expected['sweep_end_sec']!=13 or playback['requested_gain_db']!=-6 or playback['same_clock_as_capture'] is not False:
        raise ValueError('Recorded timing/playback contract mismatch')
    prior=read(p/'quality.json')['acoustic_markers']['markers'];hints=[m['sample']/FS for m in prior]
    selected,zero,alternate,timing=choose_timing(y,source,hints,cfg)
    noise=noise_metrics(y,selected,cfg)
    candidate,core,processed,bf,metrics,power=candidate_response(selected,noise,cfg)
    residual=reconstruct(selected,processed,bf,cfg)
    zero_noise=noise_metrics(y,zero,cfg);_,zero_core,zero_processed,zero_bf,zero_metrics,_=candidate_response(zero,zero_noise,cfg)
    zero_residual=reconstruct(zero,zero_processed,zero_bf,cfg)
    cross=None;cross_wave=None
    if row['pilot_order'] in cfg['crosscheck_pilot_orders']:cross_wave,cross=fd_crosscheck(selected,bf,core,cfg)
    # A fresh pure numerical rerun checks deterministic regeneration; no metadata or cached result substitutes it.
    again=extract_variant(y,source,timing,selected['ppm'],cfg)
    regenerated,_,_,_,_,_=candidate_response(again,noise,cfg)
    payload=candidate.astype('<f4').tobytes();regen=regenerated.astype('<f4').tobytes()
    regeneration={'candidate_float32_sha256':hashlib.sha256(payload).hexdigest(),'regenerated_float32_sha256':hashlib.sha256(regen).hexdigest(),
                  'byte_identical':payload==regen,'scope':'Fresh numerical regeneration of same inputs/configuration; not a new acoustic take'}
    if not regeneration['byte_identical']:raise RuntimeError('Deterministic regeneration failed')
    flags=[]
    if timing['status'].startswith('TIMING_UNRESOLVED'):flags.append('MARKER_SWEEP_CLOCK_DISAGREEMENT')
    if timing['status'].startswith('ZERO_DRIFT'):flags.append('ZERO_DRIFT_WITH_UNRESOLVED_WORKING_INTERVAL')
    if noise['marker_tail_or_nonstationarity_warning']:flags.append('PRE_SWEEP_GAP_EXCESS_OR_MARKER_TAIL')
    if max(noise['stationarity_three_block_power_range_db'])>6:flags.append('PRE_NOISE_NONSTATIONARITY')
    if not metrics['band_support_found']:flags.append('NO_COMMON_SUPPORTED_OCTAVE')
    flags += ['FINITE_BAND_AND_TAIL','FIRST_ENERGY_NOT_CALIBRATED_DIRECT_PATH','NO_INDEPENDENT_ACOUSTIC_VALIDATION']
    status='PROVISIONAL_TIMING_REVIEW' if timing['status'].startswith('TIMING_UNRESOLVED') else 'PROVISIONAL_LIMITED_BAND_TAIL'
    if not metrics['band_support_found']:status='HOLD_INPUT_OR_PROCESSING'
    start_crop=metrics['common_crop_start_sample'];tail=metrics['common_taper_start_sample'];end=metrics['common_crop_end_sample']
    sensitivity=[]
    for delta in [-.01,.01]:
        a=max(0,start_crop+round(delta*FS));energy=np.sum(core[a:end]**2,axis=0)
        sensitivity.append({'common_start_delta_sec':delta,'untapered_energy_change_db':db10(energy/(np.sum(core[start_crop:end]**2,axis=0)+1e-30)).tolist()})
    for delta in [-.05,.05]:
        b=min(len(core),max(start_crop+1,end+round(delta*FS)));energy=np.sum(core[start_crop:b]**2,axis=0)
        sensitivity.append({'common_end_delta_sec':delta,'untapered_energy_change_db':db10(energy/(np.sum(core[start_crop:end]**2,axis=0)+1e-30)).tolist()})
    freq=fft.rfftfreq(65536,1/FS);H=fft.rfft(core,65536,axis=0);C=fft.rfft(processed,65536,axis=0)
    spectrum_ix=np.arange(0,len(freq),8)
    plot={'core':core.astype('float32'),'processed':processed.astype('float32'),'block_power':power,
          'frequency_hz':freq[spectrum_ix],'response_db':db20(H[spectrum_ix]),'candidate_db':db20(C[spectrum_ix]),
          'noise_frequency_hz':noise['psd_frequencies_hz'],'noise_psd_db':db10(noise['psd_fs2_per_hz']),
          'residual_frequency_hz':residual['frequency_hz'],'observed_psd_db':db10(residual['observed_psd']),
          'residual_psd_db':db10(residual['residual_psd'])}
    small_noise={k:v for k,v in noise.items() if not k.startswith('psd_')}
    small_residual={k:v for k,v in residual.items() if k not in ['frequency_hz','observed_psd','residual_psd']}
    small_zero_residual={k:v for k,v in zero_residual.items() if k not in ['frequency_hz','observed_psd','residual_psd']}
    details={'run_id':row['run_id'],'pilot_order':row['pilot_order'],'status':status,'flags':flags,
        'timing':timing,'gain_convention':cfg['gain_convention'],'capture_domain':cfg['capture_domain'],
        'full_response_origin':{'time_zero_sample':len(selected['inverse'])-1,'sample_rate_hz':FS,
            'time_axis_sec':'(sample_index - time_zero_sample)/16000; relative to analysis crop and source-sweep reference',
            'capture_crop_start_sample':selected['capture_crop_start_sample'],'capture_crop_stop_sample':selected['capture_crop_stop_sample'],
            'beta_landmark_sec':selected['beta_landmark_sec'],'anchor_sec':cfg['analysis_anchor_sec'],
            'absolute_propagation_or_device_delay_separately_known':False,
            'candidate_time_zero_relative_to_full_core_sec':start_crop/FS},
        'inverse_calibration':selected['calibration'],'noise':small_noise,'response_metrics':metrics,'reconstruction':small_residual,
        'no_drift_comparison':{'ppm':0,'reconstruction':small_zero_residual,'pairwise_delays':zero_metrics['pairwise_delays'],
            'selected_minus_zero_pair_delays_samples':[a['delay_samples_j_minus_i']-b['delay_samples_j_minus_i'] for a,b in zip(metrics['pairwise_delays'],zero_metrics['pairwise_delays'])]},
        'regularized_frequency_domain_crosscheck':cross,'common_window_sensitivity':sensitivity,'regeneration':regeneration,
        'allowed_uses':['Provisional method review','Declared-band/finite-tail diagnostics; later use only after policy review'],
        'qualified_rir_available':False,'simulation_ready':False,'physical_replay_qualified':False,'processing_sec':time.monotonic()-start,
        'worker_peak_rss_bytes':psutil.Process().memory_info().rss,
        'original_capture_status':row['original_status'],'capture_audit_pass':row['capture_audit_pass'],
        'local_binding_status':'BOUND','exception':None}
    return {'metrics':tidy(details),'arrays':{'full_ess_diagnostic':selected['full'].astype('float32'),
        'candidate_4ch':candidate.astype('float32'),'alternate_clock_full_diagnostic':alternate['full'].astype('float32') if selected['ppm']!=alternate['ppm'] else zero['full'].astype('float32'),
        **({'fd_crosscheck_4ch':cross_wave.astype('float32')} if cross_wave is not None else {})},'plot_data':plot}

class Monitor:
    def __init__(self,report,total,cfg):
        self.report=Path(report);self.total=total;self.cfg=cfg;self.done=0;self.failed=0;self.detail='';self.start=time.monotonic()
        self.stop=threading.Event();self.peak_rss=0;self.min_available=float('inf');self.min_disk=float('inf');self.resource_failure=None
    def sample(self,state='RUNNING'):
        process=psutil.Process();children=process.children(recursive=True);rss=process.memory_info().rss
        for p in children:
            try:rss+=p.memory_info().rss
            except psutil.NoSuchProcess:pass
        available=psutil.virtual_memory().available;free=shutil.disk_usage(str(SIM)).free
        self.peak_rss=max(self.peak_rss,rss);self.min_available=min(self.min_available,available);self.min_disk=min(self.min_disk,free)
        if rss>self.cfg['task_ram_cap_gib']*1024**3 or available<self.cfg['min_available_ram_gib']*1024**3 or free<self.cfg['free_disk_floor_gib']*1024**3:
            self.resource_failure='Configured memory or disk guard crossed; stop submitting jobs'
        elapsed=time.monotonic()-self.start;rate=self.done/elapsed if self.done else 0
        row={'stage':'S1_pilot','status':state,'updated_utc':now(),'completed':self.done,'failed':self.failed,'total':self.total,
             'elapsed_sec':elapsed,'records_per_minute':rate*60,'eta_sec':(self.total-self.done)/rate if rate else None,
             'rss_process_tree_bytes':rss,'available_ram_bytes':available,'free_output_disk_bytes':free,'cpu_percent_system':psutil.cpu_percent(),
             'detail':self.detail,'resource_failure':self.resource_failure}
        save(self.report/'status.json',row)
        with (self.report/'heartbeat.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row)+'\n')
    def __enter__(self):
        self.sample()
        def loop():
            while not self.stop.wait(15):self.sample()
        self.thread=threading.Thread(target=loop,daemon=True);self.thread.start();return self
    def __exit__(self,typ,value,tb):
        self.stop.set();self.thread.join();self.sample('FAILED' if typ else 'COMPLETE')

def execute(report,derived,limit,workers):
    report=Path(report);derived=Path(derived);cfg=read(report/'extraction_config.json');cache=HashCache()
    if read(report/'synthetic_results.json')['status']!='PASSED':raise RuntimeError('Synthetic gate has not passed')
    if not 1<=limit<=12 or not 1<=workers<=min(4,cfg['workers_max']):raise ValueError('Only bounded selected 12 and <=4 workers permitted')
    policy=read(report/'qc_policy.json')
    if policy['status']=='DEVELOPMENT_INITIAL_BEFORE_REAL_PILOT_SCORING':
        policy.update(status='DEVELOPMENT_ACTIVE_SYNTHETIC_GATE_PASSED',synthetic_gate_sha256=sha(report/'synthetic_results.json'),first_real_scoring_authorized_utc=now())
        save(report/'qc_policy.json',policy)
    codes=[cache.bind(Path(__file__).parent/n) for n in ['s1_signal.py','s1_run.py','s0_common.py']]
    codekey=canonical_json_hash([{'path':x['path'],'sha256':x['sha256']} for x in codes])
    selected=read(report/'selected_pilot_manifest.json')['recordings'];active={r['run_id'] for r in read(report/'active_campaign_manifest.json')['recordings']}
    rows=selected[:limit];jobs=[];resumed=[]
    for row in rows:
        if row['run_id'] not in active or row['room_table']=='Loeb Caf':raise ValueError('Out-of-scope recording')
        for f in row['s1_file_bindings']:
            if cache.bind(f['path'],f['sha256'])['status']!='BOUND':raise ValueError('Input binding changed: '+f['path'])
        key=canonical_json_hash({'inputs':[(f['path'],f['sha256']) for f in row['s1_file_bindings']],
             'config':cfg,'qc_policy':policy,'code_sha256':codekey,'scope':sha(report/'scope_and_room_context.v3.json')})
        receipt=report/'records'/row['run_id']/'metrics.json'
        if receipt.exists():
            old=read(receipt)
            if old.get('resume_key')==key and old.get('exception') is None and all(cache.bind(a['path'],a['sha256'])['status']=='BOUND' for a in old.get('outputs',[])):
                resumed.append(row['run_id']);continue
        jobs.append((row,key))
    cache.flush();started=time.monotonic();start_utc=now();execution=[]
    with Monitor(report,len(jobs),cfg) as monitor:
        if monitor.resource_failure:raise RuntimeError(monitor.resource_failure)
        # Bounded submission batches prevent an unbounded queue; the coordinator is the only writer.
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers,mp_context=multiprocessing.get_context('spawn')) as pool:
            for batch_start in range(0,len(jobs),workers):
                if monitor.resource_failure:raise RuntimeError(monitor.resource_failure)
                batch=jobs[batch_start:batch_start+workers]
                futures={pool.submit(process,row,cfg):(row,key) for row,key in batch}
                for future in concurrent.futures.as_completed(futures):
                    row,key=futures[future];recorddir=report/'records'/row['run_id'];recorddir.mkdir(parents=True,exist_ok=True)
                    attemptroot=derived/row['run_id'];attemptroot.mkdir(parents=True,exist_ok=True)
                    number=len(list(attemptroot.glob('attempt_*')))+1;attempt=attemptroot/f'attempt_{number:03d}';attempt.mkdir()
                    try:
                        result=future.result();details=result['metrics'];outputs=[]
                        for name,array in result['arrays'].items():
                            path=attempt/(name+'.wav');sf.write(path,array,FS,subtype='FLOAT',format='WAV')
                            outputs.append({'role':name,'path':str(path),'sha256':sha(path),'bytes':path.stat().st_size,
                                            'sample_rate_hz':FS,'channels':['MIC0','MIC1','MIC2','MIC3'],'format':'WAV FLOAT32','frames':len(array)})
                        np.savez_compressed(attempt/'plot_data.npz',**result['plot_data'])
                        details.update(resume_key=key,code_bindings=codes,extraction_config_sha256=sha(report/'extraction_config.json'),
                           qc_policy_sha256=sha(report/'qc_policy.json'),scope_overlay_sha256=sha(report/'scope_and_room_context.v3.json'),
                           inputs=row['s1_file_bindings'],outputs=outputs,plot_data_path=str(attempt/'plot_data.npz'),attempt_number=number)
                        save(attempt/'metrics.json',details);save(recorddir/'metrics.json',details)
                        execution.append({'run_id':row['run_id'],'status':details['status'],'processing_sec':details['processing_sec']})
                        print(f'{monitor.done+1}/{len(jobs)} {row["run_id"]}: {details["status"]}; {details["processing_sec"]:.2f}s; clock {details["timing"]["selected_ppm"]:.2f} ppm; band {details["response_metrics"]["supported_candidate_band_hz"]}; tail {details["response_metrics"]["candidate_duration_sec"]:.3f}s',flush=True)
                    except Exception as exc:
                        monitor.failed+=1;details={'run_id':row['run_id'],'pilot_order':row['pilot_order'],'status':'HOLD_INPUT_OR_PROCESSING',
                            'exception':type(exc).__name__+': '+str(exc),'traceback':traceback.format_exc(),'resume_key':key,'simulation_ready':False,'outputs':[]}
                        save(attempt/'failure.json',details);save(recorddir/'metrics.json',details);execution.append(details)
                        print('FAILED '+row['run_id']+': '+str(exc),flush=True)
                    monitor.done+=1;monitor.detail=row['run_id']
                    elapsed=time.monotonic()-started;rate=monitor.done/elapsed
                    print(f'Elapsed {elapsed:.1f}s, {rate*60:.2f} records/min, estimated remaining {(len(jobs)-monitor.done)/rate:.1f}s',flush=True)
    bytes_derived=sum(p.stat().st_size for p in derived.rglob('*') if p.is_file())
    if bytes_derived>cfg['scratch_cap_gib']*1024**3:raise RuntimeError('Derivative storage exceeded S1 cap')
    run={'started_utc':start_utc,'finished_utc':now(),'elapsed_sec':time.monotonic()-started,'workers':workers,'processed_this_invocation':len(jobs),'resumed_ids':resumed,
        'results':execution,'peak_process_tree_rss_bytes':monitor.peak_rss,'minimum_available_ram_bytes':monitor.min_available,
        'minimum_free_disk_bytes':monitor.min_disk,'derived_bytes':bytes_derived,'failed':monitor.failed,'code_bindings':codes}
    save(report/('execution_'+str(time.time_ns())+'.json'),run);cache.flush()
    return 0 if not monitor.failed else 2

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',required=True);p.add_argument('--derived',required=True);p.add_argument('--limit',type=int,default=12);p.add_argument('--workers',type=int,default=4)
    a=p.parse_args();raise SystemExit(execute(a.report,a.derived,a.limit,a.workers))
