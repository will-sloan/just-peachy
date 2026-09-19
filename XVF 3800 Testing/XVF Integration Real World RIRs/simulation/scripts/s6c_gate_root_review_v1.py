"""Independent actual epoch4 gate admission review. See README_S6C_GATE_ROOT_REVIEW_V1.md."""
from pathlib import Path
from copy import deepcopy
from collections import Counter
import hashlib,json
SIM=Path(__file__).resolve().parents[1]
REPORT=SIM/'reports/S6C/20260910T123540Z'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def bind(p,sha=None):
 p=Path(p).resolve();raw=p.read_bytes();h=hashlib.sha256(raw).hexdigest()
 if sha is not None:assert h==sha,(str(p),h)
 return dict(path=str(p),bytes=len(raw),sha256=h)
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def checked(b):assert bind(b['path'])==b;return read(b['path'])
def main():
 sb=bind(REPORT/'EPOCH4_EXECUTION_MANIFEST.json','720a6cc6c1f9a11ea5d39c3c7f2ab52452aad507ea3d0e0a56fa2c3074af9945');spec=checked(sb)
 mb=bind(REPORT/'jobs/epoch4/explicit_gate6_v2_rep1.json','e688f4ae3f4c4d8bce133de00759ad8ceeac225a4f6275784c4ce0a5dec40ad5');manifest=checked(mb)
 ab=bind(REPORT/'orchestration/epoch4_gate6_scan_v2/ADMISSION.json','943a4604e6c6e1fdd6411b76a0bf6f6a217f61f82c8c223f5075ad3c2398c87d');admission=checked(ab)
 assert admission['jobs']==mb and admission['native_epoch']==sb and admission['workers']==4
 assert admission['status']=='PREPARED_FOR_REVIEW'
 for b in admission['sources']:assert bind(b['path'])==b
 proposal=checked(manifest['panel_proposal'])
 assert manifest['panel_proposal']['sha256']=='f303d7e80bc9dd8fa8b7ba7444216d1e6b29f75a0cce8762c40d92ce5201c6da'
 cases=proposal['family_native_gate_case_ids']
 pairs=[('C117','C118'),('C065','C079'),('C119','C120'),('C121','C122'),('C123','C124'),('C125','C126'),('C127','C128'),('C129','C130')]
 modes=['old_voice_gate','normalized_joint','reliability_joint','hypothesis_joint','semimarkov_joint','bounded_global_joint','quarantine_joint','shadow_gallery_joint']
 profiles={(p['candidate_id'],p['asr_tap'],p['identity_tap']):p for p in spec['profiles']}
 inputs={(r['case_id'],r['stream']):r for r in checked(spec['input_index'])['rows']}
 bank={r['case_id']:r for r in checked(spec['scene_manifest'])['scenes']}
 assert len(cases)==len(set(cases))==6 and all(c in bank for c in cases)
 assert manifest['requested']==len(manifest['jobs'])==192
 assert set(manifest['candidate_ids'])=={x for pair in pairs for x in pair}
 counts=Counter();seen=set();checks=0
 for pair,mode in zip(pairs,modes):
  for tap in ('O0','O1'):
   off,on=[profiles[(pid,tap,tap)] for pid in pair]
   assert off['cue_condition']=='CUES_OFF' and on['cue_condition']=='REAL_ALIGNED_CUES'
   aa,bb=[deepcopy(p['profile']) for p in (off,on)]
   for v in (aa,bb):
    assert v['tracker']['mode']==mode and v['tracker']['max_tracks']==64 and v['tracker']['lifecycle_policy']=='retire_archive'
    assert v['identity']['mode']=='none'
    v.pop('profile_id');v['tracker'].pop('cues_enabled')
   assert aa==bb,(pair,tap,'not one cue switch')
   checks+=1
 for job in manifest['jobs']:
  pid,cid,tap=job['candidate_id'],job['case_id'],job['asr_tap'];ident=job['identity']
  assert cid in cases and job['identity_tap']==tap and not job['realtime']
  profile=profiles[pid,tap,tap];inp=inputs[cid,tap]
  assert job['profile']==profile['profile'] and job['recipe_id']=='N01'
  assert job['job_key']==digest(ident) and job['job_key'] not in seen;seen.add(job['job_key'])
  assert ident['execution_digest']==spec['execution_digest']
  assert job['gallery'] is None and ident['gallery'] is None and ident['gallery_condition']=='NONE'
  assert job['asr_audio']==job['identity_audio']==inp['audio']
  assert job['asr_pcm_sha256']==job['identity_pcm_sha256']==inp['audio_pcm_sha256']
  assert job['duration_sec']==inp['duration_sec']
  assert ident['fresh_state'] is True and ident['inner_threads']==1
  assert ident['origin']=='same canonical capture sample-zero pair; no per-utterance alignment'
  assert ident['gain']==dict(O0='historical +3dB already applied once',O1='unity',adapter=1.)
  assert ident['cue_condition']==profile['cue_condition']
  assert job['telemetry']==(inp['telemetry'] if profile['cue_condition']=='REAL_ALIGNED_CUES' else None)
  for key in ('profile','asr_audio','identity_audio','telemetry','gallery','realtime'):assert ident[key]==job[key]
  target=Path(job['folder']).resolve()
  assert Path('G:/Just_Peachy_S6C/20260910T123540Z/epoch4').resolve() in target.parents
  assert not target.exists(),'Gate unexpectedly started'
  assert set(ident)=={'schema','execution_digest','profile','cue_condition','gallery_condition','enrollment_tier','asr_audio','identity_audio','telemetry','gallery','gain','origin','realtime','fresh_state','inner_threads','provider'}
  counts[pid,tap]+=1;checks+=1
 assert set(counts.values())=={6} and len(counts)==32
 assert not (REPORT/'orchestration/epoch4_gate6_scan_v2/STARTED.json').exists()
 out=REPORT/'independent_review/GATE192_ROOT_REVIEW_V1.json'
 value=dict(status='PASS_FOR_NATIVE_ADMISSION_NOT_EXECUTED',created_utc=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),checks=checks,
  jobs=mb,admission=ab,epoch=sb,panel=manifest['panel_proposal'],source=bind(__file__),readme=bind(Path(__file__).with_name('README_S6C_GATE_ROOT_REVIEW_V1.md')),
  native_jobs=0,case_ids=cases,pairs=pairs,scope='Independent exact registry, one-field cue companions,192 original job identities, complete paired grid, gain/origin/gallery and not-started checks. No models, outputs or source mutation. Original runner revalidates current resources, code/models and source payloads at actual launch.')
 with out.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
 print(json.dumps(bind(out),indent=2))
if __name__=='__main__':main()

