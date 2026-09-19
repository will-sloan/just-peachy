"""Shared-clock ESS library extraction; no geometry fitting, hardware or file writes."""
import copy, math
import numpy as np
from scipy import signal, fft
import s1_signal as s1
from s1_signal import FS, PAIRS, db10, db20

def marker_clock(y,source,hints,cfg):
    t=s1.marker_clock(y,source,hints,cfg)
    t["legacy_integer_aligned_median_wavelet_coherence"]=t["median_wavelet_coherence"]
    nfft=4096;f=fft.rfftfreq(nfft,1/FS);waves={}
    for bi,(lo,hi) in enumerate(cfg["marker_bands_hz"]):
        mask=s1.smooth_mask(f,lo,hi,min(200,(hi-lo)/4))
        for mi,ts in enumerate(cfg["marker_source_times_sec"]):
            template=source[round(ts*FS):round((ts+.02)*FS)]
            X=fft.rfft(template,nfft);P=abs(X)**2
            inverse=np.conj(X)/(P+cfg["marker_regularization_relative"]*P.max())*mask
            start=round((hints[mi]-.035)*FS);stop=start+round(.13*FS)
            response=fft.irfft(fft.rfft(y[start:stop],nfft,axis=0)*inverse[:,None],nfft,axis=0)
            for mic in range(4):
                o=next(o for o in t["observations"] if o["band_index"]==bi and o["marker_index"]==mi and o["mic"]==mic)
                pos=o["capture_landmark_sec"]*FS-start+np.arange(-80,81)
                waves[bi,mi,mic]=s1.sinc_sample(response[:,mic],pos)
    coherences=[]
    for fit in t["fits"]:
        bi,mic=fit["band_index"],fit["mic"]
        a,b=waves[bi,0,mic],waves[bi,1,mic]
        coherence=float(abs(np.dot(a,b))/(np.linalg.norm(a)*np.linalg.norm(b)+1e-30))
        fit["legacy_integer_aligned_coherence"]=fit["start_end_wavelet_coherence"]
        fit["start_end_wavelet_coherence"]=coherence;coherences.append(coherence)
    t["median_wavelet_coherence"]=float(np.median(coherences))
    t["coherence_alignment_scope"]="Fractional acoustic-landmark alignment of marker diagnostic snippets only. Microphone recordings/responses are never independently shifted."
    p,u=t["marker_regression_ppm"],t["working_half_width_ppm"]
    reliable=(t["median_wavelet_coherence"]>=cfg["clock_min_coherence"] and
              abs(p)+u<=cfg["clock_limit_ppm"] and u<=cfg["clock_max_reliable_half_width_ppm"])
    if reliable and abs(p)>u:chosen=p;status="PER_RECORD_MARKER_CLOCK"
    elif reliable:chosen=0.;status="ZERO_WITHIN_MARKER_UNCERTAINTY"
    else:chosen=0.;status="CONSERVATIVE_ZERO_FALLBACK"
    t.update(selected_ppm=chosen,status=status,reliable_marker_evidence=bool(reliable),
        microphone_vector_resampled=False,reference_only_common_clock_mapping=True,
        sweep_concentration_is_diagnostic_only=True,
        mapping_equation="capture_seconds = beta_landmark + (1 + ppm*1e-6)*source_seconds + remaining response delay")
    return t

def band_filter(reference,cfg):
    spec=cfg["output_weighting"];nfft=fft.next_fast_len(max(262144,len(reference)))
    if nfft<len(reference):raise ValueError("Source-power FFT must retain the entire sweep")
    # Source-only ridge attenuation; never divides by a weak source bin or boosts it.
    P=abs(fft.rfft(reference,nfft))**2
    freq=fft.rfftfreq(nfft,1/FS)
    ridge=spec["source_power_ridge_relative"]*P.max()
    regularizer=P/(P+ridge)
    lo0,lo1=spec["lower_transition_hz"];hi0,hi1=spec["upper_transition_hz"]
    weight=np.ones_like(freq);weight[freq<=lo0]=0;weight[freq>=hi1]=0
    ix=(freq>lo0)&(freq<lo1);weight[ix]=.5-.5*np.cos(np.pi*(freq[ix]-lo0)/(lo1-lo0))
    ix=(freq>hi0)&(freq<hi1);weight[ix]=.5+.5*np.cos(np.pi*(freq[ix]-hi0)/(hi1-hi0))
    gain=weight*regularizer
    # A single symmetric FIR design for the chosen common weighting, no per-mic EQ.
    b=signal.firwin2(spec["fir_taps"],freq,gain,fs=FS,nfreqs=131073,window=("kaiser",8.6))
    return b

