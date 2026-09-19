"""Independent model-free audit of actual S6C enrollment. README_S6C_ENROLLMENT_RESULT_REVIEW.md."""
from pathlib import Path
import hashlib,io,json,os,sys
for n in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[n]='1'
import numpy as np
import soundfile as sf
import s6c_analysis as c

def run():
 edge=Path('C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe')
 if Path(sys.executable).resolve()!=edge.resolve():raise ValueError('Exact native EDGE interpreter required for bit-level enrollment arithmetic; analysis environment is a different numerical runtime')
 r=c.REPORT;root=r/'enrollment';doneb=c.bind(root/'ENROLLMENT_COMPLETION.json');done=c.verified(doneb)
 assert done['status']=='COMPLETE'
 plan=c.verified(done['plan']);assert done['plan']['sha256']=='6cbcd082b2afb7f640363d533211b93a3d79e69582f3e34a5306c3a20bca2e84'
 from importlib.metadata import version
 assert sys.version==plan['python'] and all(version(k)==v for k,v in plan['versions'].items())
 outputs={Path(b['path']).name:(b,c.verified(b)) for b in done['outputs']}
 material=c.verified(plan['material_manifest']);source={s['source_id']:s for s in material['accepted_sources']}
 coverage={(x['identity'],x['requested_usable_seconds']):x for x in material['coverage']}
 expected={k for k,x in coverage.items() if x['status']=='AVAILABLE'}
 checks=0;bindings=[];nodes={}
 for b in outputs['EMBEDDING_CACHE_INDEX.json'][1]['rows']:
  node=c.verified(b);assert node['status']=='COMPLETE' and node['identity']['plan_sha256']==done['plan']['sha256'];key=c.digest(node['identity']);assert Path(b['path']).stem==key and key not in nodes
  vb=node['vector'];raw=Path(vb['path']).read_bytes();assert len(raw)==vb['bytes'] and hashlib.sha256(raw).hexdigest()==vb['sha256'];v=np.load(io.BytesIO(raw),allow_pickle=False);assert v.shape==(192,) and v.dtype==np.float32 and np.isfinite(v).all()
  nodes[key]=v;bindings.append(b);checks+=3
 waves={}
 def wave(sid):
  if sid not in waves:
   s=source[sid];b=s['decoded_16k_binding'];assert c.bind(b['path'])==b
   x,sr=sf.read(b['path'],dtype='float32');assert sr==16000 and x.ndim==1 and len(x)==s['samples'];waves[sid]=x
  return waves[sid]
 def embedding(x):
  identity=dict(plan_sha256=done['plan']['sha256'],samples=len(x),waveform_sha256=hashlib.sha256(np.ascontiguousarray(x,dtype=np.float32).tobytes()).hexdigest())
  return nodes[c.digest(identity)]
 templates={};seen=set();max_centroid_delta=0.
 for row in outputs['TEMPLATE_INDEX.json'][1]['rows']:
  key=row['metadata_identity'],row['enrollment_tier'];assert key in expected and key not in seen;seen.add(key)
  rec=c.verified(row['receipt']);identity=rec['identity'];cov=coverage[key];assert rec['status']=='COMPLETE' and identity['metadata_identity']==key[0] and identity['tier']==key[1] and identity['source_ids']==cov['source_ids'] and identity['plan_sha256']==done['plan']['sha256']
  meta=c.verified(rec['metadata']);vb=rec['vector'];assert c.bind(vb['path'])==vb;vector=np.load(vb['path'],allow_pickle=False)
  assert meta['profile_id']==rec['profile_id'] and meta['display_name']==plan['people'][key[0]]['display_name'];assert [Path(x['path']).resolve() for x in meta['source_files']]==[Path(source[s]['decoded_16k_binding']['path']).resolve() for s in cov['source_ids']]
  vectors=[]
  for sid in cov['source_ids']:
   assert source[sid]['s6c_role']=='E' and source[sid]['identity']==key[0]
   x=wave(sid)
   for a in range(0,max(1,len(x)-8000+1),16000):vectors.append(embedding(x[a:a+32000]))
  matrix=np.stack(vectors);center=np.mean(matrix,axis=0);center=(center/np.linalg.norm(center)).astype(np.float32)
  delta=float(np.max(np.abs(center-vector)));max_centroid_delta=max(max_centroid_delta,delta);assert np.array_equal(center,vector) and meta['embedding_count']==len(vectors)
  consistency=float(np.min(matrix@center));assert consistency==meta['within_enrollment_consistency'];assert meta['quality_status']==('PASS' if consistency>=.3 else 'REVIEW_LOW_CONSISTENCY')
  templates[key]=(rec,vector);bindings.append(row['receipt']);checks+=9
 assert seen==expected and len(seen)==95
 scoremap=outputs['SCORER_GALLERY_MAP.json'][1];galleryindex=outputs['RESEARCH_GALLERY_INDEX.json'][1];assert scoremap['runtime_input'] is False and scoremap['status']=='COMPLETE'
 declared={(x['gallery_condition'],x['enrollment_tier'],x['case_id']):x for x in plan['galleries']};mapped={}
 manifests={}
 for row in scoremap['rows']:
  key=row['gallery_condition'],row['enrollment_tier'],row['case_id'];assert key not in mapped;planned=declared[key]
  for field in ('available_identities','intended_identities','unavailable_identities'):assert row[field]==planned[field]
  assert row['loaded_count']==len(row['available_identities'])==len(row['profiles'])
  for p in row['profiles']:
   rec,_=templates[p['metadata_identity'],row['enrollment_tier']];assert p['profile_id']==rec['profile_id'] and p['display_name']==plan['people'][p['metadata_identity']]['display_name']
  mapped[key]=row;manifests[row['manifest']['sha256']]=row['manifest'];checks+=5
 assert set(mapped)==set(declared) and len(mapped)==2169 and len(manifests)==176
 for row in galleryindex['rows']:assert row['manifest']==mapped[row['gallery_condition'],row['enrollment_tier'],row['case_id']]['manifest']
 loaded={}
 # Actual preserved loader, no model class imported or instantiated.
 sys.path.insert(0,plan['app_root']);from edge_speech_pipeline.speakers import ProfileStore
 for sha,b in manifests.items():
  g=c.verified(b);profiles=ProfileStore(Path(g['profile_root']),expected_backend_sha256=g['backend_sha256']).load();assert set(profiles)=={p['display_name'] for p in g['profiles']}
  for p in g['profiles']:
   m=c.verified(p['metadata']);assert c.bind(p['vector']['path'])==p['vector'];v=np.load(p['vector']['path'],allow_pickle=False);assert np.array_equal(profiles[p['display_name']],v/float(np.linalg.norm(v)))
  loaded[sha]=profiles;checks+=1+len(profiles)*2
 C=outputs['C_WINDOW_EMBEDDINGS.json'][1]['rows'];Cmap={};prior_end={}
 for row in C:
  sid=row['source_id'];s=source[sid];a,b=row['source_start_sample'],row['source_end_sample'];assert s['s6c_role']=='C' and row['metadata_identity']==s['identity'] and a%32000==0 and b==min(a+32000,s['samples']) and b-a>=8000 and a>=prior_end.get(sid,0)
  prior_end[sid]=b;vector=np.asarray(row['vector'],np.float32);assert np.array_equal(vector,embedding(wave(sid)[a:b]));key=(sid,a,b);assert key not in Cmap;Cmap[key]=row;checks+=3
 assert len(C)==702 and len({x['metadata_identity'] for x in C})==34
 amendment=c.verified(plan['calibration_amendment']);fits=[]
 for item in outputs['C_ONLY_CALIBRATION_INDEX.json'][1]['rows']:
  d=c.verified(item['receipt']);setting=next(x['settings'] for x in amendment['candidates'] if x['candidate_id']==item['candidate_id']);g=mapped[setting['gallery_condition'],setting['enrollment_tier'],None]
  members=d['known_metadata_identities'];assert set(members)==set(g['available_identities']);assert not set(d['withheld_metadata_identities'])&set(members)
  rows=[x for x in C if x['metadata_identity'] in members];assert len(rows)==d['total_window_queries'] and len(rows)==len(d['score_rows'])
  assert [{k:v for k,v in x.items() if k!='vector'} for x in rows]==d['score_rows'];assert d['known_people_without_C']==sorted(set(members)-{x['metadata_identity'] for x in rows})
  matrix=np.stack([loaded[g['manifest']['sha256']][plan['people'][p]['display_name']] for p in members]);scores=np.stack([matrix@np.asarray(x['vector'],np.float32) for x in rows]);assert np.array_equal(scores,np.asarray(d['cosine_scores'],np.float32))
  table=[]
  for threshold in amendment['fitted_rule']['threshold_grid']:
   for margin in amendment['fitted_rule']['margin_grid']:
    counts=dict(wrong_known_accepted=0,correct_known_accepted=0,unknown_rejected=0,total_queries=len(rows))
    for query,score in zip(rows,scores):
     rank=sorted(range(len(members)),key=lambda j:(-float(score[j]),j));a=rank[0];second=float(score[rank[1]]) if len(rank)>1 else -1.
     accepted=float(score[a])>=threshold and float(score[a])-second>=margin
     counts['unknown_rejected' if not accepted else 'correct_known_accepted' if members[a]==query['metadata_identity'] else 'wrong_known_accepted']+=1
    table.append(dict(score_threshold=threshold,margin_threshold=margin,**counts))
  winner=min(table,key=lambda x:(x['wrong_known_accepted'],-x['correct_known_accepted'],-x['score_threshold'],-x['margin_threshold']));assert table==d['grid'] and winner==d['selected']==item['selected'];assert set(d['calibration_metadata_identities'])<=set(members)
  fits.append(dict(candidate_id=item['candidate_id'],selected=winner,people=d['calibration_people'],clips=d['calibration_unique_clips'],known_people_without_C=d['known_people_without_C']));bindings.append(item['receipt']);checks+=9
 assert len(fits)==7
 result=dict(status='PASS',schema='s6c_actual_enrollment_independent_review.v1',checks=checks,completion=doneb,plan=done['plan'],source_bindings=bindings,
  reviewer_sources=[c.bind(Path(__file__)),c.bind(Path(__file__).with_name('README_S6C_ENROLLMENT_RESULT_REVIEW.md'))],runtime=dict(executable=sys.executable,python=sys.version,packages={k:version(k) for k in plan['versions']}),prior_review=c.bind(r/'independent_review/ACTUAL_ENROLLMENT_RESULT_REVIEW_V1.json'),prior_executor_lineage=c.bind(r/'independent_review/enrollment_review_executor_v1/SOURCE_LINEAGE.json'),initial_attempt_note='Initial invocation of the preserved V1 helper under the separate analysis interpreter failed exact centroid equality. It produced no accepted audit receipt; original-native-EDGE invocation then passed. V2 enforces that numerical runtime before reading payloads.',templates=len(templates),native_centroid_max_absolute_delta=max_centroid_delta,distinct_galleries=len(manifests),gallery_rows=len(mapped),empty_gallery_rows=sum(not x['available_identities'] for x in mapped.values()),C_windows=len(C),C_people=34,calibration_results=fits,
  scope='Reconstructed exact native centroids and C query vectors from hash-bound actual waveform cache; actual ProfileStore rosters; independently recomputed all32 calibration grid cells per candidate. No graph inference, Q audio processing, hardware, threshold retuning, or empirical Q identity claim.',model_calls=0,hardware_passes=0)
 out=r/'independent_review/ACTUAL_ENROLLMENT_RESULT_REVIEW_V2.json';c.save(out,result);print(json.dumps(dict(path=str(out),sha256=c.bind(out)['sha256'],checks=checks,templates=len(templates),galleries=len(manifests),fits=7)))

if __name__=='__main__':run()
