"""Incremental disjoint enrollment evidence; each unique block is analyzed once."""
import hashlib
import numpy as np
from .people import vector_valid


class EnrollmentQuality:
    def __init__(self,models,config,target_sec):
        if target_sec not in (15,30,60):raise ValueError('Choose15,30or60 seconds')
        self.models=models;self.config=config;self.target=target_sec
        self.samples=0;self.clipped=0;self.accepted=[];self.vectors=[]
        self.hash=hashlib.sha256();self.model_segment_calls=0;self.model_embedding_calls=0

    def process(self,samples):
        samples=np.asarray(samples,np.float32).reshape(-1)
        if not 0<len(samples)<=160000 or not np.isfinite(samples).all():raise ValueError('Invalid enrollment block')
        offset=self.samples;self.samples+=len(samples)
        self.clipped+=int(np.count_nonzero(np.abs(samples)>=.999))
        self.hash.update(samples.astype('<f4').tobytes())
        padded=np.pad(samples,(0,160000-len(samples)))
        seg=self.models.segment(padded,include_posteriors=True);self.model_segment_calls+=1
        speech=seg.get('speech_probability',seg['speech']);overlap=seg.get('overlap_probability',seg['overlap'])
        for left in range(0,len(samples)-7999,8000):
            piece=samples[left:left+8000]
            lo=int(left/160000*len(speech));hi=max(lo+1,int((left+8000)/160000*len(speech)))
            rms=float(np.sqrt(np.mean(piece.astype(np.float64)**2)))
            if rms<self.config.minimum_rms or np.mean(np.abs(piece)>=.999)>.005:continue
            if float(np.mean(speech[lo:hi]))<.6 or float(np.mean(overlap[lo:hi]))>.2:continue
            self.accepted.append([(offset+left)/16000,(offset+left+8000)/16000])
            self.vectors.append(self.models.embed(piece));self.model_embedding_calls+=1

    def result(self,gaps=0,source_kind='user_consented_live'):
        centroid=None;consistency=0.
        if self.vectors:
            matrix=np.stack(self.vectors);centroid=vector_valid(np.mean(matrix,axis=0).astype(np.float32))
            consistency=float(np.quantile(matrix@centroid,.1))
        usable=len(self.accepted)*.5;clipping=self.clipped/max(1,self.samples)
        return {'elapsed_s':self.samples/16000,'usable_s':usable,'target_sec':self.target,
            'clipping':clipping,'consistency':consistency,'embedding_count':len(self.vectors),
            'accepted_intervals':self.accepted[:],'gaps':gaps,'source_kind':source_kind,
            'source_sha256':self.hash.hexdigest(),
            'model_segment_calls':self.model_segment_calls,'model_embedding_calls':self.model_embedding_calls,
            'can_save':bool(usable>=self.target and clipping<=.005 and consistency>=.3 and not gaps),
            'quality':'Unique nonoverlapping estimated clean speech; no automatic single-person guarantee'},centroid