def noise_metrics(y,selected,cfg):
    c=copy.deepcopy(cfg);c["noise_welch_nperseg"]=4096
    result=s1.noise_metrics(y,selected,c)
    # Recompute edge support using the complete 10-second sweep, including its actual fades.
    beta=selected["beta_landmark_sec"];ratio=selected["ratio"]
    sweep=y[round((beta+3*ratio)*FS):round((beta+13*ratio)*FS)]
    f,py=signal.welch(sweep,fs=FS,nperseg=4096,noverlap=2048,axis=0,scaling="density")
    pn=result["psd_fs2_per_hz"];bands=[]
    for lo,hi in cfg["noise_bands_hz"]:
        ix=(f>=lo)&(f<hi);a=np.trapz(pn[ix],f[ix],axis=0);b=np.trapz(py[ix],f[ix],axis=0)
        margin=db10(b/(a+1e-30))
        bands.append({"band_hz":[lo,hi],"noise_power_fs2":a.tolist(),"sweep_plus_noise_power_fs2":b.tolist(),
          "sweep_plus_noise_to_pre_noise_db":margin.tolist(),"supported_all_channels":bool(min(margin)>=10)})
    result["bands"]=bands
    return result

def candidate_response(selected,noise,cfg):
    b=band_filter(selected["reference"],cfg)
    core=signal.fftconvolve(selected["core"],b[:,None],mode="same",axes=0)
    nf=fft.next_fast_len(len(selected["inverse"])+len(b)-1);f=fft.rfftfreq(nf,1/FS)
    k=abs(fft.rfft(selected["inverse"],nf)*fft.rfft(b,nf))**2
    predicted=np.array([np.trapz(np.interp(f,noise["psd_frequencies_hz"],noise["psd_fs2_per_hz"][:,m])*k,f) for m in range(4)])
    block=round(cfg["tail_block_sec"]*FS);count=len(core)//block
    power=np.mean(core[:count*block].reshape(count,block,4)**2,axis=1)
    late=np.median(power[round(count*.8):],axis=0);floor=np.maximum(predicted,late)
    env=signal.convolve(core**2,np.ones((8,1))/8,mode="same",method="direct")
    arrivals=[];peaks=[]
    for m in range(4):
        search=env[:round(.3*FS),m];peak=int(np.argmax(search));peaks.append(peak)
        above=np.flatnonzero((search>max(float(search[peak])*.02,float(floor[m])*9))&(np.arange(len(search))<=peak))
        first=int(above[0]) if len(above) else peak
        arrivals.append({"mic":m,"first_significant_energy_sample_in_core":first,"strongest_early_energy_sample_in_core":peak,
            "confidence":"BAND_LIMITED_ONSET_NOT_CALIBRATED_DIRECT_PATH","peak_to_model_noise_db":float(db10(search[peak]/max(floor[m],1e-30)))})
    earliest=min(a["first_significant_energy_sample_in_core"] for a in arrivals)
    start=max(0,earliest-round(cfg["common_pre_arrival_margin_sec"]*FS))
    cap=min(len(core)-1,earliest+round(cfg["tail_maximum_after_arrival_sec"]*FS))
    significant=np.flatnonzero(np.any(power>4*floor,axis=1))
    significant=significant[significant*block<=cap]
    last=(int(significant[-1])+1)*block if len(significant) else earliest
    tail=min(cap,max(earliest+round(cfg["tail_minimum_after_arrival_sec"]*FS),last+2*block))
    end=min(len(core),tail+round(cfg["tail_taper_sec"]*FS))
    weights=np.ones(len(core));weights[:start]=0;weights[end:]=0
    fade=round(.003*FS);weights[start:start+fade]=.5-.5*np.cos(np.linspace(0,np.pi,fade))
    weights[tail:end]=.5+.5*np.cos(np.linspace(0,np.pi,end-tail))
    processed=core*weights[:,None];candidate=processed[start:end].copy()
    early_a=max(0,earliest-round(.002*FS));early_b=min(len(core),max(peaks)+round(.03*FS))
    pairs=[]
    for i,j in PAIRS:
        d=s1.gcc_delay(core[early_a:early_b,i],core[early_a:early_b,j])
        post=s1.gcc_delay(processed[early_a:early_b,i],processed[early_a:early_b,j])
        pairs.append({"pair":[i,j],"delay_samples_j_minus_i":float(d),"delay_us_j_minus_i":float(d/FS*1e6),
            "candidate_delay_change_samples":float(post-d),"strongest_energy_peak_delta_samples":int(peaks[j]-peaks[i])})
    before=np.sum(core**2,axis=0);after=np.sum(processed**2,axis=0)
    levels0=db10(before/max(before[0],1e-30));levels1=db10(after/max(after[0],1e-30))
    ringing=db10(np.sum(core[:max(0,earliest-round(.002*FS))]**2,axis=0)/(np.sum(core[early_a:early_b]**2,axis=0)+1e-30))
    bf_f,bf_h=signal.freqz(b,worN=131072,fs=FS)
    ix=(bf_f>=110)&(bf_f<=7000)&(abs(db20(bf_h))<=.1)
    supported=[r["band_hz"] for r in noise["bands"] if r["supported_all_channels"]]
    metrics={"arrivals":arrivals,"pairwise_delays":pairs,"early_common_window_samples":[early_a,early_b],
        "chosen_nominal_passband_hz":[110,7000],"chosen_transition_bands_hz":[[80,110],[7000,7300]],
        "filter_only_within_0_1db_hz":[float(bf_f[ix][0]),float(bf_f[ix][-1])],
        "evidence_supported_intervals_hz":supported,"support_rule":"All microphones >=10 dB sweep-plus-noise/pre-noise power per declared interval; not calibrated acoustic bandwidth",
        "common_crop_start_sample_in_core":start,"common_taper_start_sample_in_core":tail,"common_crop_end_sample_in_core":end,
        "first_energy_sample_in_output":earliest-start,"first_energy_sec_in_output":(earliest-start)/FS,
        "candidate_duration_sec":len(candidate)/FS,"supported_tail_after_first_energy_sec":max(0,(last-earliest)/FS),
        "tail_cap_reached":tail==cap,"tail_floor_used_fs2":floor.tolist(),"predicted_noise_variance_fs2":predicted.tolist(),
        "late_empirical_floor_includes_possible_decay_fs2":late.tolist(),"energy_removed_fraction_per_mic":(1-after/(before+1e-30)).tolist(),
        "relative_level_before_db_vs_mic0":levels0.tolist(),"relative_level_after_db_vs_mic0":levels1.tolist(),
        "relative_level_change_db":(levels1-levels0).tolist(),"pre_arrival_energy_db_vs_early_window":ringing.tolist(),
        "decay_estimate_rt60_sec":None,"peak_abs_per_mic":np.max(abs(candidate),axis=0).tolist(),
        "rms_per_mic":np.sqrt(np.mean(candidate**2,axis=0)).tolist(),
        "core_energy_per_mic":before.tolist(),"candidate_energy_per_mic":after.tolist()}
    return candidate,core,processed,b,metrics,power

