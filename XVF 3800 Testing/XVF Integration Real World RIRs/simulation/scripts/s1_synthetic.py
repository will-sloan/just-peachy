"""Independent known-FIR synthesis checks before real S1 scoring; see S1_README.md."""
import argparse, hashlib, time
from fractions import Fraction
from pathlib import Path
import numpy as np
from scipy import signal, fft
import soundfile as sf
from s0_common import read,save,Progress
from s1_signal import *

def recovery_checks(core,h,cfg):
    # Known relative arrival order and frequency gains do not depend on common latency.
    peak_est=np.array([parabolic_peak(abs(core[:4000,m]),int(np.argmax(abs(core[:4000,m])))) for m in range(4)])
    peak_true=np.argmax(abs(h[:1000]),axis=0)
    delay_errors=[float((peak_est[j]-peak_est[i])-(peak_true[j]-peak_true[i])) for i,j in PAIRS]
    n=65536;f=fft.rfftfreq(n,1/FS);use=(f>=300)&(f<=6000)
    actual=abs(fft.rfft(core,n,axis=0));truth=abs(fft.rfft(h,n,axis=0))
    gain=np.median(db20(actual[use]/np.maximum(truth[use],1e-20)),axis=0)
    return {'pairwise_delay_errors_samples':delay_errors,'max_pairwise_delay_error_samples':max(abs(np.array(delay_errors))),
            'midband_gain_error_db_per_mic':gain.tolist(),'max_midband_gain_error_db':float(max(abs(gain))),
            'peak_samples':peak_est.tolist()}

def fixture(original48,ppm,noise_std,late=False,marker_tail=False):
    # Independent polyphase implementation, not the extractor's sinc warp.
    ratio=Fraction(str((1+ppm*1e-6)/3)).limit_denominator(100000)
    drive=signal.resample_poly(original48*10**(-6/20),ratio.numerator,ratio.denominator,window=('kaiser',8.6))
    h=np.zeros((14000,4));delays=[160,162,159,164];gains=[.08,.05,.11,.065]
    for m,(delay,gain) in enumerate(zip(delays,gains)):
        h[delay,m]=gain;h[delay+320,m]=.3*gain;h[delay+1120,m]=-.15*gain
        if late:h[delay+11200,m]=.25*gain
    offset=5920;result=signal.fftconvolve(drive[:,None],h,axes=0)
    y=np.zeros((350647,4));y[offset:offset+len(result)]=result
    rng=np.random.default_rng(917)
    y+=rng.normal(0,noise_std,y.shape)
    if marker_tail:
        start=offset+round(2*(1+ppm*1e-6)*FS)
        t=np.arange(round(1.15*FS))/FS
        ringing=.006*np.sin(2*np.pi*440*t)*np.exp(-t/1.2)
        y[start:start+len(ringing)]+=ringing[:,None]*np.array([1,.7,.9,.6])
    hints=[offset/FS+(1+ppm*1e-6)*t+np.median(delays)/FS for t in [2,16,16.2]]
    return y,h,hints

