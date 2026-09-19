"""Bounded captured S3 metrics/figures; no device access or signal repair."""
import argparse,csv,json,shutil
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import correlate,correlation_lags
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from s0_common import read,save,now

FS=16000
FIELDS=['AEC_AZIMUTH_VALUES','AEC_SPENERGY_VALUES']

def percentiles(a):
    a=np.asarray(a,float)
    return {'n':len(a),'p50':float(np.median(a)) if len(a) else None,'p95':float(np.percentile(a,95)) if len(a) else None,'max':float(np.max(a)) if len(a) else None}

def db(v):return float(20*np.log10(max(float(v),1e-15)))

def signal_stats(y,mask,bits):
    z=y[mask]
    return {'samples':len(z),'rms_dbfs':db(np.sqrt(np.mean(z*z))) if len(z) else None,
        'peak_dbfs':db(np.max(np.abs(z))) if len(z) else None,
        'rail_samples':int(np.count_nonzero(np.abs(z)>=1-2.**(2-bits))) if len(z) else None,
        'floor_dbfs':-300,'definition':'Unweighted digital full-scale amplitudes; -300 dBFS is display floor for exact silence. Rail is >= largest positive payload magnitude.'}

def output_lag(y,x):
    c=correlate(y,x,method='fft');lags=correlation_lags(len(y),len(x));ok=(lags>=0)&(lags<=4000)
    scores=np.abs(c[ok]);ls=lags[ok];lag=int(ls[np.argmax(scores)])
    xx=x[:len(x)-lag] if lag else x;yy=y[lag:]
    rho=float(np.dot(xx,yy)/(np.linalg.norm(xx)*np.linalg.norm(yy)+1e-30))
    close=ls[scores>=.99*np.max(scores)]
    return {'lag_samples':lag,'lag_ms':lag/FS*1000,'normalized_correlation':rho,
        'near_peak_span_samples':int(close.max()-close.min()),'resolution_ms':1000/FS,
        'definition':'Approximate output vs recaptured MIC0 ABSOLUTE correlation peak, lag search 0..250 ms; signed coefficient retained and no audio polarity changes. Nonlinear DSP and beam steering can change the waveform. Not absolute device latency.'}

