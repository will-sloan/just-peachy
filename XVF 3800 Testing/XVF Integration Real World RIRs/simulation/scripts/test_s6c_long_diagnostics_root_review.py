"""Independent source-only review; README_TEST_S6C_LONG_DIAGNOSTICS_ROOT_REVIEW.md."""
from pathlib import Path
import argparse,ast,hashlib,importlib,json,tempfile
from copy import deepcopy
HERE=Path(__file__).resolve().parent
EXPECTED='2e37e9b5c3cbb6021afbbf8768ed1e822fd20b7d9df6838e86c47ff590457d71'
def binding(p):
 p=Path(p).resolve();raw=p.read_bytes();return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def run(output):
 assert binding(HERE/'s6c_long_diagnostics_v1.py')['sha256']==EXPECTED
 m=importlib.import_module('s6c_long_diagnostics_v1');assert Path(m.__file__).resolve()==HERE/'s6c_long_diagnostics_v1.py'
 base=m.checks();assert base['check_count']==39
 checks=[]
 def ok(name,value):assert value,name;checks.append(name)
 def bad(name,fn):
  try:fn()
  except (ValueError,KeyError,TypeError):checks.append(name);return
  raise AssertionError(name)
 original=ast.parse((HERE/'s6c_paced_analysis_v1.py').read_bytes())
 wanted={n.name:ast.dump(n,include_attributes=False) for n in original.body if isinstance(n,ast.FunctionDef) and n.name in ('fail','number','utc_seconds','stats','trajectory_observations','active_context_observations')}
 tree=ast.parse((HERE/'s6c_long_diagnostics_v1.py').read_bytes())
 helper=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='pure_helpers')
 selected=next(ast.literal_eval(n.value) for n in helper.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='names' for t in n.targets))
 ok('Exact six pinned pure-function selection',selected==set(wanted))
 ok('Pure helper loader preserves original nodes',not any(isinstance(n,ast.Attribute) and n.attr in ('replace','visit') for n in ast.walk(helper)))
 for name in ('prepare','run'):
  fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
  ok(name+' refuses active quiet lease before reads',isinstance(fn.body[0],ast.Expr) and ast.unparse(fn.body[0])=='require_quiet()')
 def event(kind,p=None,source=0.,wall='2026-09-10T00:00:02+00:00'):
  return dict(event_type=kind,payload=p or {},source_time_sec=source,wall_time_utc=wall)
 rows=[event('source_started',wall='2026-09-10T00:00:00+00:00')]
 for i in range(2):
  rows.append(event('research_asr_dispatch',dict(source_start_sec=float(i),source_end_sec=float(i+1),native_endpoint=False,advisory_endpoint=False,reset_requested=False),float(i+1)))
 rows.extend([event('research_asr_drain',dict(source_end_sec=2.,padding_is_observed_audio=False,synthetic_right_padding_sec=.66)),
  event('transcript_partial',dict(text='later span',speaker='Speaker_2'),1.8),
  event('transcript_label_revision',dict(text='earlier span',speaker='Speaker_1'),.3),
  event('research_scheduler_watermark',dict(lane='asr',lane_closed=True)),
  event('research_scheduler_watermark',dict(lane='speaker',lane_closed=True)),event('session_completed')])
 def feed(data):
  e=m.Events(2.,'mature_only')
  for i,r in enumerate(data):e.consume(r,i)
  return e,e.finish()
 e,f=feed(rows)
 ok('Full integer blocks need no fabricated tail',f['asr_dispatch']['source_frames_from_dispatch_spans']==32000 and f['asr_dispatch']['tail_blocks']==0)
 ok('Native emission order preserves backward source cursor',[r['source_time_sec'] for r in e.retained]==[1.8,.3])
 ok('Native exact text/label revision payload remains intact',e.retained[1]['payload']==rows[5]['payload'])
 changed=deepcopy(rows);changed[5]['wall_time_utc']='2026-09-10T00:00:01+00:00'
 e,f=feed(changed);ok('Backward UTC recorded without sorting',f['wall_timestamp_reversal_count']==1 and e.retained[1]['emitted_from_source_started_sec']==1.)
 bad('Duplicate closed lane',lambda:feed(rows[:-1]+[rows[-2]]+rows[-1:]))
 bad('Missing completion',lambda:feed(rows[:-1]))
 bad('Observed failure',lambda:feed(rows[:-1]+[event('failure')]+rows[-1:]))
 bad('Source frame fractional sample',lambda:m.source_frame(.00001))
 bad('Nonfinite source duration',lambda:m.Events(float('inf'),'dual'))
 with tempfile.TemporaryDirectory(prefix='s6c_root_long_review_') as td:
  p=Path(td)/'input.jsonl';raw=b'{"id":1}\r\n\r\n{"id":2}\n';p.write_bytes(raw);b=binding(p);seen=[]
  got=m.stream_jsonl(b,lambda value,i:seen.append((i,value)))
  ok('Consumed bytes include blank lines and CRLF',got['bytes_consumed']==len(raw) and got['physical_lines']==3 and got['records']==2 and seen==[(0,dict(id=1)),(1,dict(id=2))])
  p.write_bytes(raw+b'{}\n');bad('Appended payload rejected',lambda:m.stream_jsonl(b,lambda *a:None))
  p.write_bytes(raw);bad('Wrong declared digest rejected',lambda:m.stream_jsonl(dict(b,sha256='0'*64),lambda *a:None))
  bad('Too-large declared input rejected before read',lambda:m.stream_jsonl(dict(b,bytes=m.MAX_FILE+1),lambda *a:None))
  bad('Boolean byte-count rejected',lambda:m.stream_jsonl(dict(b,bytes=True),lambda *a:None))
 sample=lambda t,phase,cpu,pids:dict(phase=phase,elapsed_from_native_launch_sec=t,process=dict(complete_process_tree=True,cpu_sec=cpu,processes=[dict(pid=x,creation_time=1.,threads=2) for x in pids]),telemetry={},event_queue_backlog=None)
 x=m.trajectory([sample(2.,'periodic',10.,[1,2]),sample(4.,'terminal_after_finalization',8.,[1])])
 ok('Membership changes and signed sampled counter delta retained',x['observed_membership_changes']==1 and x['process']['cpu_sec']['sampled_first_to_last_delta']==-2.)
 ok('Unobserved memory stays missing',x['process']['private_resident_uss_bytes']['missing']==2)
 ok('First sample offset is explicit',x['first_sample_elapsed_sec']==2.)
 value=dict(status='PASS_INDEPENDENT_SOURCE_REVIEW',helper=binding(HERE/'s6c_long_diagnostics_v1.py'),readme=binding(HERE/'README_S6C_LONG_DIAGNOSTICS_V1.md'),root_test=binding(__file__),root_readme=binding(HERE/'README_TEST_S6C_LONG_DIAGNOSTICS_ROOT_REVIEW.md'),owner_checks_reproduced=base['check_count'],independent_checks=checks,pure_function_ast_hashes={k:hashlib.sha256(v.encode()).hexdigest() for k,v in wanted.items()},model_calls=0,policy_replays=0,actual_long_sessions=0,actual_event_logs_read=0,scope='Source and synthetic fixtures only. Existing inventory V3 owns closed native chain admission. Actual analysis remains gated on exact closed owner/lease, byte hashes, event counts, dispatch coverage, finalization and terminal trajectory parity.')
 with output.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
 print(json.dumps(binding(output)))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);run(p.parse_args().output)

