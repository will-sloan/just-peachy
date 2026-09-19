"""Bounded native enrollment integration comparison; see README_S6C_NATIVE_GALLERY_REVIEW.md."""
from pathlib import Path
from collections import Counter
import argparse,csv,gzip,hashlib,io,json
import s6c_analysis_v3 as core
from s6c_family_native_results import paired as anonymous_pair

R=core.REPORT
CASES={'S45_01_06','S45_03_01','S45_04_05','S45_06_07','S45_08_07','S45_12_01'}
GROUPS={
 'gallery':('gallery_native_core_v3','gallery_native_names_v3','n01_gallery_panel_core_v2','n01_gallery_panel_names_v2',336,
  ['b04b4e035ae063b779db6289d4001a8c628ede76ab58a00aefd97a03e01dc175','c0629a0e7e7520a4863a27f15ccd41f813929ffd1e78154b04eab671d778b641','160f10fc744ea356e5ba76c4ea0fd79d376ce6c411e7887b8b75b24e0de7a96e','d1e9fd962cf2426ac1b635d0905a3cec0867531cd5143cedcd511abfdb493b1a']),
 'common':('common_duration_native_core_v3','common_duration_native_names_v3','common_duration_panel_core_v3','common_duration_panel_names_v3',72,
  ['ae9394152d7d949340f2abcb8c2722c2210fedf93914155fa847e19b541380fb','499c0680a5f3d6c7dd39f29a18395a8ed7086bfb99bb9fa5c20f56bacd87784c','22b68796c65eed6e343cd54920bfcf134985d1748aeffe3d45c4a408fae30bb4','8dc9b0b91769165c10220600e9fcb9d86aad844d173c07ea483f1bc278b826cb'])}
CLOCKS={'first_display_time','first_final_time','latest_label_time','first_known_name_time'}
IDS={'gallery':{f'C{x:03}' for x in range(87,117)}-{'C108','C109'},'common':{f'C{x}' for x in range(141,147)}}

def require(ok,message):
 if not ok:raise ValueError(message)
def raw(b):
 data=Path(b['path']).read_bytes()
 require(len(data)==b['bytes'] and hashlib.sha256(data).hexdigest()==b['sha256'],'Changed exact bound buffer')
 return data
def obj(b):
 data=raw(b)
 return json.loads(gzip.decompress(data) if str(b['path']).endswith('.gz') else data)
def key(x):
 return x.get('profile_id',x.get('candidate_id')),x.get('stream',x.get('asr_tap')),x['identity_tap'],x['case_id']
def unique(rows,allowed=None,turn=False):
 out={}
 for x in rows:
  k=key(x)
  if allowed is not None and k not in allowed:continue
  if turn:k=(*k,int(x['segment_index']))
  require(k not in out,'Duplicate selected key');out[k]=x
 return out
def table(receipt,name):
 matches=[b for b in receipt['tables'] if Path(b['path']).name==name];require(len(matches)==1,'Unique bound table required')
 return list(csv.DictReader(io.StringIO(raw(matches[0]).decode('utf-8-sig')))),matches[0]
def num(value):return None if value in (None,'') else float(value)
def turn_pair(a,b):
 require(key(a)==key(b) and a['segment_index']==b['segment_index'],'Turn identity differs')
 for f in ('metadata_identity','source_id','roster_status','whole_clip_bin','activity_available','status','sole_active_samples','mapped_file_support_samples','active_samples','excluded_other_source_overlap_samples'):
  require(a[f]==b[f],'Turn source/roster/support differs: '+f)
 result={f:a[f] for f in ('profile_id','stream','identity_tap','case_id','segment_index','metadata_identity','roster_status','sole_active_samples')}
 for f in ('correct_name_samples','wrong_known_name_samples','unknown_name_samples','first_any_name_wait_sec','first_correct_name_wait_sec','first_confirmed_correct_name_wait_sec','first_stable_correct_name_wait_sec'):
  av,bv=num(a[f]),num(b[f]);result.update({f+'_native':av,f+'_cached':bv,f+'_delta':av-bv if av is not None and bv is not None else None})
 for f in ('first_any_name_status','first_correct_name_status','first_confirmed_correct_name_status','first_stable_correct_name_status'):
  result.update({f+'_native':a[f],f+'_cached':b[f],f+'_equal':a[f]==b[f]})
 return result
def exports(value,view):
 return [{k:v for k,v in row.items() if k not in CLOCKS} for row in value[view]]
