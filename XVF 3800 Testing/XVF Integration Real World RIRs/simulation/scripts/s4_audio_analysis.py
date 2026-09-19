"""S4 local audio/level calibration, no hardware. See README_S4.md."""
import argparse, math
import numpy as np
import soundfile as sf
from s4_common import *
from s4_h2_analysis import rail_metrics, audit_converter
from s3_analyze import output_lag
from s4_capture_selection import accepted_cases, case_folder

def analyze_case(folder,scene):
    result=read(folder/'case_result.json');assert result['status']=='PASS'
    data,fs=sf.read(folder/'decoded_six.wav',dtype='int32',always_2d=True);data=data>>8
    assert fs==16000 and data.shape[1]==6
    offset=result['payload']['capture_minus_source_offset_samples'];streams={};alignment={}
    speech=[s for s in scene['segments'] if s['kind']=='utterance']
    for name,index in [('O0',4),('O1',5)]:
        delays=[]
        if offset is not None:
            for seg in speech:
                other=[s for s in speech if s is not seg and max(s['source_start_sample'],seg['source_start_sample'])<min(s['source_stop_sample'],seg['source_stop_sample'])]
                if other:continue
                start=max(0,seg['source_start_sample']+offset);end=min(len(data),seg['convolution_stop_sample']+offset+4000)
                if end-start<8000 or not np.any(data[start:end,0]):continue
                lag=output_lag(data[start:end,index].astype(float)/2**23,data[start:end,0].astype(float)/2**23)
                lag['source_id']=seg['source_id'];lag['qualified']=bool(abs(lag['normalized_correlation'])>=.1 and 0<lag['lag_samples']<4000)
                delays.append(lag)
        valid=[r for r in delays if r['qualified']]
        median=int(round(np.median([r['lag_samples'] for r in valid]))) if valid else None
        support=[]
        if offset is not None and median is not None:
            for seg in speech:
                ranges=seg['activity_ranges_samples_estimated']
                if ranges:support.append(((ranges[0][0]+offset+median)/16000,(ranges[-1][1]+offset+median)/16000))
        streams[name]=rail_metrics(data[:,index],support_intervals=support if speech else None)
        streams[name].update(relative_delay_by_nonoverlap_utterance=delays,relative_delay_median_samples=median,
            support_scope='Estimated first-to-last active source frame per utterance, retained50msRIR convention, exactinputoffset and approximateoutputlag; onset500ms is not calibrated AGC or phonetic timing')
        if median is not None:
            spread=max(abs(r['lag_samples']-median) for r in valid)
            alignment[name]={'processed_output_minus_recaptured_input_s':median/16000,
                'evidence':str(folder/'audio_metrics.json')+' relative_delay_by_nonoverlap_utterance; absolute correlation peak vs recaptured MIC0',
                'uncertainty_s':max(1,spread)/16000,'uncertainty_scope':'Observed across-utterance peak spread and one-sample grid only; not calibrated physical latency uncertainty',
                'full_device_latency_proven':False}
    output={'case_id':scene['case_id'],'batch':result['batch'],'analyzed_utc':now(),'streams':streams,'output_alignment':alignment,
        'input_payload':result['payload'],'input_scene_sha256':result['input_scene_sha256'],'recipe':result['recipe'],
        'input_source_to_decoded_offset_s':offset/16000 if offset is not None else None,
        'converter':audit_converter(folder),'analysis_code':bind(Path(__file__))}
    save(folder/'audio_metrics.json',output);return output