def extract(y,source,hints,cfg,compare_zero=True):
    timing=marker_clock(y,source,hints,cfg)
    chosen=s1.extract_variant(y,source,timing,timing["selected_ppm"],cfg)
    zero=chosen if chosen["ppm"]==0 else s1.extract_variant(y,source,timing,0,cfg)
    timing["sweep_concentration_improvement_fraction"]=chosen["concentration"]/max(zero["concentration"],1e-30)-1
    noise=noise_metrics(y,chosen,cfg)
    candidate,core,processed,b,metrics,power=candidate_response(chosen,noise,cfg)
    residual=s1.reconstruct(chosen,processed,b,cfg)
    comparison={"zero_concentration":zero["concentration"],"selected_concentration":chosen["concentration"]}
    sensitivity=[]
    if timing["status"]=="CONSERVATIVE_ZERO_FALLBACK":
        for ppm in [timing["marker_regression_ppm"]-timing["working_half_width_ppm"],
                    timing["marker_regression_ppm"]+timing["working_half_width_ppm"]]:
            ppm=float(np.clip(ppm,-cfg["clock_limit_ppm"],cfg["clock_limit_ppm"]))
            alternate=s1.extract_variant(y,source,timing,ppm,cfg)
            _,_,_,_,altmetrics,_=candidate_response(alternate,noise_metrics(y,alternate,cfg),cfg)
            sensitivity.append({"ppm":ppm,
                "max_early_pair_delay_change_samples":max(abs(a["delay_samples_j_minus_i"]-c["delay_samples_j_minus_i"]) for a,c in zip(metrics["pairwise_delays"],altmetrics["pairwise_delays"])),
                "max_relative_level_change_db":float(max(abs(np.array(metrics["relative_level_after_db_vs_mic0"])-altmetrics["relative_level_after_db_vs_mic0"]))),
                "concentration":alternate["concentration"]})
    timing["fallback_sensitivity"]=sensitivity
    timing["uncertainty_effect_over_sweep_samples"]=timing["working_half_width_ppm"]*1e-6*10*FS
    return {"candidate":candidate,"core":core,"processed":processed,"bandfilter":b,"block_power":power,
        "selected":chosen,"timing":timing,"noise":noise,"response_metrics":metrics,"residual":residual,"zero_comparison":comparison}
