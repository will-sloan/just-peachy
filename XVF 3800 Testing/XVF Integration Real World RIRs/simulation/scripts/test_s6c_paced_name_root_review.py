"""Independent name-emission oracle. See README_TEST_S6C_PACED_NAME_ROOT_REVIEW.md."""
from pathlib import Path
from datetime import datetime,timedelta,timezone
from itertools import product
from copy import deepcopy
import argparse,hashlib,json
import s6c_paced_name_emissions as subject

HELD_SHA='f3314d18dbd9578a9c2a6bf19b6aabb9306ab2415db9488aeae9fa1968ea2a3e'
def binding(path):
 p=Path(path).resolve();raw=p.read_bytes()
 return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def run():
 target=binding(subject.__file__);assert target['sha256']==HELD_SHA
 inherited=subject.fixtures();assert inherited['status']=='PASS' and inherited['checks']==30
 checks=[];oracle=0
 # Exhaustively enumerate six adjacent .1-second states. The oracle counts
 # integer native-time ticks and never calls the subject's run-merging logic.
 states=[('correct_name',True,0,'a'),('correct_name',False,0,'a'),
         ('wrong_known_name',True,0,'a'),('unknown_name',False,0,'a'),
         ('correct_name',True,1,'b')]
 for sequence in product(range(len(states)),repeat=6):
  intervals=[]
  for i,sid in enumerate(sequence):
   status,confirmed,occurrence,identity=states[sid]
   intervals.append(dict(start_sec=i/10,end_sec=(i+1)/10,name_status=status,
    segment_index=occurrence,reference_identity=identity,
    assigned_state=dict(confirmed=confirmed)))
  expected=[]
  for i,sid in enumerate(sequence):
   if sid not in (0,4) or i>0 and sequence[i-1]==sid:continue
   length=0
   while i+length<len(sequence) and sequence[i+length]==sid:length+=1
   if length>=5:
    expected.append(((i+5)/10,states[sid][2],states[sid][3]))
  got=subject.stable_runs(intervals)
  assert [(round(x['criterion_attainment_sec'],6),x['segment_index'],x['reference_identity']) for x in got]==expected
  oracle+=1
 checks.append('15625 integer-tick cases independently verify .5-second attainment, tentative/wrong/Unknown breaks and occurrence boundaries')
 origin=datetime(2026,1,1,tzinfo=timezone.utc)
 def event(kind,sec,p=None):
  return dict(event_type=kind,wall_time_utc=(origin+timedelta(seconds=sec)).isoformat(),payload=p or {})
 profile=dict(profile_id='pa',display_name='Alice',metadata_identity='corpus:a')
 gallery=dict(profiles=[profile],available_identities=['corpus:a'],intended_identities=['corpus:a'],
  gallery_condition='FIXED_ROTATION_A',enrollment_tier=15)
 support=dict(output_mappings={'O0':dict(source_with_rir_to_output_offset_samples=0)},
  all_speaker_reference_complete=True,turns=[
   dict(segment_index=0,source_id='a0',whole_clip_bin='1_to_2s',activity_available=True,file_support=[[0,16000]],active_ranges=[[0,16000]]),
   dict(segment_index=1,source_id='a1',whole_clip_bin='1_to_2s',activity_available=True,file_support=[[32000,48000]],active_ranges=[[32000,48000]])])
 q={('case',0):dict(source_id='a0',identity='corpus:a'),('case',1):dict(source_id='a1',identity='corpus:a')}
 value=dict(case_id='case',profile_id='candidate',stream='O0',identity_tap='O0',duration_sec=4.,decisions=[dict(evidence_id='e1')])
 admission=dict(source_kind='CANONICAL_SINGLE_SCENE_PAIR',realtime=True,native_session_complete=True,
  source_offset_samples=0,inserted_gap_samples=0,case_id='case',profile_id='candidate',asr_tap='O0',identity_tap='O0')
 closure=dict(state='COMPLETED',finalization_error=None,live_lanes_at_finalization=[],
  resident_bundle_lease_retained=False,event_and_transcript_handles_closed=True,
  finished_utc=(origin+timedelta(seconds=5)).isoformat())
 d=dict(evidence_id='e1',source_start_sec=0.,source_end_sec=.5,available_at_sec=.2,
  known_name='Alice',known_profile_id='pa',display_label='Alice',naming_state='confirmed')
 p=dict(utterance_id='u',text='word',source_start_sec=0.,source_end_sec=.5,latest_label='Alice',
  latest_known_name='Alice',latest_known_profile_id='pa',latest_naming_state='confirmed')
 events=[event('source_started',0),event('speaker_decision',1.25,dict(decision=d)),
  event('transcript_partial',1.5,p),event('session_completed',4.5)]
 analyze=lambda ee=events,v=value,s=support,g=gallery,qq=q,aa=admission,cc=closure:subject.analyze(ee,v,s,g,qq,aa,cc)
 result=analyze()
 assert result['turns'][0]['first_correct_decision_delay_sec']==1.25
 assert result['turns'][0]['first_stable_retained_row_delay_sec']==2.
 assert result['turns'][1]['first_correct_decision_status']=='NO_QUALIFIED_DECISION_EMISSION'
 assert result['retained_rows'][0]['exposure_row_sec']['correct_name']==3.5
 checks.append('Delayed native emission remains distinct from modeled .2s availability and an unobserved repeated occurrence')
 # Same person across separate source occurrences cannot qualify one spanning event.
 ee=deepcopy(events);ee[1]['payload']['decision']['source_end_sec']=2.5
 result=analyze(ee=ee)
 assert result['decisions'][0]['reference_status']=='MULTIPLE_SOURCE_OCCURRENCES'
 assert all(t['qualified_decision_emissions']==0 for t in result['turns'])
 checks.append('Repeated same-person occurrences are not merged into an attributable span')
 # A later ASR span cannot retroactively label an earlier unsupported row.
 ee=deepcopy(events);ee[2]['payload']['source_start_sec']=1.1;ee[2]['payload']['source_end_sec']=1.5
 ee.insert(3,event('transcript_final',2.5,p));result=analyze(ee=ee)
 assert result['intervals'][0]['name_status']=='unqualified_reference'
 assert result['intervals'][1]['name_status']=='correct_name'
 assert result['turns'][0]['first_stable_retained_row_delay_sec']==3.
 checks.append('A final arrived span never backfills earlier row qualification')
 # Empty final clears text; a revision must not resurrect it.
 ee=deepcopy(events);ee.insert(3,event('transcript_final',2.,dict(p,text='')))
 ee.insert(4,event('transcript_label_revision',2.1,dict(p,text=None)))
 result=analyze(ee=ee)
 assert result['retained_rows'][0]['exposure_row_sec']=={'correct_name':.5,'no_readable_text':3.}
 checks.append('Empty ASR clears readable exposure through subsequent label revision')
 # Two simultaneous rows intentionally produce overlapping row-seconds.
 ee=deepcopy(events);ee.insert(3,event('transcript_partial',2.,dict(p,utterance_id='v')))
 result=analyze(ee=ee,s=dict(support,turns=[]),qq={})
 assert result['strict_empty']['assigned_name_retained_row_sec']==6.5
 assert result['strict_empty']['assigned_name_retained_rows']==2
 assert result['strict_empty']['assigned_name_readable_emissions']==2
 assert result['strict_empty']['assigned_decision_emissions']==1
 assert all(r['first_correct_status']=='UNQUALIFIED_REFERENCE' for r in result['retained_rows'])
 checks.append('Empty controls preserve 6.5 overlapping assigned row-seconds without invented identity/WER')
 # A clock reversal makes timing unavailable while event counts remain exact.
 ee=deepcopy(events);ee[2]['wall_time_utc']=event('x',1.)['wall_time_utc']
 result=analyze(ee=ee)
 assert result['status']=='UNAVAILABLE_WALL_CLOCK_ORDER' and len(result['turns'])==2
 assert result['event_counts']['speaker_decision']==1 and len(result['clock']['reversals'])==1
 checks.append('Relevant UTC reversal invalidates metrics without sorting or deleting event counts')
 rejects=0
 for changed in (dict(admission,realtime=False),dict(admission,case_id='foreign'),
  dict(admission,source_offset_samples=1),dict(admission,inserted_gap_samples=1)):
  try:analyze(aa=changed)
  except ValueError:rejects+=1
  else:raise AssertionError('Invalid admission accepted')
 for changed in (dict(closure,finalization_error='error'),dict(closure,live_lanes_at_finalization=['speaker']),
  dict(closure,event_and_transcript_handles_closed=False),dict(closure,finished_utc=event('x',4.)['wall_time_utc'])):
  try:analyze(cc=changed)
  except ValueError:rejects+=1
  else:raise AssertionError('Invalid closure accepted')
 ee=deepcopy(events);ee.insert(2,deepcopy(ee[1]))
 try:analyze(ee=ee)
 except ValueError:rejects+=1
 else:raise AssertionError('Duplicate evidence accepted')
 try:analyze(v=dict(value,decisions=[]))
 except ValueError:rejects+=1
 else:raise AssertionError('Wrong prediction evidence accepted')
 checks.append('Ten route/pacing/closure/evidence identity mutations rejected')
 return dict(status='PASS_INDEPENDENT_SOURCE_AND_SYNTHETIC_ORACLE',target=target,
  helper=binding(__file__),readme=binding(Path(__file__).with_name('README_TEST_S6C_PACED_NAME_ROOT_REVIEW.md')),
  dependencies=[binding(subject.names.__file__),binding(Path(subject.__file__).with_name('README_S6C_PACED_NAME_EMISSIONS.md'))],
  inherited_fixture_count=inherited['checks'],integer_tick_oracle_cases=oracle,
  independent_checks=checks,negative_admission_cases=rejects,
  actual_native_cells_scored=0,new_neural_calls=0,new_policy_replays=0,
  scope='Independent pure review, not an empirical paced or accuracy result. Caller must separately admit actual source/closure/event/gallery/Q bytes.')

if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',required=True,type=Path);args=ap.parse_args()
 result=run()
 with args.output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
 print(json.dumps(binding(args.output)))