def analyze(batch):
    summary_path=REPORT/('audio_analysis_'+batch+'.json')
    frozen_path=REPORT/'OUTPUT_LEVEL_POLICY.json'
    if summary_path.exists() and frozen_path.exists():
        policy=read(frozen_path)
        if batch in policy['calibration_batches']:
            expected=next(b for b in policy['calibration_bindings'] if Path(b['path'])==summary_path)
            bind(summary_path,expected['sha256'])
            print('Frozen calibration analysis binding verified; original evidence preserved without rewriting.')
            return read(summary_path)
    if summary_path.exists():
        previous=read(summary_path)
        if all(c['analysis_code']['sha256']==bind(Path(__file__))['sha256'] for c in previous['cases']):
            for c in previous['cases']:
                folder=case_folder(c['case_id']) if batch=='final' else REPORT/'hardware'/batch/c['case_id'];receipt=read(folder/'case_result.json')
                assert receipt['input_scene_sha256']==c['input_scene_sha256']
                for b in receipt['output_audio'].values():bind(b['path'],b['sha256'])
                bind(c['converter']['native_file']['path'],c['converter']['native_file']['sha256'])
            print('Compatible completed audio analysis verified; no repeated analysis.')
            return previous
        raise RuntimeError('Existing analysis code differs; preserve and explicitly review a new analysis version')
    scenes={s['case_id']:s for s in read(BANK/'SCENE_MANIFEST.json')['scenes']};folder=REPORT/'hardware'/batch
    files=[r['folder']/'case_result.json' for r in accepted_cases().values()] if batch=='final' else sorted(folder.glob('S4_*/case_result.json'));cases=[]
    with Progress('audio_analysis_'+batch,len(files)) as progress:
        for p in files:
            if read(p)['status']!='PASS':continue
            row=analyze_case(p.parent,scenes[p.parent.name]);cases.append(row);progress.case=p.parent.name;progress.done+=1
    summary={'batch':batch,'cases':cases,'count':len(cases),'rail_totals':{s:sum(c['streams'][s]['rail_samples'] for c in cases) for s in ['O0','O1']},
        'peak_max':{s:max((c['streams'][s]['peak_fs'] for c in cases),default=None) for s in ['O0','O1']}}
    save(REPORT/('audio_analysis_'+batch+'.json'),summary)
    if batch=='final':save(REPORT/'output_alignment.json',{c['case_id']:c['output_alignment'] for c in cases})
    print(json.dumps({k:v for k,v in summary.items() if k!='cases'},indent=2));return summary

def freeze(recipe,calibration_batches):
    summaries=[read(REPORT/('audio_analysis_'+b+'.json')) for b in calibration_batches]
    assert any(s['batch']=='calibration_base' and s['count']==6 for s in summaries)
    cases=[c for summary in summaries for c in summary['cases']]
    peak=max(c['streams']['O0']['peak_fs'] for c in cases);gain_db=min(30,math.floor(20*math.log10(.25/peak)));gain=10**(gain_db/20)
    selected=[c for c in cases if c['recipe']==recipe];assert selected
    policy={'schema':'s4_output_level_v1','frozen':True,'frozen_utc':now(),'hardware_recipe':recipe,
        'fixed_host_gain':{'O0':gain,'O1':1.},'fixed_host_gain_db':{'O0':gain_db,'O1':0.},'device_AEC_ASROUTGAIN':1,
        'gain_location':'One host mono input adapter only; original PCM24 O0/O1 remain unchanged',
        'method':'floor dB gain taking largest raw O0 peak across all bounded calibration outputs to <=0.25FS, capped at +30dB. No H2 scores used.',
        'calibration_raw_O0_max_peak_fs':peak,'calibration_gained_O0_max_peak_fs':peak*gain,
        'calibration_batches':calibration_batches,'calibration_bindings':[bind(REPORT/('audio_analysis_'+b+'.json')) for b in calibration_batches],
        'selected_recipe_calibration_O1_rails':sum(c['streams']['O1']['rail_samples'] for c in selected),
        'selected_recipe_calibration_O1_max_peak_fs':max(c['streams']['O1']['peak_fs'] for c in selected),
        'no_per_utterance_normalization':True,'no_clipped_wav_repair_claim':True,'no_output_accuracy_winner':True,
        'final_headroom_exceedance_policy':'Retain original output, flag affected stream LIMITED; never silently alter frozen gain or clip/normalize offline',
        'source_level_policy_binding':bind(BANK/'SOURCE_LEVEL_POLICY.json'),
        'limitation':'Finite numerical calibration over this cohort/range; no absolute SPL or future-input guarantee'}
    path=REPORT/'OUTPUT_LEVEL_POLICY.json'
    if path.exists():raise RuntimeError('Output policy already frozen; preserve existing run')
    save(path,policy);save(BANK/'OUTPUT_LEVEL_POLICY.json',policy);print(json.dumps(policy,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--batch');p.add_argument('--freeze-recipe');p.add_argument('--calibration-batches',nargs='+');a=p.parse_args()
    if a.batch:analyze(a.batch)
    if a.freeze_recipe:freeze(a.freeze_recipe,a.calibration_batches)