def native_input_guard(pred,native,inputs):
 require(native['identity']['telemetry']==pred['identity']['telemetry'] and native['identity']['cue_condition']==pred['identity']['cue_condition'],'Actual native cue input differs from predictor')
 pid,tap,itap,case=key(pred)
 require(native['identity']['asr_audio']==inputs[case,tap]['audio'] and native['identity']['identity_audio']==inputs[case,itap]['audio'],'Actual native PCM input declarations differ from canonical route')
def gallery_guard(pred,native,gallery):
 binding=pred['identity']['gallery']
 require(binding is not None and native['identity']['gallery']==binding,'Native and predictor gallery binding differ')
 require(native['identity']['profile']==pred['identity']['profile'],'Native actual profile differs from replay profile')
 wanted=sorted((x['profile_id'],x['display_name']) for x in gallery['profiles'])
 matches=[x for x in native['gallery_load_receipts'] if x['manifest']==binding]
 require(len(matches)==1,'One exact actual native gallery load receipt required')
 native_load=matches[0];replay_load=pred['snapshot']['scheduler']['identity']['gallery']
 for loaded in (native_load,replay_load):
  require(loaded['manifest']==binding and loaded['loaded_count']==len(wanted),'Gallery load count/manifest differs')
  require(sorted((x['profile_id'],x['display_name']) for x in loaded['templates'])==wanted,'Actual loaded profile identities differ')
 # Measured loader time is intentionally separate; compare every other receipt field.
 require({k:v for k,v in native_load.items() if k!='loaded_elapsed_sec'}=={k:v for k,v in replay_load.items() if k!='loaded_elapsed_sec'},'Native/replay load metadata differs')
 return len(wanted)

def tests():
 a=dict(profile_id='C',stream='O0',identity_tap='O0',case_id='x',segment_index='0',metadata_identity='p',source_id='s',roster_status='ENROLLED',whole_clip_bin='<1s',activity_available='True',status='SCORED',sole_active_samples='10',mapped_file_support_samples='20',active_samples='10',excluded_other_source_overlap_samples='0')
 for f in ('correct_name_samples','wrong_known_name_samples','unknown_name_samples','first_any_name_wait_sec','first_correct_name_wait_sec','first_confirmed_correct_name_wait_sec','first_stable_correct_name_wait_sec'):a[f]=''
 for f in ('first_any_name_status','first_correct_name_status','first_confirmed_correct_name_status','first_stable_correct_name_status'):a[f]='CENSORED'
 b=dict(a,correct_name_samples='2');a['correct_name_samples']='1'
 require(turn_pair(a,b)['correct_name_samples_delta']==-1,'Delta sign');n=1
 for f in ('source_id','sole_active_samples','roster_status'):
  try:turn_pair(a,dict(b,**{f:'wrong'}))
  except ValueError:n+=1
  else:raise AssertionError('Guard failed')
 try:unique([a,a])
 except ValueError:n+=1
 else:raise AssertionError('Duplicate admitted')
 require(exports({'first':[dict(text='x',latest_known_name='A',first_final_time=1)]},'first')==[dict(text='x',latest_known_name='A')],'Explicit clock projection');n+=1
 require(exports({'first':[dict(text='x',latest_known_name='B',first_final_time=1)]},'first')!=[dict(text='x',latest_known_name='A')],'Names must not be stripped');n+=1
 pred=dict(profile_id='C',stream='O0',identity_tap='O1',case_id='x',identity=dict(telemetry={'sha256':'cue'},cue_condition='REAL'))
 ni=dict(telemetry={'sha256':'cue'},cue_condition='REAL',asr_audio={'sha256':'a'},identity_audio={'sha256':'b'})
 inputs={('x','O0'):dict(audio={'sha256':'a'}),('x','O1'):dict(audio={'sha256':'b'})}
 native_input_guard(pred,dict(identity=ni),inputs);n+=1
 for f,v in [('telemetry',{'sha256':'wrong'}),('cue_condition','OFF'),('asr_audio',{'sha256':'wrong'}),('identity_audio',{'sha256':'wrong'})]:
  try:native_input_guard(pred,dict(identity=dict(ni,**{f:v})),inputs)
  except ValueError:n+=1
  else:raise AssertionError('Native input mismatch admitted')
 return dict(status='PASS',checks=n)

