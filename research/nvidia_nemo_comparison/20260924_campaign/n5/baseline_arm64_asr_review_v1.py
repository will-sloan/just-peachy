"""Strict baseline component reader; README_BASELINE_ARM64_ASR_V1.md."""
import json
from pathlib import Path

CONFIG=dict(kind='start',sample_rate=16000,feature_dim=80,push_frames=1600,threads=1,
    padding_frames=10560,endpoint_rules=[2.4,1.2,20],decoding='greedy_search',
    max_active_paths=4,blank_penalty=0,provider='cpu')
CASES=('empty','short_tail','saved_source','saved_source_repeat')


def require(value,message):
    if not value:raise ValueError(message)


def pairs(items):
    value={}
    for k,v in items:
        require(k not in value,'Duplicate JSON key');value[k]=v
    return value


def review(path,frames):
    require(type(frames) is int and 1281<=frames<=960000,'Invalid admitted frames')
    raw=Path(path).read_bytes();require(len(raw)<=1024**2 and raw.endswith(b'\n'),'Output bound or final newline')
    def invalid(v):raise ValueError('Nonfinite JSON: '+v)
    rows=[json.loads(line,object_pairs_hook=pairs,parse_constant=invalid) for line in raw.decode('utf-8').splitlines()]
    require(len(rows)==10 and rows[0]==CONFIG,'Missing rows or different configuration')
    results=[]
    for index,(name,n) in enumerate(zip(CASES,(0,1281,frames,frames))):
        begin,end=rows[index*2+1:index*2+3]
        require(begin==dict(kind='case_start',case=name,frames=n),'Case order/source differs')
        require(set(end)=={'kind','case','frames','sent_frames','padding_frames','endpoint_resets','stream_closed','finals'},'Unexpected terminal fields')
        require(end['kind']=='case_closed' and end['case']==name and end['frames']==end['sent_frames']==n
            and end['padding_frames']==10560 and end['stream_closed'] is True,'Incomplete source/stream closure')
        require(type(end['endpoint_resets']) is int and 0<=end['endpoint_resets']<=n//1600+1,'Reset count invalid')
        require(isinstance(end['finals'],list) and len(end['finals'])<=end['endpoint_resets']+1,'Final count invalid')
        previous=0;finished=False
        for final in end['finals']:
            require(set(final)=={'text','sent_frames','phase'} and isinstance(final['text'],str)
                and 0<len(final['text'])<100000,'Invalid final text')
            sent=final['sent_frames'];require(type(sent) is int and previous<=sent<=n and not finished,'Invalid final source order')
            require(final['phase'] in ('endpoint','finish'),'Unknown final phase')
            if final['phase']=='finish':require(sent==n,'Tail source differs');finished=True
            else:require(sent>0 and (sent%1600==0 or sent==n),'Endpoint is not a push boundary')
            previous=sent
        results.append(end)
    require(results[2]['finals'] and results[2]['finals']==results[3]['finals']
            and results[2]['endpoint_resets']==results[3]['endpoint_resets'],'Resident stream parity differs')
    require(rows[-1]==dict(kind='complete',recognizer_closed=True,state_parity=True,CM5_tested=False,GUI_validated=False),'Missing normal recognizer closure')
    return dict(status='PASS_COMPONENT_TRANSCRIPT_AND_ENDPOINT_CONTRACT_ONLY',cases=results,
        source_frames=frames,state_parity=True,GUI_validated=False,CM5_tested=False)


def compare(reference,native):
    require(reference['status']==native['status']=='PASS_COMPONENT_TRANSCRIPT_AND_ENDPOINT_CONTRACT_ONLY','Unreviewed result')
    require(reference['source_frames']==native['source_frames'] and reference['cases']==native['cases'],'Windows/ARM64 component transcript or endpoint parity differs')
    return dict(status='PASS_WINDOWS_VS_EMULATED_ARM64_ASR_COMPONENT_PARITY',cases=4,
        frames=reference['source_frames'],precision='Existing INT8 encoder/joiner, FP32 decoder; no conversion',
        scope='Final raw transcript, endpoint source positions, reset counts and fresh-stream repeat; no token timestamps/PnC/GUI claim',
        GUI_validated=False,CM5_tested=False,N5_complete=False)
