"""Existing accelerated control for pure conversion. README_TEST_S6C_PACED_NATIVE_CONVERSION_V1.md."""
from pathlib import Path
import argparse,gzip,json,sys
import s6c_paced_analysis_v1 as target

R=target.REPORT
AUTH_SHA='332602ae80fd3239085f39e74f4234d903b59a9e6e481a358623efbb3212559c'
EPOCH2_SHA='1f7f0e10186eb1187d05d9be258372d6dfbe39ec3741c2ce2976a2ca3d005cdb'

def run(args):
 reader=target.ExactReader()
 authority=target.file_binding(R/'gallery_native_integration_review_v1/RESULT.json')
 assert authority['sha256']==AUTH_SHA
 audit=reader.json(authority)
 row=next(r for r in audit['native_chains'] if r['key']==['C105','O0','O0','S45_08_07'])
 prior=json.loads(gzip.decompress(reader.raw(row['prediction'])))
 receipt=reader.json(prior['identity']['source'])
 assert receipt['status']=='COMPLETE' and receipt['identity']['realtime'] is False
 spec_binding=target.file_binding(R/'EPOCH2_EXECUTION_MANIFEST.json');assert spec_binding['sha256']==EPOCH2_SHA
 spec=reader.json(spec_binding)
 profile_row=next(p for p in spec['profiles'] if p['candidate_id']=='C105' and p['asr_tap']=='O0' and p['identity_tap']=='O0')
 assert profile_row['profile']==prior['identity']['profile']
 # Explicit test projection: not a fabricated paced cell or native admission.
 source=dict(schema='TEST_ONLY_ACCELERATED_SOURCE_PROJECTION',actual_native_receipt=prior['identity']['source'],
  duration_sec=receipt['audio_duration_sec'],telemetry=receipt['identity']['telemetry'],
  scope='Only the pure converter uses this metadata projection; it is not a canonical paced source/manifest/cell and cannot pass paced inventory admission.')
 folder=R/'paced_analysis_checks/observed_accelerated_control_v1';folder.mkdir(parents=True,exist_ok=True)
 source_path=folder/'TEST_ONLY_SOURCE_PROJECTION.json'
 if not source_path.exists():target.save_json(source_path,source)
 sb=target.file_binding(source_path);assert reader.json(sb)==source
 job=dict(profile_row=profile_row,source=sb,gallery=receipt['identity']['gallery'],repetition=1,
  candidate_id='C105',case_id='S45_08_07',asr_tap='O0',identity_tap='O0')
 modules,Profile,Provider,Gallery=target.load_frozen_modules(spec,reader)
 events=reader.lines(receipt['events']);summary=reader.json(receipt['summary'])
 value,parity=target.native_prediction(events,summary,job,prior['identity']['source'],spec,modules,(Profile,Provider,Gallery),reader,{})
 assert parity['status']=='PASS',parity
 fields=('decisions','final_transcripts_first','final_transcripts_latest','final_transcripts_first_display','transcript_events','identity_events')
 for field in fields:
  assert target.canonical(value[field])==target.canonical(prior[field]),field
 observations=target.native_event_observations(events,source['duration_sec'])
 assert observations['event_counts']==receipt['actual_counts']
 context=target.active_context_observations(events)
 assert context['shared_dispatches']==178 and context['native_speech_gate_active']+context['native_speech_gate_inactive']==178
 result=dict(status='PASS_EXISTING_ACCELERATED_CONTROL_ONLY',schema='jp_s6c_paced_converter_control.v1',
  helper=target.file_binding(Path(__file__)),readme=target.file_binding(Path(__file__).with_name('README_TEST_S6C_PACED_NATIVE_CONVERSION_V1.md')),
  target_helper=target.file_binding(Path(target.__file__)),target_readme=target.file_binding(Path(target.__file__).with_name('README_S6C_PACED_ANALYSIS_V1.md')),
  source_authority=authority,source_prediction=row['prediction'],actual_native_source=prior['identity']['source'],
  test_projection=sb,actual_source_realtime=False,paced_cells_admitted=0,new_neural_calls=0,
  policy_replay_count=1,parity=parity,semantic_fields_compared=list(fields),event_counts=observations['event_counts'],
  active_context=context,consumed_source_buffers=reader.reads,
  scope='One existing accelerated native control validates pure observation extraction/replay/export conversion. Generated prediction stays in memory and is not published as paced evidence. This does not test paced source/owner/trajectory admission or count a new native session.')
 if args.output:print(json.dumps(target.save_json(args.output,result)))
 else:print(json.dumps({k:v for k,v in result.items() if k!='consumed_source_buffers'},indent=2))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path);run(p.parse_args())