def run(group):
 nc,nn,cc,cn,count,shas=GROUPS[group];receipts=[];bindings=[]
 for ns,filename,sha in zip((nc,nn,cc,cn),('ANALYSIS_RECEIPT.json','NAME_ANALYSIS_RECEIPT.json')*2,shas):
  b=core.bind(R/ns/filename,sha);x=obj(b)
  require(x['status'] in ('COMPLETE_REQUESTED_INDEX','COMPLETE_REQUESTED_NAME_INDEX') and x['requested']==x['scored'],'Complete scored receipt required')
  require(x.get('unscored',x.get('failed_or_missing'))==0,'Failed scoring cannot be admitted')
  bindings.append(b);receipts.append(x)
 ncore,nname,ccore,cname=receipts
 require(ncore['input_index']==ccore['input_index'],'Native/cached canonical input authority differs')
 inputs={(x['case_id'],x['stream']):x for x in obj(ncore['input_index'])['rows']}
 require(ncore['index']==nname['index'] and ccore['index']==cname['index'],'Core/name prediction indexes differ')
 nidx,cidx=obj(ncore['index']),obj(ccore['index'])
 require(nidx['status']=='COMPLETE' and nidx['requested']==nidx['completed']==count and set(nidx['case_ids'])==CASES,'Exact native grid differs')
 require(cidx['status']=='COMPLETE','Cached index incomplete')
 native_rows=unique(nidx['rows']);cached_rows=unique(cidx['rows'],set(native_rows))
 expected={(p,t,t,c) for p in IDS[group] for t in ('O0','O1') for c in CASES}
 require(set(native_rows)==expected and core.expected_grid(nidx,CASES)==expected,'Exact fixed profile/case/tap product differs')
 require(len(native_rows)==count and set(cached_rows)==set(native_rows),'Missing matched cached prediction')
 require(all(t==it for p,t,it,c in native_rows),'Only declared same-tap gallery gates')
 native_sources={}
 for b in nidx['source_indices']:
  s=obj(b);require(s['status']=='COMPLETE' and s['worker_pool_joined'] is True and s['requested']==s['completed']==len(s['rows']),'Native source index/worker closure incomplete')
  for row in s['rows']:
   require(row['status'] in ('COMPLETE','COMPLETE_REUSED'),'Unsuccessful native source')
   require(row['job_key'] not in native_sources,'Duplicate actual native source key');native_sources[row['job_key']]=row['receipt']
 ns,nsb=table(ncore,'SCENE_RESULTS.csv');cs,csb=table(ccore,'SCENE_RESULTS.csv')
 nt,ntb=table(nname,'TURNS.csv');ct,ctb=table(cname,'TURNS.csv')
 nscene,cscene=unique(ns),unique(cs,set(native_rows))
 require(set(nscene)==set(native_rows) and set(cscene)==set(native_rows),'Core table grid differs')
 nturn,cturn=unique(nt,set(native_rows),True),unique(ct,set(native_rows),True)
 require(set(nturn)==set(cturn),'Naming occurrence support grid differs')
 comparisons=[anonymous_pair(nscene[k],cscene[k]) for k in sorted(native_rows)]
 turn_comparisons=[turn_pair(nturn[k],cturn[k]) for k in sorted(nturn)]
 galleries={};native_bindings=[];integrations=[]
 for k,row in sorted(native_rows.items()):
  pred,cached=obj(row['result']),obj(cached_rows[k]['result'])
  require(key(pred)==key(cached)==k and pred['status']==cached['status']=='COMPLETE','Prediction route/status differs')
  for f in ('profile','gallery','gallery_condition','enrollment_tier','cue_condition','telemetry'):
   require(pred['identity'][f]==cached['identity'][f],'Matched predictor setting differs: '+f)
  native_b=pred['identity']['source'];native=obj(native_b)
  require(native['status']=='COMPLETE' and native_sources.get(native['job_key'])==native_b and core.digest(native['identity'])==native['job_key'],'Native receipt authority differs')
  require(key(native)==k,'Native actual candidate/route differs')
  native_input_guard(pred,native,inputs)
  gal_b=pred['identity']['gallery'];gkey=gal_b['sha256']
  if gkey not in galleries:galleries[gkey]=obj(gal_b)
  loaded=gallery_guard(pred,native,galleries[gkey])
  finalization=obj(native['finalization'])
  require(finalization['state']=='COMPLETED' and finalization['finalization_error'] is None and not finalization['live_lanes_at_finalization'] and finalization['event_and_transcript_handles_closed'] is True and not finalization['resident_bundle_lease_retained'],'Native lane/handle closure differs')
  native_bindings.append(dict(key=k,receipt=native_b,prediction=row['result'],cached_prediction=cached_rows[k]['result'],finalization=native['finalization'],gallery=gal_b))
  integrations.append(dict(profile_id=k[0],stream=k[1],identity_tap=k[2],case_id=k[3],loaded_count=loaded,native_gallery_cache_hit=native['gallery_cache_hit'],native_gallery_admission_sec=native['gallery_admission_sec'],
   first_final_export_equal=exports(pred,'final_transcripts_first')==exports(cached,'final_transcripts_first'),
   latest_final_export_equal=exports(pred,'final_transcripts_latest')==exports(cached,'final_transcripts_latest'),
   first_display_export_equal=exports(pred,'final_transcripts_first_display')==exports(cached,'final_transcripts_first_display')))
 out=R/(group+'_native_integration_review_v1')
 require(not out.exists(),'Preserve existing review');out.mkdir()
 for name,rows in [('CORE_NATIVE_VS_CACHED.csv',comparisons),('NAME_TURNS_NATIVE_VS_CACHED.csv',turn_comparisons),('NATIVE_GALLERY_ADMISSION.csv',integrations)]:core.csv_write(out/name,rows)
 summary=[]
 for pid,tap,it in sorted({k[:3] for k in native_rows}):
  cells=[x for x in comparisons if x['profile_id']==pid and x['stream']==tap];turns=[x for x in turn_comparisons if x['profile_id']==pid and x['stream']==tap];ints=[x for x in integrations if x['profile_id']==pid and x['stream']==tap]
  row=dict(profile_id=pid,stream=tap,identity_tap=it,native_cells=len(cells),source_occurrences=len(turns),text_changed_cells=sum(not x['normalized_final_text_equal'] for x in cells),loaded_counts=sorted({x['loaded_count'] for x in ints}))
  for f in ('cp_latest_revised_errors','unknown_samples'):
   vals=[x['native_minus_cached_'+f] for x in cells];row[f+'_paired_cells']=sum(v is not None for v in vals);row[f+'_delta']=sum(v for v in vals if v is not None)
  for f in ('correct_name_samples','wrong_known_name_samples','unknown_name_samples'):
   vals=[x[f+'_delta'] for x in turns];row[f+'_paired_turns']=sum(v is not None for v in vals);row[f+'_delta']=sum(v for v in vals if v is not None);row[f+'_changed_turns']=sum(v is not None and v!=0 for v in vals)
  for f in ('first_final_export_equal','latest_final_export_equal','first_display_export_equal'):row[f+'_cells']=sum(x[f] for x in ints)
  summary.append(row)
 core.csv_write(out/'SUMMARY.csv',summary)
 result=dict(status='COMPLETE_ACTUAL_NATIVE_GALLERY_INTEGRATION_REVIEW',group=group,native_cells=count,source_occurrences=len(turn_comparisons),profiles=sorted({k[0] for k in native_rows}),cases=sorted(CASES),receipts=bindings,native_source_indices=nidx['source_indices'],source_tables=[nsb,csb,ntb,ctb],native_chains=native_bindings,summary=summary,tests=tests(),source=core.bind(__file__),readme=core.bind(Path(__file__).with_name('README_S6C_NATIVE_GALLERY_REVIEW.md')),inherited_pair_helper=core.bind(Path(__file__).with_name('s6c_family_native_results.py')),artifacts=[core.bind(p) for p in sorted(out.glob('*.csv'))],
  scope='Actual native receipt/profile/gallery/loader/closure checks plus same candidate/case/tap comparison to earlier cached policy scores. Native and replay gallery receipt fields agree apart explicitly excluded measured loaded_elapsed_sec. Export equality excludes only four listed measured clocks, preserving words, source boundaries and name/anonymous fields.',
  clock_fields_excluded=sorted(CLOCKS),limitations=['Same six source scenes are duplicated integration checks, not independent accuracy samples or additional full-bank counts.','Native audio/model/vector/event payloads are transitively bound by completed native receipts and original parity checks, not reread here.','Fresh inference/availability may change scores; deltas are retained and do not establish bit-exact vectors or clocks.','Gallery admission time is separate from one-time cached loader provenance and is not cold model load.','No new models, policy replay, source scoring or tuning.'])
 core.save(out/'RESULT.json',result);return core.bind(out/'RESULT.json')

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--group',choices=GROUPS);p.add_argument('--test',action='store_true');a=p.parse_args()
 if not a.test and a.group is None:p.error('--group is required')
 print(json.dumps(tests() if a.test else run(a.group)))