def analyze_case(folder,definition):
    result=read(folder/'case_result.json');meta=read(folder/'capture_metadata.json');telemetry=read(folder/'telemetry_summary.json')
    bits=result['framing']['container_bits'];y,fs=sf.read(folder/'decoded_six.wav',always_2d=True,dtype='float64');assert fs==FS
    raw,_=sf.read(folder/'native_packed.wav',always_2d=True,dtype='int32')
    offset=result['payload']['capture_minus_source_offset_samples'];startup=result['framing']['startup_frames_excluded']
    sample_source=(np.arange(len(y))-offset)/FS
    cb=meta['callback_times'];frames=np.array([c['first_native_frame'] for c in cb]);cbtimes=np.array([c['host_callback_monotonic_ns'] for c in cb],dtype=np.int64);t0=int(cbtimes[0])
    def availability(nativeframe):
        i=int(np.clip(np.searchsorted(frames,nativeframe,side='right')-1,0,len(cb)-1));return int(cbtimes[i])
    rows=[json.loads(l) for l in (folder/'telemetry/received_telemetry.jsonl').read_text().splitlines()]
    field={}
    for name in FIELDS:
        rr=[r for r in rows if r['command']==name];v=np.asarray([r['values'] for r in rr],float)
        times=np.array([r['response_end_monotonic_ns'] for r in rr],dtype=np.int64)
        holds=np.all(v[1:]==v[:-1],axis=1);run=longest=0
        for hold in holds:run=run+1 if hold else 0;longest=max(longest,run)
        field[name]={**telemetry['per_field'][name],'identical_adjacent_arrays':int(holds.sum()),'adjacent_comparisons':len(holds),'longest_held_array_intervals':longest,
            'transaction_duration_ms':percentiles([(r['response_end_monotonic_ns']-r['logical_request_start_monotonic_ns'])/1e6 for r in rr]),
            'line_delivery_after_response_ms':percentiles([(r['host_line_arrival_monotonic_ns']-r['response_end_monotonic_ns'])/1e6 for r in rr]),
            'request_attempts_total':sum(r['attempts'] for r in rr),'read_failures':sum(not r['parse_ok'] for r in rr),
            'held_value_interpretation':'Repeated host reads are not independent DSP updates.'}
    azrows=[r for r in rows if r['command']==FIELDS[0]];erows=[r for r in rows if r['command']==FIELDS[1]]
    azt=np.array([r['response_end_monotonic_ns'] for r in azrows],np.int64);et=np.array([r['response_end_monotonic_ns'] for r in erows],np.int64)
    az=np.rad2deg(np.asarray([r['values'] for r in azrows],float));energy=np.asarray([r['values'] for r in erows],float)
    outputmetrics={};turns=[]
    for index,label in [(4,'O0'),(5,'O1')]:
        lags=[];speech_mask=np.zeros(len(y),bool)
        for seg in definition['segments']:
            if seg['kind']!='utterance':continue
            a=max(0,seg['source_start_sample']+offset);b=min(len(y),seg['convolution_stop_sample']+offset+4000)
            lag=output_lag(y[a:b,index],y[a:b,0]);lags.append(lag)
            start=seg['source_start_sample']+offset+lag['lag_samples'];stop=seg['convolution_stop_sample']+offset+lag['lag_samples']
            speech_mask[max(0,start):min(len(y),stop)]=True
        if not lags:
            speech_mask=(sample_source>=2)&(sample_source<6)
        silence_mask=np.ones(len(y),bool)
        for seg in definition['segments']:
            a=seg['source_start_sample']/FS-.5;b=seg.get('convolution_stop_sample',seg['source_stop_sample'])/FS+.5
            silence_mask&=~((sample_source>=a)&(sample_source<b))
        outputmetrics[label]={'whole_capture':signal_stats(y[:,index],np.ones(len(y),bool),bits),'source_support_plus_estimated_processing_delay':signal_stats(y[:,index],speech_mask,bits),
            'silence_outside_support_with_500ms_guard':signal_stats(y[:,index],silence_mask,bits),'per_utterance_processing_delay':lags,
            'max_adjacent_step_fs':float(np.max(np.abs(np.diff(y[:,index])))),'continuity_scope':'No independent processed-output counter exists. Input continuity is exact; isolated processed waveform steps alone cannot prove a transport discontinuity.'}
    for seg in definition['segments']:
        if seg['kind']!='utterance':continue
        write_start=availability(seg['source_start_sample']*3)
        receive_start=availability(startup+3*(seg['rir_expected_significant_onset_sample']+offset))
        receive_end=availability(startup+3*(seg['convolution_stop_sample']+offset))
        amask=(azt>=receive_start)&(azt<=receive_end);emask=(et>=receive_start)&(et<=receive_end)
        # Coarse, pre-described endfire sectors, not +/-5-degree accuracy acceptance.
        role=seg['rir_role'];sector=(az[:,3]>120) if role=='left' else (az[:,3]<60) if role=='right' else ((az[:,3]>=60)&(az[:,3]<=120))
        previous_energy=np.searchsorted(et,azt,side='right')-1;valid=previous_energy>=0;safe_idx=np.maximum(0,previous_energy)
        gate=valid&(energy[safe_idx,3]>0)&((azt-et[safe_idx])<=100_000_000)
        candidates=np.flatnonzero((azt>=write_start)&(azt<=receive_end)&sector&gate)
        first=int(candidates[0]) if len(candidates) else None
        atstart=int(np.searchsorted(azt,write_start,side='right')-1)
        already_matching=atstart>=0 and bool(sector[atstart]&gate[atstart])
        first_energy=et[(et>=write_start)&(et<=receive_end)&(energy[:,3]>0)]
        turns.append({**seg,'source_write_callback_s':(write_start-t0)/1e9,'recaptured_onset_containing_callback_s':(receive_start-t0)/1e9,
            'recaptured_support_end_containing_callback_s':(receive_end-t0)/1e9,'native_angle_samples':int(amask.sum()),
            'native_auto_angle_median_deg':float(np.median(az[amask,3])) if amask.any() else None,
            'native_auto_angle_p10_p90_deg':np.percentile(az[amask,3],[10,90]).tolist() if amask.any() else None,
            'auto_energy_median_vendor_units':float(np.median(energy[emask,3])) if emask.any() else None,'positive_auto_energy_samples':int(np.count_nonzero(energy[emask,3]>0)),
            'first_positive_energy_after_source_write_s':float((first_energy[0]-write_start)/1e9) if len(first_energy) else None,
            'first_energized_sector_after_source_write_s':float((azt[first]-write_start)/1e9) if first is not None else None,
            'sector_already_matching_at_source_write':already_matching,
            'lag_interpretation':'Host receipt lag from callback writing source-file boundary; includes queued playback and unknown phonetic onset. Not device reaction latency or accuracy; fields paired causally by last completed energy read <=100ms old, not atomically.'})
    framecount_ok=sum(c['frames'] for c in cb)==meta['captured_frames'] and all(cb[i]['first_native_frame']==cb[i-1]['first_native_frame']+cb[i-1]['frames'] for i in range(1,len(cb)))
    runtime={'case_id':result['case_id'],'transport_status':result['status'],'input_id':result['input_id'],'input_hash':result['input_sha256'],'duration_requested_s':definition['duration_s'],
        'decoded_duration_s':len(y)/FS,'transport':result['payload'],'framing':result['framing'],'preframing_all_zero':bool(np.all(raw[:startup]==0)),
        'duplex_input_offset_from_native_start_samples_16k':offset+startup/3,'duplex_input_offset_from_native_start_ms':(offset+startup/3)/FS*1000,
        'offset_definition':'Exact input waveform offset in captured stream sample indexing, including host queues/startup. Not calibrated board delay.',
        'callback':{'count':len(cb),'frame_counts_contiguous':framecount_ok,'gap_ms':percentiles(np.diff(cbtimes)/1e6),
            'callback_block_duration_ms':percentiles([c['frames']/48 for c in cb]),'flags':meta['callback_flags'],'errors':meta['callback_errors'],
            'adc_dac_timestamp_limitation':'WDM-KS ADC/DAC timestamps start at zero and track sample counters while currentTime is QPC. They cannot provide a calibrated common host epoch. Host callback availability only.',
            'max_frame_availability_window_ms':max(c['frames'] for c in cb)/48},
        'microphones':[signal_stats(y[:,j],np.ones(len(y),bool),bits) for j in range(4)],'outputs':outputmetrics,
        'O0_O1_bit_identical':bool(np.array_equal(y[:,4],y[:,5])),'telemetry_status':telemetry['status'],'telemetry':field,
        'native_retry_responses':telemetry['native_result']['retry_responses'],'telemetry_retry_interpretation':'Documented pending replies drained successfully, not failed measurements.',
        'turns':turns,'configuration':read(folder/'configuration.json')['settings'],'host_callback_t0_ns':t0}
    return runtime,{'y':y,'source_s':sample_source,'az':az,'az_host_s':(azt-t0)/1e9,'energy':energy,'energy_host_s':(et-t0)/1e9,'cb':cb,'t0':t0}

