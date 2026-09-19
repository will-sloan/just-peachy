"""Offline failure-oriented transport checks; no Control call or audio stream."""
import argparse,json
from pathlib import Path
import numpy as np
from s3_hardware import payload_check
from measurement_app.core import decode_packed
from s0_common import save

def run(report):
    report=Path(report);q=np.load(report/'inputs/T1_tagged_expected24.npy');n=len(q)
    y=np.column_stack([q[:,2:],np.zeros((n,2),np.int32)])
    y=np.concatenate([np.zeros((53,6),np.int32),y])[:n]
    cases={}
    cases['common_offset_pass']=payload_check(y,q)['status']=='PASS'
    corrupt=y.copy();corrupt[40000,1]+=2;cases['one_payload_error_rejected']=payload_check(corrupt,q)['status']=='FAIL'
    corrupt=y.copy();corrupt[:,[0,1]]=corrupt[:,[1,0]];cases['swapped_mics_rejected']=payload_check(corrupt,q)['status']=='FAIL'
    corrupt=y.copy();corrupt[:,2]=-corrupt[:,2];cases['sign_flip_rejected']=payload_check(corrupt,q)['status']=='FAIL'
    corrupt=y.copy();corrupt[1:,3]=y[:-1,3];cases['one_mic_delay_rejected']=payload_check(corrupt,q)['status']=='FAIL'
    corrupt=np.delete(y,40000,axis=0);cases['dropped_group_rejected']=payload_check(corrupt,q)['status']=='FAIL'
    corrupt=np.insert(y,40000,y[40000],axis=0);cases['duplicated_group_rejected']=payload_check(corrupt,q)['status']=='FAIL'
    raw=y.reshape(-1,2).copy();raw[1::3]|=1;raw[2::3]|=1
    _,qc=decode_packed(np.concatenate([np.zeros((2,2),np.int32),raw,np.ones((1,2),np.int32)]),24)
    cases['partial_boundaries_separated']=qc['marker_error_count']==0 and qc['startup_frames_excluded']==2 and qc['trailing_frames']==1
    raw[100000,0]^=1;_,qc=decode_packed(raw,24);cases['midstream_marker_error_detected']=qc['marker_error_count']==1
    result={'status':'PASS' if all(cases.values()) else 'FAIL','checks':cases,'checks_passed':sum(cases.values()),'checks_total':len(cases),'physical_IO_calls':0}
    save(report/'offline_transport_checks.json',result);print(json.dumps(result,indent=2));assert all(cases.values())

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',required=True);a=p.parse_args();run(a.report)
