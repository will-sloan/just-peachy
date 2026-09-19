"""Compact enrollment-duration figure review; README_S6C_ENROLLMENT_FIGURE_REVIEW_V1.md."""
from pathlib import Path
from collections import Counter
import argparse,csv,hashlib,io,json,math
HERE=Path(__file__).resolve().parent;REPORT=HERE.parent/'reports/S6C/20260910T123540Z'
def read(path,expected=None):
 path=Path(path).resolve();raw=path.read_bytes();b=dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
 if expected is not None:assert b=={k:expected[k] for k in ('path','bytes','sha256')}
 return raw,b
def doc(path,expected=None):
 raw,b=read(path,expected);return json.loads(raw),b
def main(out):
 checks=0;used=[]
 def ok(value):
  nonlocal checks
  assert value;checks+=1
 def opened(path,expected=None):
  raw,b=read(path,expected);used.append(b);return raw,b
 figure,fb=doc(REPORT/'figures/enrollment_duration_v1/FIGURE_RECEIPT.json')
 ok(fb['sha256']=='79e13b463627d5ee6fdeb0069a404facd356c20ebad623fcac627cfe04f74b9e');used.append(fb)
 for b in [figure['source'],figure['readme'],figure['authority'],figure['table'],*figure['outputs']]:opened(b['path'],b);checks+=1
 authority,ab=doc(figure['authority']['path'],figure['authority'])
 ok(authority['status']=='COMPLETE_REQUESTED_NAME_INDEX' and figure['table'] in authority['tables'])
 raw,tb=opened(figure['table']['path'],figure['table']);table=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
 plot,pdb=doc(next(x['path'] for x in figure['outputs'] if Path(x['path']).name=='PLOT_DATA.json'))
 ok(plot['authority']==ab and plot['table']==tb and plot['sample_rate']==16000)
 fields=('source_turns','sole_active_samples','correct_name_samples','wrong_known_name_samples','unknown_name_samples')
 statuses={'ALL','ENROLLED','WITHHELD_OR_UNSELECTED','INTENDED_BUT_UNAVAILABLE','NO_GALLERY_CONTROL'}
 ids={'A':{5:'C141',15:'C142',30:'C143'},'B':{5:'C144',15:'C145',30:'C146'}}
 keyed={(r['profile_id'],r['stream'],r['roster_status']):r for r in table}
 ok(len(keyed)==len(table)==60)
 ok(set(keyed)=={(pid,tap,z) for m in ids.values() for pid in m.values() for tap in ('O0','O1') for z in statuses})
 points={(r['roster'],r['tier_sec'],r['stream']):r for r in plot['rows']}
 ok(len(points)==len(plot['rows'])==12)
 ok(set(points)=={(roster,tier,tap) for roster in ids for tier in ids[roster] for tap in ('O0','O1')})
 summaries=[];denoms={}
 for (roster,tier,tap),point in points.items():
  pid=ids[roster][tier];ok(point['profile_id']==pid)
  counts={}
  for z in statuses:
   row=keyed[pid,tap,z];ok(row['identity_tap']==tap and int(row['scored_scenes'])==240 and int(row['unmapped_turns'])==0)
   counts[z]={k:int(row[k]) for k in fields}
   for k in fields:ok(counts[z][k]==point['original_integer_counts'][z][k] and counts[z][k]>=0)
   v=counts[z];ok(v['correct_name_samples']+v['wrong_known_name_samples']+v['unknown_name_samples']==v['sole_active_samples'])
  for k in fields:ok(counts['ALL'][k]==sum(counts[z][k] for z in statuses-{'ALL'}))
  ok(counts['ALL']['source_turns']==777 and counts['ALL']['sole_active_samples']==28612432)
  for z in ('INTENDED_BUT_UNAVAILABLE','NO_GALLERY_CONTROL'):ok(all(counts[z][k]==0 for k in fields))
  e,w=counts['ENROLLED'],counts['WITHHELD_OR_UNSELECTED'];rate=100*e['correct_name_samples']/e['sole_active_samples'];seconds=w['wrong_known_name_samples']/16000
  ok(math.isclose(rate,point['correctly_named_enrolled_speech_percent'],rel_tol=0,abs_tol=1e-12))
  ok(seconds==point['withheld_wrong_known_source_seconds'])
  d=(e['source_turns'],e['sole_active_samples'],w['source_turns'],w['sole_active_samples'])
  if roster not in denoms:denoms[roster]=d
  ok(denoms[roster]==d)
  summaries.append(dict(roster=roster,tier=tier,tap=tap,enrolled_correct_percent=rate,withheld_wrong_known_source_sec=seconds))
 expected={'A':(267,8862040,510,19750392),'B':(246,8411960,531,20200472)}
 ok(denoms==expected)
 for roster in ids:
  for tap in ('O0','O1'):
   ordered=[points[roster,k,tap] for k in (5,15,30)]
   ok(all(a['correctly_named_enrolled_speech_percent']<b['correctly_named_enrolled_speech_percent'] for a,b in zip(ordered,ordered[1:])))
 caption=opened(next(x['path'] for x in figure['outputs'] if Path(x['path']).name=='CAPTION.md'))[0].decode()
 cp,cpb=doc(REPORT/'enrollment/common30_v1/COMMON30_GALLERY_PLAN.json');used.append(cpb)
 cc,ccb=doc(REPORT/'enrollment/common30_v1/COMMON30_GALLERY_COMPLETION.json');used.append(ccb)
 # Completed assembly explicitly binds the exact preparation plan.
 ok(any(isinstance(v,dict) and v.get('sha256')==cpb['sha256'] for v in cc.values()))
 membership={}
 for roster in ids:
  rows=[r for r in cp['rows'] if r['gallery_condition']=='COMMON30_FIXED_ROSTER_'+roster]
  ok({r['enrollment_tier'] for r in rows}=={5,15,30})
  people=set(rows[0]['available_identities']);membership[roster]=people
  ok(len(people)==14 and sum(x.startswith('CMU_ARCTIC_') for x in people)==9 and sum(x.startswith('HIFITTS_') for x in people)==5)
  for r in rows:ok(set(r['available_identities'])==set(r['intended_identities'])==people and not r['unavailable_identities'])
 ok(not membership['A']&membership['B'] and len(membership['A']|membership['B'])==28)
 prep,prepb=doc(REPORT/'enrollment_inventory/v2/PREPARATION_RECEIPT.json');used.append(prepb)
 raw,cb=opened(prep['tier_coverage']['path'],prep['tier_coverage']);coverage=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
 lookup={(r['identity'],int(r['requested_usable_seconds'])):r for r in coverage}
 duration_ranges=[]
 for roster,people in membership.items():
  prior={}
  for tier in (5,15,30):
   usable=[];whole=[]
   for person in people:
    r=lookup[person,tier];ok(r['status']=='AVAILABLE');source_ids=json.loads(r['source_ids'])
    if person in prior:ok(source_ids[:len(prior[person])]==prior[person])
    prior[person]=source_ids
    usable.append(float(r['actual_estimated_usable_seconds']));whole.append(float(r['actual_whole_clip_seconds']))
   duration_ranges.append(dict(roster=roster,target_estimated_usable_sec=tier,estimated_usable_min=min(usable),estimated_usable_max=max(usable),whole_clip_min=min(whole),whole_clip_max=max(whole)))
 ok('estimated usable-speech tiers' in caption and 'not identical measured durations' in caption)
 ok('not necessarily confirmed/stable' in caption and 'Missing name assignments remain in the denominator' in caption)
 out.parent.mkdir(parents=True,exist_ok=True)
 result=dict(status='PASS_NUMERIC_WITH_CAPTION_CORRECTIONS',check_count=checks,source_bindings=used,figure=fb,plot_data=pdb,rows_checked=60,series=4,points_per_series=3,point_values=summaries,roster_denominators={k:dict(enrolled_turns=v[0],enrolled_samples=v[1],withheld_turns=v[2],withheld_samples=v[3]) for k,v in denoms.items()},common_roster_people=dict(A=14,B=14,disjoint_union=28,each_corpus_counts={'CMU ARCTIC':9,'HiFiTTS':5},union_corpus_counts={'CMU ARCTIC':18,'HiFiTTS':10}),actual_duration_ranges=duration_ranges,
  corrections=[dict(scope='caption roster arithmetic',text='Each common roster has14 identities (9 CMU ARCTIC+5 HiFiTTS); A and B are disjoint,28 in their union. The current singular pool wording can imply14 total.'),dict(scope='caption intervention interpretation',text='Tiers retain nested whole-clip material; actual estimated speech duration, speech content, native window count and template change together. This is not an isolated duration-only intervention.')],
  review_source=read(__file__)[1],review_readme=read(HERE/'README_S6C_ENROLLMENT_FIGURE_REVIEW_V1.md')[1],new_scoring=False,plotting=False,individual_predictions_read=False,new_models=0,scope='Exact existing60 aggregate rows and12 plotted points independently reconciled; additional compact common roster and source-tier metadata only. Figure visuals remain covered by the separate root review. No figure/source data was edited.')
 with out.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
 print(json.dumps(read(out)[1]))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)