def run(report):
    report=Path(report);cfg=read(report/'extraction_config.json');policy=read(report/'qc_policy.json')
    row=read(report/'selected_pilot_manifest.json')['recordings'][0]
    path=Path(row['absolute_run_path'])/'02_raw/pass_01_amplified/excitation_original.wav'
    source=source_at_16k(path,cfg);raw,fs=sf.read(path,dtype='float64')
    cases=[('zero_clock',0,1e-8,False,False),('positive_clock',200,1e-8,False,False),
           ('negative_clock',-200,1e-8,False,False),('background_noise',200,5e-5,False,False),
           ('late_reflection',0,1e-8,True,False),('marker_contamination',0,1e-7,False,True)]
    results=[];t0=time.monotonic()
    with Progress(report,'S1_synthetic_fixtures',len(cases)) as progress:
        for name,ppm,noise_std,late,contaminated in cases:
            start=time.monotonic();y,h,hints=fixture(raw,ppm,noise_std,late,contaminated)
            selected,zero,alternate,timing=choose_timing(y,source,hints,cfg)
            noise=noise_metrics(y,selected,cfg)
            candidate,core,processed,bf,metrics,_=candidate_response(selected,noise,cfg)
            checks=recovery_checks(core,h,cfg);tolerances=policy['synthetic_acceptance']
            acceptance={}
            if not contaminated:
                acceptance={'clock_sign_and_error':abs(timing['marker_regression_ppm']-ppm)<=tolerances['max_clock_error_ppm'],
                    'distinct_channel_gain_scaling':checks['max_midband_gain_error_db']<=tolerances['max_midband_gain_error_db'],
                    'relative_delay_preservation':checks['max_pairwise_delay_error_samples']<=tolerances['max_pairwise_peak_delay_error_samples'],
                    'linear_convolution_length':len(selected['full'])==len(selected['window'])+len(selected['inverse'])-1}
            else:acceptance={'marker_contamination_warning':noise['marker_tail_or_nonstationarity_warning']}
            if late:
                a=round(checks['peak_samples'][0])+11200;local=abs(core[a-8:a+9,0]);observed=a-8+np.argmax(local)
                acceptance['late_reflection_not_wrapped']=abs(observed-a)<=tolerances['late_reflection_location_error_samples']
                checks['late_reflection_recovered_sample']=int(observed)
            if name=='zero_clock':
                again=extract_variant(y,source,timing,selected['ppm'],cfg)
                acceptance['deterministic_float_regeneration']=np.array_equal(again['full'],selected['full'])
                reversed_checks=recovery_checks(core[:,::-1],h,cfg)
                acceptance['reversed_channel_mutation_detected']=reversed_checks['max_pairwise_delay_error_samples']>.35
                gain_checks=recovery_checks(core*10**(-6/20),h,cfg)
                acceptance['double_gain_mutation_detected']=gain_checks['max_midband_gain_error_db']>5
                aligned=np.column_stack([np.roll(core[:,m],int(round(checks['peak_samples'][0]-checks['peak_samples'][m]))) for m in range(4)])
                acceptance['per_mic_alignment_mutation_detected']=recovery_checks(aligned,h,cfg)['max_pairwise_delay_error_samples']>.35
            result={'name':name,'true_clock_ppm':ppm,'true_common_offset_samples':5920,'noise_std_fs':noise_std,
                'method':'Independent scipy.resample_poly of exact 48k source, then known FIR convolution at capture rate',
                'marker_ppm':timing['marker_regression_ppm'],'working_half_width_ppm':timing['working_half_width_ppm'],
                'chosen_ppm':timing['selected_ppm'],'timing_status':timing['status'],'clock_concentration':timing['clock_sensitivity'],
                'recovery':checks,'checks':acceptance,'passed':all(acceptance.values()),'elapsed_sec':time.monotonic()-start,
                'marker_gap_warning':noise['marker_tail_or_nonstationarity_warning']}
            results.append(result);progress.done+=1;progress.detail=name
            save(report/'synthetic_results.json',{'status':'RUNNING','cases':results})
            print(f'{name}: pass={result["passed"]} ppm={result["marker_ppm"]:.2f}, chosen={result["chosen_ppm"]:.2f}, gainerr={checks["max_midband_gain_error_db"]:.3f}dB, delayerr={checks["max_pairwise_delay_error_samples"]:.3f} samples, {result["elapsed_sec"]:.2f}s',flush=True)
    total={'status':'PASSED' if all(r['passed'] for r in results) else 'FAILED','cases':results,
        'checks_passed':sum(sum(r['checks'].values()) for r in results),'checks_total':sum(len(r['checks']) for r in results),
        'elapsed_sec':time.monotonic()-t0,'not_acoustic_repeatability':True,'no_real_microphone_recording_scored':True}
    save(report/'synthetic_results.json',total)
    return 0 if total['status']=='PASSED' else 2

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',required=True);a=p.parse_args();raise SystemExit(run(a.report))
