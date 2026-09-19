"""Bounded S1 signal analysis. Never reads angle/distance labels or controls devices.

ESS basis: Farina (2000), https://angelofarina.it/Public/Papers/134-AES00.PDF.
All inverse/clock/band/tail choices here are development policy, not calibration.
"""
import itertools, math
import numpy as np
from scipy import signal, fft
import soundfile as sf

FS=16000
PAIRS=list(itertools.combinations(range(4),2))

def db10(value):return 10*np.log10(np.maximum(value,1e-30))
def db20(value):return 20*np.log10(np.maximum(np.abs(value),1e-30))

def source_at_16k(path,cfg):
    x,fs=sf.read(path,dtype='float64',always_2d=False)
    if fs!=48000 or x.ndim!=1:raise ValueError('Expected exact mono 48 kHz excitation')
    p=cfg['resample_source']
    taps=signal.firwin(p['fir_taps'],p['cutoff_hz'],fs=48000,window=tuple(p['window']))
    return signal.resample_poly(x,1,3,window=taps)*10**(cfg['playback_gain_db']/20)

def sinc_sample(x,positions,taps=64,beta=8.6):
    """Deterministic fractional sampling with zero extension, bounded working tiles."""
    x=np.asarray(x,dtype=np.float64);positions=np.asarray(positions,dtype=float)
    if x.ndim!=1:raise ValueError('Reference-only scalar resampling; never per-microphone input')
    out=np.empty(len(positions));offset=np.arange(-taps//2+1,taps//2+1)
    denom=np.i0(beta)
    for first in range(0,len(positions),4096):
        p=positions[first:first+4096];idx=np.floor(p).astype(int)[:,None]+offset
        delta=p[:,None]-idx
        window=np.i0(beta*np.sqrt(np.maximum(0,1-(delta/(taps/2))**2)))/denom
        weights=np.sinc(delta)*window;weights/=weights.sum(axis=1)[:,None]
        valid=(idx>=0)&(idx<len(x))
        out[first:first+len(p)]=np.sum(x[np.clip(idx,0,len(x)-1)]*valid*weights,axis=1)
    return out

def warp_reference(x,ratio,cfg):
    p=cfg['clock_reference_warp']
    return sinc_sample(x,np.arange(int(np.ceil(len(x)*ratio)))/ratio,p['taps'],p['kaiser_beta'])

def smooth_mask(freq,lo,hi,edge=150):
    w=np.ones_like(freq)
    w[freq<lo]=0;w[freq>hi]=0
    ix=(freq>=lo)&(freq<lo+edge);w[ix]=.5-.5*np.cos(np.pi*(freq[ix]-lo)/edge)
    ix=(freq>hi-edge)&(freq<=hi);w[ix]=.5-.5*np.cos(np.pi*(hi-freq[ix])/edge)
    return w

def parabolic_peak(a,index):
    if index<=0 or index>=len(a)-1:return float(index)
    l,m,r=a[index-1:index+2];denom=l-2*m+r
    correction=.5*(l-r)/denom if denom else 0
    return float(index+np.clip(correction,-.5,.5))

def marker_clock(y,source,hints,cfg):
    """Whiten each distinct exact marker, then fit repeated acoustic landmarks.

    Several bands/channels expose landmark ambiguity; spread is a working
    sensitivity interval, never a confidence interval or independent clock truth.
    """
    expected=np.asarray(cfg['marker_source_times_sec']);nfft=4096;f=fft.rfftfreq(nfft,1/FS)
    observations=[];wavelets={}
    for band_index,(lo,hi) in enumerate(cfg['marker_bands_hz']):
        mask=smooth_mask(f,lo,hi,min(200,(hi-lo)/4))
        for marker_index,ts in enumerate(expected):
            template=source[round(ts*FS):round((ts+.02)*FS)]
            X=fft.rfft(template,nfft);power=np.abs(X)**2
            inverse=np.conj(X)/(power+cfg['marker_regularization_relative']*power.max())*mask
            start=round((hints[marker_index]-.035)*FS);stop=start+round(.13*FS)
            if start<0 or stop>len(y):raise ValueError('Marker window outside capture')
            response=fft.irfft(fft.rfft(y[start:stop],nfft,axis=0)*inverse[:,None],nfft,axis=0)
            for mic in range(4):
                env=np.abs(signal.hilbert(response[:,mic]))
                a,b=round(.018*FS),round(.052*FS)
                peak=a+int(np.argmax(env[a:b]));fp=parabolic_peak(env,peak)
                wav=response[max(0,peak-80):peak+81,mic]
                wavelets[(band_index,marker_index,mic)]=wav
                observations.append({'band_index':band_index,'band_hz':[lo,hi],'marker_index':marker_index,'mic':mic,
                    'source_sec':float(ts),'capture_landmark_sec':(start+fp)/FS,'peak_energy':float(env[peak]**2)})
    fits=[];slopes=[];coherences=[]
    for bi in range(len(cfg['marker_bands_hz'])):
        for mic in range(4):
            obs=[o for o in observations if o['band_index']==bi and o['mic']==mic]
            times=np.array([o['capture_landmark_sec'] for o in obs]);ratio,intercept=np.polyfit(expected,times,1)
            residual=(times-(intercept+ratio*expected))*FS
            slopes.append((ratio-1)*1e6)
            aa=wavelets[(bi,0,mic)];bb=wavelets[(bi,1,mic)]
            coherence=float(abs(np.dot(aa,bb))/(np.linalg.norm(aa)*np.linalg.norm(bb)+1e-30));coherences.append(coherence)
            fits.append({'band_index':bi,'mic':mic,'ppm':float((ratio-1)*1e6),'intercept_sec':float(intercept),
                         'residual_samples':residual.tolist(),'start_end_wavelet_coherence':coherence,
                         'end_pair_residual_samples':float(((times[2]-times[1])-ratio*.2)*FS)})
    median=float(np.median(slopes));spread=float(np.percentile(np.abs(np.asarray(slopes)-median),90))
    residual=max(float(np.percentile([abs(v) for f0 in fits for v in f0['residual_samples']],90)),.1)
    half=max(cfg['clock_uncertainty_floor_ppm'],spread*2,residual/FS/14*1e6*2)
    within=abs(median)<=cfg['clock_limit_ppm'] and half<=cfg['clock_limit_ppm']
    return {'marker_regression_ppm':median,'working_half_width_ppm':half,
        'working_interval_ppm':[median-half,median+half],'interval_is_calibrated_confidence_interval':False,
        'median_wavelet_coherence':float(np.median(coherences)),'within_search_contract':within,
        'observations':observations,'fits':fits,
        'intercept_scope':'Repeated acoustic landmark; includes unknown bulk latency, propagation, capture delay and response group delay. Not geometric distance.',
        'method':'Three distinct-source-marker inverse filters, three common bands, four channels, per-band/channel linear regression; source marker waveforms are not assumed identical'}

def ess_inverse(reference,cfg,ratio):
    n=len(reference);L=(cfg['sweep_source_end_sec']-cfg['sweep_source_start_sec'])*ratio/np.log(cfg['sweep_end_hz']/cfg['sweep_start_hz'])
    inverse=reference[::-1]*np.exp(-np.arange(n)/FS/L)
    calibration=signal.fftconvolve(reference,inverse)
    nf=fft.next_fast_len(len(calibration));freq=fft.rfftfreq(nf,1/FS)
    transfer=fft.rfft(calibration,nf)*np.exp(2j*np.pi*freq*(n-1)/FS)
    lo,hi=cfg['calibration_band_hz'];band=(freq>=lo)&(freq<=hi)
    scalar=float(np.median(transfer[band].real))
    if scalar<=0:raise ValueError('Invalid self-convolution calibration')
    inverse/=scalar
    values=db20(transfer[band]/scalar)
    return inverse,{'inverse_samples':n,'inverse_time_zero_sample':n-1,'normalization_scalar':scalar,
        'self_transfer_midband_db_percentiles':np.percentile(values,[1,50,99]).tolist(),
        'gain_scope':'Unity numerical transfer in calibration band; no microphone/analog/source response normalization'}

def extract_variant(y,source,timing,ppm,cfg):
    ratio=1+ppm*1e-6
    if ratio<=0 or abs(ppm)>cfg['clock_limit_ppm']:raise ValueError('Clock variant outside bounded policy')
    obs=timing['observations'];beta=float(np.median([o['capture_landmark_sec']-ratio*o['source_sec'] for o in obs]))
    a,b=cfg['sweep_source_start_sec'],cfg['sweep_source_end_sec']
    reference=warp_reference(source[round(a*FS):round(b*FS)],ratio,cfg)
    start=round((beta+ratio*a-cfg['analysis_anchor_sec'])*FS)
    stop=round((beta+ratio*cfg['marker_source_times_sec'][1]-cfg['end_marker_guard_sec'])*FS)
    if start<0 or stop>len(y) or stop<=start:raise ValueError('Excitation analysis crop outside capture')
    window=y[start:stop]
    inverse,calibration=ess_inverse(reference,cfg,ratio)
    full=signal.fftconvolve(window,inverse[:,None],mode='full',axes=0)
    zero=len(inverse)-1;length=round(cfg['maximum_response_sec']*FS)
    core=full[zero:zero+length].copy()
    if len(core)!=length:raise ValueError('Incomplete response horizon')
    energy=np.sum(core[:round(.35*FS)]**2,axis=1)
    peak=int(np.argmax(signal.convolve(energy,np.ones(5)/5,mode='same')))
    radius=round(.0005*FS);concentration=float(energy[max(0,peak-radius):peak+radius+1].sum()/(energy.sum()+1e-30))
    return {'ppm':float(ppm),'ratio':ratio,'beta_landmark_sec':beta,'capture_crop_start_sample':start,'capture_crop_stop_sample':stop,
            'full':full,'core':core,'reference':reference,'window':window,'inverse':inverse,'calibration':calibration,
            'concentration':concentration,'shared_peak_sample':peak}

def choose_timing(y,source,hints,cfg):
    timing=marker_clock(y,source,hints,cfg);p=timing['marker_regression_ppm'];u=timing['working_half_width_ppm']
    marker_p=float(np.clip(p,-cfg['clock_limit_ppm'],cfg['clock_limit_ppm']))
    values=[0.,marker_p]
    if timing['within_search_contract']:
        values += [float(np.clip(p-u,-500,500)),float(np.clip(p+u,-500,500))]
    else:values += [-100.,100.]
    variants={v:extract_variant(y,source,timing,v,cfg) for v in dict.fromkeys(values)}
    zero=variants[0.];alternate=variants[marker_p]
    improvement=alternate['concentration']/max(zero['concentration'],1e-30)-1
    supports=(timing['within_search_contract'] and abs(p)>u and timing['median_wavelet_coherence']>=.65 and
              improvement>=cfg['clock_sweep_min_concentration_improvement_fraction'])
    if supports:selected=alternate;status='PROVISIONAL_COMMON_DRIFT_SUPPORTED'
    elif abs(p)<=u and timing['within_search_contract']:selected=zero;status='ZERO_DRIFT_COMPATIBLE_UNRESOLVED_INTERVAL'
    else:selected=zero;status='TIMING_UNRESOLVED_MARKER_SWEEP_DISAGREEMENT'
    timing.update(selected_ppm=selected['ppm'],status=status,sweep_concentration_improvement_fraction=float(improvement),
        clock_sensitivity=[{'ppm':v,'concentration':r['concentration'],'shared_peak_sample':r['shared_peak_sample'],'beta_landmark_sec':r['beta_landmark_sec']} for v,r in variants.items()],
        mapping_equation='capture_seconds = beta_landmark_seconds + (1 + ppm*1e-6)*source_seconds + residual_response_delay',
        microphone_vector_resampled=False,reference_only_common_clock_mapping=True,
        limitation='Sweep concentration is a compact-response diagnostic from the same measurement, not an independent clock measurement. No label/distance is used.')
    return selected,zero,alternate,timing

def noise_metrics(y,selected,cfg):
    beta=selected['beta_landmark_sec'];ratio=selected['ratio'];marker=beta+2*ratio
    a,b=cfg['noise_window_before_marker_sec'];start=round((marker+a)*FS);stop=round((marker+b)*FS)
    if start<0 or stop>len(y) or stop-start<FS//2:raise ValueError('Verified pre-excitation noise window missing')
    noise=y[start:stop];nper=cfg['noise_welch_nperseg']
    f,pnn=signal.welch(noise,fs=FS,nperseg=nper,noverlap=nper//2,axis=0,detrend='constant',scaling='density')
    sweep_start=round((beta+3*ratio+.15)*FS);sweep_end=round((beta+13*ratio-.05)*FS)
    _,pyy=signal.welch(y[sweep_start:sweep_end],fs=FS,nperseg=nper,noverlap=nper//2,axis=0,scaling='density')
    bands=[]
    for lo,hi in cfg['noise_bands_hz']:
        ix=(f>=lo)&(f<hi);pn=np.trapz(pnn[ix],f[ix],axis=0);ps=np.trapz(pyy[ix],f[ix],axis=0)
        bands.append({'band_hz':[lo,hi],'noise_power_fs2':pn.tolist(),'sweep_plus_noise_power_fs2':ps.tolist(),
                      'sweep_to_noise_db':db10(ps/(pn+1e-30)).tolist(),
                      'supported_all_channels':bool(np.min(db10(ps/(pn+1e-30)))>=10)})
    parts=np.array([np.mean(part**2,axis=0) for part in np.array_split(noise,3)])
    stationarity=(db10(parts.max(axis=0)/(parts.min(axis=0)+1e-30))).tolist()
    pre_sweep=y[round((beta+3*ratio-.2)*FS):round((beta+3*ratio-.03)*FS)]
    lastgap=db10(np.mean(pre_sweep**2,axis=0)/(np.mean(noise**2,axis=0)+1e-30))
    return {'window_capture_samples':[start,stop],'window_capture_sec':[start/FS,stop/FS],
            'source_relative_to_first_acoustic_marker_sec':[a,b],'duration_sec':len(noise)/FS,
            'window_verified_before_excitation':True,'post_sweep_used_as_noise_only':False,
            'stationarity_three_block_power_range_db':stationarity,'bands':bands,
            'pre_sweep_gap_above_pre_marker_noise_db':lastgap.tolist(),'marker_tail_or_nonstationarity_warning':bool(lastgap.max()>6),
            'marker_tail_limitation':'Gap excess may be residual marker energy or changed ambience; not uniquely identified as decay',
            'power_unit':'normalized-recording-full-scale squared; not SPL','psd_frequencies_hz':f,'psd_fs2_per_hz':pnn}

def supported_band(noise,cfg):
    groups=[];current=[]
    for row in noise['bands']:
        if row['supported_all_channels']:current.append(row)
        elif current:groups.append(current);current=[]
    if current:groups.append(current)
    if not groups:return tuple(cfg['candidate_band_edges_hz']),False
    best=max(groups,key=lambda g:np.log(g[-1]['band_hz'][1]/g[0]['band_hz'][0]))
    lo=max(cfg['candidate_band_edges_hz'][0],best[0]['band_hz'][0]);hi=min(cfg['candidate_band_edges_hz'][1],best[-1]['band_hz'][1])
    return (lo,hi),bool(hi>lo and hi/lo>=2)

def gcc_delay(a,b,maxlag=16):
    nf=fft.next_fast_len(len(a)+len(b)-1);A=fft.rfft(a,nf);B=fft.rfft(b,nf)
    cross=B*np.conj(A);cross/=np.maximum(abs(cross),max(abs(cross).max()*1e-6,1e-30))
    cc=fft.irfft(cross,nf);view=np.r_[cc[-maxlag:],cc[:maxlag+1]]
    index=int(np.argmax(abs(view)));return parabolic_peak(abs(view),index)-maxlag

def candidate_response(selected,noise,cfg):
    (lo,hi),band_ok=supported_band(noise,cfg)
    bandfilter=signal.firwin(cfg['candidate_fir_taps'],[lo,hi],pass_zero=False,fs=FS,window=('kaiser',8.6))
    core=signal.fftconvolve(selected['core'],bandfilter[:,None],mode='same',axes=0)
    nf=fft.next_fast_len(len(selected['inverse'])+len(bandfilter)-1);f=fft.rfftfreq(nf,1/FS)
    kernel2=abs(fft.rfft(selected['inverse'],nf)*fft.rfft(bandfilter,nf))**2
    predicted=np.array([np.trapz(np.interp(f,noise['psd_frequencies_hz'],noise['psd_fs2_per_hz'][:,m])*kernel2,f) for m in range(4)])
    block=round(cfg['tail_block_sec']*FS);count=len(core)//block
    blockpower=np.mean(core[:count*block].reshape(count,block,4)**2,axis=1)
    # Empirical late response can include real decay; using it as a floor is deliberately conservative.
    late=np.median(blockpower[round(count*.8):],axis=0);floor=np.maximum(predicted,late)
    envelopes=signal.convolve(core**2,np.ones((8,1))/8,mode='same',method='direct')
    arrivals=[];peaks=[]
    for m in range(4):
        search=envelopes[:round(.3*FS),m];peak=int(np.argmax(search));peaks.append(peak)
        threshold=max(float(search[peak])*.02,float(floor[m])*9)
        candidates=np.flatnonzero((search>threshold)&(np.arange(len(search))<peak+1))
        first=int(candidates[0]) if len(candidates) else peak
        arrivals.append({'mic':m,'first_significant_energy_sample':first,'first_significant_energy_sec':first/FS,
            'strongest_early_energy_sample':peak,'strongest_early_energy_sec':peak/FS,
            'confidence':'BAND_LIMITED_ENERGY_ONSET_NOT_CALIBRATED_DIRECT_PATH',
            'peak_to_model_noise_db':float(db10(search[peak]/max(floor[m],1e-30)))})
    earliest=min(r['first_significant_energy_sample'] for r in arrivals)
    start=max(0,earliest-round(cfg['common_pre_arrival_margin_sec']*FS))
    latest_allowed=min(len(core)-1,earliest+round(cfg['tail_maximum_after_arrival_sec']*FS))
    significant=np.flatnonzero(np.any(blockpower>4*floor[None,:],axis=1))
    significant=significant[significant*block<=latest_allowed]
    last=(int(significant[-1])+1)*block if len(significant) else earliest
    tail=max(earliest+round(cfg['tail_minimum_after_arrival_sec']*FS),last+2*block)
    tail=min(tail,latest_allowed);end=min(len(core),tail+round(cfg['tail_taper_sec']*FS))
    weights=np.ones(len(core));weights[:start]=0;weights[end:]=0
    fade=round(.003*FS)
    if start+fade<len(weights):weights[start:start+fade]=.5-.5*np.cos(np.linspace(0,np.pi,fade))
    if end>tail:weights[tail:end]=.5+.5*np.cos(np.linspace(0,np.pi,end-tail))
    processed=core*weights[:,None];candidate=processed[start:end].copy()
    before=np.sum(core**2,axis=0);after=np.sum(processed**2,axis=0)
    early_a=max(0,earliest-round(.002*FS));early_b=min(len(core),max(peaks)+round(.03*FS))
    pairwise=[]
    for i,j in PAIRS:
        d=gcc_delay(core[early_a:early_b,i],core[early_a:early_b,j])
        post=gcc_delay(processed[early_a:early_b,i],processed[early_a:early_b,j])
        pairwise.append({'pair':[i,j],'delay_samples_j_minus_i':float(d),'delay_us_j_minus_i':float(d/FS*1e6),
                         'candidate_delay_change_samples':float(post-d),'strongest_energy_peak_delta_samples':int(peaks[j]-peaks[i]),
                         'scope':'GCC-PHAT of common early response window; not calibrated direct-path TDOA or angle'})
    level_before=db10(before/max(before[0],1e-30));level_after=db10(after/max(after[0],1e-30))
    pre=core[:max(0,earliest-round(.002*FS))]
    ringing=db10(np.sum(pre**2,axis=0)/(np.sum(core[early_a:early_b]**2,axis=0)+1e-30))
    metrics={'supported_candidate_band_hz':[lo,hi],'band_support_found':band_ok,
        'candidate_filter':{'type':'common symmetric 513-tap Kaiser FIR, centered linear convolution','group_delay_compensated_samples':(len(bandfilter)-1)//2,
                            'cutoff_hz':[lo,hi],'cutoff_is_half_amplitude_not_flat_passband':True},
        'arrivals':arrivals,'pairwise_delays':pairwise,'early_common_window_samples':[early_a,early_b],
        'noise_model_variance_fs2':predicted.tolist(),'conservative_empirical_late_floor_fs2':late.tolist(),'tail_floor_used_fs2':floor.tolist(),
        'tail_policy':'Last common block above 4x conservative floor, 40ms margin then common 60ms cosine taper; empirical floor may include weak real decay',
        'last_significant_energy_sec':last/FS,'supported_tail_after_first_energy_sec':max(0,(last-earliest)/FS),
        'common_crop_start_sample':start,'common_taper_start_sample':tail,'common_crop_end_sample':end,
        'candidate_duration_sec':len(candidate)/FS,'energy_removed_fraction_per_mic':(1-after/(before+1e-30)).tolist(),
        'relative_level_before_db_vs_mic0':level_before.tolist(),'relative_level_after_db_vs_mic0':level_after.tolist(),
        'relative_level_change_db':(level_after-level_before).tolist(),'pre_arrival_energy_db_vs_early_window':ringing.tolist(),
        'decay_estimate_rt60_sec':None,'decay_fit_limit':'No RT60 certification: finite captured tail, nonstationary/short noise reference and conservative truncation. Plotted energy decay is descriptive.',
        'simulation_ready':False,'candidate_is_provisional':True}
    return candidate,core,processed,bandfilter,metrics,blockpower

def reconstruct(selected,processed,bandfilter,cfg):
    predicted=signal.fftconvolve(selected['reference'][:,None],processed,mode='full',axes=0)
    observed=signal.fftconvolve(selected['window'],bandfilter[:,None],mode='same',axes=0)
    a=round((cfg['analysis_anchor_sec']+.15)*FS);b=min(len(observed),round((len(selected['reference'])/FS+cfg['analysis_anchor_sec'])*FS))
    difference=observed[a:b]-predicted[a:b]
    power=np.sum(observed[a:b]**2,axis=0)
    relative=db10(np.sum(difference**2,axis=0)/(power+1e-30))
    f,obs_psd=signal.welch(observed[a:b],fs=FS,nperseg=2048,axis=0)
    _,err_psd=signal.welch(difference,fs=FS,nperseg=2048,axis=0)
    return {'scope':'Same-sweep band-matched internal consistency only; no independent speech or acoustic validation',
            'comparison_window_capture_relative_samples':[a,b],'relative_residual_energy_db':relative.tolist(),
            'frequency_hz':f,'observed_psd':obs_psd,'residual_psd':err_psd}

def fd_crosscheck(selected,bandfilter,main_core,cfg):
    nf=fft.next_fast_len(len(selected['window'])+len(selected['reference'])-1)
    X=fft.rfft(selected['reference'],nf);P=abs(X)**2;Y=fft.rfft(selected['window'],nf,axis=0)
    H=Y*np.conj(X[:,None])/(P[:,None]+cfg['crosscheck_fd_regularization_relative']*P.max())
    h=fft.irfft(H,nf,axis=0)[:len(main_core)]
    h=signal.fftconvolve(h,bandfilter[:,None],mode='same',axes=0)
    f=fft.rfftfreq(65536,1/FS);a=fft.rfft(main_core,65536,axis=0);b=fft.rfft(h,65536,axis=0)
    use=(f>300)&(f<6000)
    change=db20(b[use]/(a[use]+1e-30))
    return h,{'method':'Zero-padded regularized frequency-domain division; bounded secondary cross-check only',
              'regularization_relative_to_max_source_bin_power':cfg['crosscheck_fd_regularization_relative'],
              'median_magnitude_difference_db_per_mic':np.median(change,axis=0).tolist(),
              'p90_absolute_magnitude_difference_db_per_mic':np.percentile(abs(change),90,axis=0).tolist(),
              'fft_samples':nf,'not_independent_validation':True}
