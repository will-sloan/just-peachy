"""New all-bank alignment records without overwriting prior capture analysis. README_S6A.md."""
from pathlib import Path
import numpy as np
import soundfile as sf
from s6a_common import REPORT, bind, read, save, now
from s4_h2_analysis import rail_metrics, audit_converter
from s3_analyze import output_lag
from s4_h2_run import alignment_for

def analyze(folder,scene):
    target=REPORT/'capture_alignment'/scene['case_id']/'audio_metrics.json'
    inputs={'capture':bind(folder/'case_result.json'),'decoded':bind(folder/'decoded_six.wav'),'code':bind(__file__)}
    if target.exists():
        row=read(target);assert row['s6_inputs']==inputs;return row,bind(target)
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
            support_scope='Same S5 correlation estimator applied now to former reserve; numerical source support, not exact word timing')
        if median is not None:
            spread=max(abs(r['lag_samples']-median) for r in valid)
            alignment[name]={'processed_output_minus_recaptured_input_s':median/16000,
                'evidence':str(target)+' relative_delay_by_nonoverlap_utterance; absolute correlation peak versus recaptured MIC0',
                'uncertainty_s':max(1,spread)/16000,'uncertainty_scope':'Observed utterance peak spread and sample grid; not calibrated physical uncertainty',
                'full_device_latency_proven':False}
    output={'case_id':scene['case_id'],'analyzed_utc':now(),'streams':streams,'output_alignment':alignment,
        'input_payload':result['payload'],'input_scene_sha256':result['input_scene_sha256'],'recipe':result['recipe'],
        'input_source_to_decoded_offset_s':offset/16000 if offset is not None else None,
        'converter':audit_converter(folder),'s6_inputs':inputs,'historical_split':scene['split'],'s6_all240_authorized':True}
    save(target,output);return output,bind(target)