def write_csv(path,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)

def run(report,hardware):
    report=Path(report);hardware=Path(hardware);defs=read(report/'inputs_manifest.json');summary=read(hardware/'hardware_summary.json')
    assert summary['status']=='BOUNDED_CASES_CAPTURED';assert read(hardware/'restoration.json')['status']=='PASS'
    target=report/'analysis';target.mkdir(exist_ok=True);figs=target/'figures';figs.mkdir(exist_ok=True)
    results=[];data={};sources=[(hardware,c) for c in summary['cases']]
    if hardware.name=='hardware_retry1':
        original=read(report/'hardware_initial/hardware_summary.json')
        sources=[(report/'hardware_initial',c) for c in original['cases'] if not c['case_id'].startswith('T3')]+sources
    for parent,case in sources:
        definition=next(d for d in defs['cases'] if d['case_id']==case['input_id']);r,d=analyze_case(parent/case['case_id'],definition);r['attempt']=parent.name;results.append(r);data[r['case_id']]=d
    repetitions=[r for r in results if r['case_id'].startswith('T3')]
    repeat={'n':2,'input_hash_equal':repetitions[0]['input_hash']==repetitions[1]['input_hash'],
        'configuration_equal':repetitions[0]['configuration']==repetitions[1]['configuration'],
        'O0_speech_rms_delta_db':repetitions[1]['outputs']['O0']['source_support_plus_estimated_processing_delay']['rms_dbfs']-repetitions[0]['outputs']['O0']['source_support_plus_estimated_processing_delay']['rms_dbfs'],
        'O1_speech_rms_delta_db':repetitions[1]['outputs']['O1']['source_support_plus_estimated_processing_delay']['rms_dbfs']-repetitions[0]['outputs']['O1']['source_support_plus_estimated_processing_delay']['rms_dbfs'],
        'per_turn_angle_median_delta_deg':[b['native_auto_angle_median_deg']-a['native_auto_angle_median_deg'] for a,b in zip(repetitions[0]['turns'],repetitions[1]['turns'])],
        'per_turn_host_sector_lag_delta_s':[(b['first_energized_sector_after_source_write_s']-a['first_energized_sector_after_source_write_s']) if a['first_energized_sector_after_source_write_s'] is not None and b['first_energized_sector_after_source_write_s'] is not None else None for a,b in zip(repetitions[0]['turns'],repetitions[1]['turns'])],
        'scope':'Two same-vector fresh-state repeats, descriptive differences only; no population CI or adaptive DSP bit-repeat expectation.'}
    if hardware.name=='hardware_retry1':
        earlier=read(report/'initial_analysis_metrics.json')['cases'][-2:]
        for r in earlier:r['attempt']='hardware_initial'
        results=results[:4]+earlier+results[4:]
    aggregate={'schema_version':'jp_s3_analysis_v1','metric_definition_version':'s3-v1','created_utc':now(),'cases':results,'repeat':repeat,
        'repeat_comparison_attempt':hardware.name,'original_repeat_comparison':read(report/'initial_analysis_metrics.json')['repeat'] if hardware.name=='hardware_retry1' else None,
        'total_compared_mic_samples':sum(r['transport']['compared_mic_samples'] for r in results),'total_payload_mismatches':sum(r['transport']['payload_mismatches'] for r in results),
        'speech_output_rail_samples':{s:sum(r['outputs'][s]['whole_capture']['rail_samples'] for r in results if r['case_id']!='T1_tagged') for s in ['O0','O1']},
        'telemetry_policy':'Two mandatory fields streamed with transaction bounds. Available optional selected-azimuth was included as one preflight probe only; no third-field trajectory from the qualified two-field adapter.',
        'timing_limit':'Host callback blocks are up to 150ms; absolute device/telemetry offset unresolved. No fitted telemetry shift. Processed-audio correlation lag is relative to recaptured MIC0, not full-stack latency.',
        'storage_free_gib':{d:shutil.disk_usage(d+':/').free/2**30 for d in ['C','G']}}
    save(report/'analysis_metrics.json',aggregate)
    table=[]
    for r in results:
        row={'case_id':r['case_id'],'attempt':r['attempt'],'status':r['transport_status'],'payload_mismatches':r['transport']['payload_mismatches'],'compared_mic_samples':r['transport']['compared_mic_samples'],
            'common_stream_offset_ms':r['duplex_input_offset_from_native_start_ms'],'decoded_duration_s':r['decoded_duration_s'],'startup_zero_native_frames':r['framing']['startup_frames_excluded'],
            'azimuth_read_rate_hz':r['telemetry'][FIELDS[0]]['mean_arrival_rate_hz'],'azimuth_gap_p95_ms':r['telemetry'][FIELDS[0]]['interval_p95_s']*1000}
        for s in ['O0','O1']:
            row[s+'_support_rms_dbfs']=r['outputs'][s]['source_support_plus_estimated_processing_delay']['rms_dbfs'];row[s+'_rail_samples']=r['outputs'][s]['whole_capture']['rail_samples']
            ll=r['outputs'][s]['per_utterance_processing_delay'];row[s+'_processing_lag_median_ms']=float(np.median([l['lag_ms'] for l in ll])) if ll else ''
        table.append(row)
    write_csv(target/'per_case_metrics.csv',table)
    plt.rcParams.update({'font.size':10,'figure.dpi':160})
    fig,ax=plt.subplots(2,1,figsize=(10,6),layout='constrained',sharex=True);xx=np.arange(len(table))
    for s,c in [('O0','#1768ac'),('O1','#db6b23')]:
        ax[0].plot(xx,[r[s+'_support_rms_dbfs'] for r in table],'o-',label=s,color=c)
        ax[1].plot(xx,[np.nan if r[s+'_processing_lag_median_ms']=='' else r[s+'_processing_lag_median_ms'] for r in table],'o-',label=s,color=c)
    ax[0].set(ylabel='Support RMS (dBFS)',title='Captured outputs: levels differ; this does not select an accuracy winner');ax[0].legend()
    labels=[r['case_id'].replace('T3_ABA_repeat','ABA ')+(' retry' if r['attempt']=='hardware_retry1' else '') for r in table]
    ax[1].set(ylabel='Approx. lag from MIC0 (ms)',xticks=xx,xticklabels=labels);ax[1].tick_params(axis='x',labelsize=8,rotation=20);ax[1].legend()
    for a in ax:a.grid(alpha=.2)
    fig.savefig(figs/'01_levels_and_relative_delay.png');plt.close(fig)
    plotted=[];d=data['T3_ABA_repeat1'];r=repetitions[0]
    fig,ax=plt.subplots(3,1,figsize=(11,8),layout='constrained')
    n=len(d['y']);hop=320
    for i in range(0,n,hop):
        block=d['y'][i:i+hop];source=(i-r['transport']['capture_minus_source_offset_samples'])/FS
        native=r['framing']['startup_frames_excluded']+3*i;cbidx=max(0,np.searchsorted([c['first_native_frame'] for c in d['cb']],native,side='right')-1)
        hs=(d['cb'][cbidx]['host_callback_monotonic_ns']-d['t0'])/1e9
        plotted.append({'kind':'audio_20ms','source_index_s':source,'host_callback_availability_s':hs,
            'O0_rms_dbfs':db(np.sqrt(np.mean(block[:,4]**2))),'O1_rms_dbfs':db(np.sqrt(np.mean(block[:,5]**2))),
            'O0_abs_peak_fs':float(np.max(np.abs(block[:,4]))),'O1_abs_peak_fs':float(np.max(np.abs(block[:,5])))})
    aa=[p for p in plotted if p['kind']=='audio_20ms']
    for s in ['O0','O1']:ax[0].plot([p['host_callback_availability_s'] for p in aa],[p[s+'_rms_dbfs'] for p in aa],label=s,linewidth=.8)
    ax[0].set(ylabel='20ms RMS (dBFS)',ylim=(-100,0),title=f'ABA repeat 1 ({hardware.name}): host receipt timelines, no fitted metadata shift');ax[0].legend(loc='upper right')
    for j,label in enumerate(['Focus 1','Focus 2','Scanning','Auto']):ax[1].plot(d['az_host_s'],d['az'][:,j],label=label,linewidth=1 if j==3 else .5,alpha=1 if j==3 else .6)
    ax[1].set(ylabel='Native angle (degrees)',ylim=(-5,185));ax[1].legend(ncol=4)
    ax[2].plot(d['energy_host_s'],d['energy'][:,3],color='#438d4a');ax[2].set(ylabel='Auto speech energy\n(vendor units)',xlabel='Seconds from first audio callback (host availability)')
    for t in r['turns']:
        for a in ax:a.axvspan(t['recaptured_onset_containing_callback_s'],t['recaptured_support_end_containing_callback_s'],alpha=.09,color='gray')
        ax[1].text(t['recaptured_onset_containing_callback_s'],175,t['utterance_label']+' '+t['rir_role'],fontsize=9)
    for a in ax:a.grid(alpha=.2);a.set_xlim(0,39)
    for i,t in enumerate(d['az_host_s']):plotted.append({'kind':'azimuth_full_rate','host_response_s':float(t),**{f'beam{j}_deg':float(d['az'][i,j]) for j in range(4)}})
    for i,t in enumerate(d['energy_host_s']):plotted.append({'kind':'energy_full_rate','host_response_s':float(t),**{f'beam{j}_energy':float(d['energy'][i,j]) for j in range(4)}})
    write_csv(figs/'02_timeline_data.csv',plotted);fig.savefig(figs/'02_ABA_host_timeline.png');plt.close(fig)
    fig,ax=plt.subplots(2,1,figsize=(10,6),layout='constrained');repeatrows=[]
    for name in ['T3_ABA_repeat1','T3_ABA_repeat2']:
        d=data[name];ax[0].plot(d['az_host_s'],d['az'][:,3],label=name,linewidth=.8)
        for t,a in zip(d['az_host_s'],d['az'][:,3]):repeatrows.append({'kind':'auto_angle','case_id':name,'host_response_s':float(t),'native_auto_deg':float(a)})
    ax[0].set(ylabel='Native auto angle (degrees)',title='Two fresh-state repeats; common source-vector identity, no fitted shifts');ax[0].legend()
    for i,r in enumerate(results):
        for field,shift in zip(FIELDS,[-.12,.12]):
            m=r['telemetry'][field];ax[1].plot([i+shift]*3,[m['interval_median_s']*1000,m['interval_p95_s']*1000,m['interval_max_s']*1000],'.-',color='#1768ac' if field==FIELDS[0] else '#db6b23',label=field if i==0 else None)
            repeatrows.append({'kind':'gap_summary','case_id':r['case_id'],'field':field,'p50_ms':m['interval_median_s']*1000,'p95_ms':m['interval_p95_s']*1000,'max_ms':m['interval_max_s']*1000})
    ax[1].set(ylabel='Read gaps p50 / p95 / max (ms)',xticks=xx,xticklabels=labels);ax[1].tick_params(axis='x',labelsize=8,rotation=20);ax[1].set_yscale('log');ax[1].legend(fontsize=8)
    for a in ax:a.grid(alpha=.2)
    write_csv(figs/'03_repeat_and_gap_data.csv',repeatrows);fig.savefig(figs/'03_repeat_and_logging_gaps.png');plt.close(fig)
    print(json.dumps({'cases':len(results),'compared_samples':aggregate['total_compared_mic_samples'],'mismatches':aggregate['total_payload_mismatches'],'speech_rails':aggregate['speech_output_rail_samples'],'repeat':repeat,'case_metrics':table},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',required=True);p.add_argument('--hardware',required=True);a=p.parse_args();run(a.report,a.hardware)
