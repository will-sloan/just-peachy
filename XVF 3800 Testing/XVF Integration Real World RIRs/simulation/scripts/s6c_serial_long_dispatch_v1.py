"""Five exact prepared continuous sessions; README_S6C_SERIAL_LONG_DISPATCH_V1.md."""
from __future__ import annotations
import argparse,ast,copy,hashlib,importlib.util,json,math,types
from datetime import datetime,timedelta,timezone
from pathlib import Path
HERE=Path(__file__).resolve().parent
REPORT=HERE.parent/'reports/S6C/20260910T123540Z'
PAYLOAD=Path('G:/Just_Peachy_S6C/20260910T123540Z')
STAGING=HERE.parent/'staging/s6c/20260910T123540Z'
PINS={
 's6c_paced_dispatch_v3.py':'3815b657dd777fad3ca10a9bd7957a6fdaa4d1b5e6bf69a7be499764425bbbd2',
 's6c_long_native_epoch4_fast_v2.py':'079642ba24d59f625a6ae0c4342d9a26f51e56221f29b5a50f54830adfa22d67',
 's6c_long_b36_fast_v1.py':'6e18e18a4d133364c4b2a568339dac0365dd752a4ab090d23713bafd9102694e',
 's6c_long_b36_v1.py':'09b809f6301e696054c4563fdad0d48072ae22716bafcf9002a33bdffd866c66',
 's6c_historical_fast_observer_v1.py':'579963cb5e873a0a08504bb4f022ea8a92a158886d36abfd87ee4a0f9cd6d299'}
C_HELPER='s6c_long_native_epoch4_fast_v2.py'
B_HELPER='s6c_long_b36_fast_v1.py'
SPECS=[
 ('C065','long_native_epoch4/epoch4_long_c065_o0_fast_v2/MANIFEST.json','fd0cf760c5caed83c5340804bf4746a7402884d0d7c466e48f1d104e11724f62'),
 ('C067','long_native_epoch4/epoch4_long_c067_o0_fast_v2/MANIFEST.json','7827894c482464fe0099a349e897f932dc813995432b19c2f228977144c92675'),
 ('C088','long_native_epoch4/epoch4_long_c088_o0_fast_v2/MANIFEST.json','f4cd1952ed92dfb23aa1fcbc082df72dead2433b8de5819885d5ecd6e00a4c85'),
 ('C091','long_native_epoch4/epoch4_long_c091_o0_fast_v2/MANIFEST.json','1890486c14c2d3b044bb1d0fc5d2ee65c5e2fac982d80de87bc16c729b6e53d7'),
 ('B36','long_b36/b36_o0_continuous_fast_v1/MANIFEST.json','853499c10f3ea80de4cf5ab4e8569a9cf1c8008d6dcdb47ed486dd4d0528ffa7')]
QUEUE_SCHEMA='s6c-serial-long-queue.v1'
AUTH_SCHEMA='s6c-serial-long-authority.v1'
NAMESPACE='five_prepared_long_v1'
DURATION=1827.426625
FRAMES=29238826

def require(ok,message):
 if not ok:raise ValueError(message)
def pinned(name):
 p=HERE/name;require(hashlib.sha256(p.read_bytes()).hexdigest()==PINS[name],'Pinned source changed: '+name);return p
def module(name):
 p=pinned(name);s=importlib.util.spec_from_file_location('_long_dispatch_'+p.stem,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
D=module('s6c_paced_dispatch_v3.py')

def sources():
 rows=[D.binding(pinned(name)) for name in PINS]
 rows.extend(D.binding(HERE/name) for name in ('README_S6C_PACED_DISPATCH_V3.md','README_S6C_LONG_NATIVE_EPOCH4_FAST_V2.md','README_S6C_LONG_B36_FAST_V1.md','README_S6C_LONG_B36_V1.md','README_S6C_HISTORICAL_FAST_OBSERVER_V1.md','s6c_serial_long_dispatch_v1.py','README_S6C_SERIAL_LONG_DISPATCH_V1.md'))
 return rows

def exact_item(candidate,relative,sha):
 path=REPORT/relative;plan,pb=D.read(path);require(pb['sha256']==sha,'Exact prepared continuous manifest')
 is_b=candidate=='B36';helper=D.binding(pinned(B_HELPER if is_b else C_HELPER))
 require(D.dt(plan['deadline_utc'])==D.DEADLINE,'Original deadline and closure reserve unchanged')
 require(plan['composition']['sha256']=='bfa18ae06bb224faaad2d4f5096f2e6a0d1aebff5c7c16192d608739d3533bf3','Exact original composition')
 if is_b:
  require(plan['schema']=='s6c-exact-historical-b36-continuous-fast.v1' and len(plan['jobs'])==1,'Exact B36 continuous schema/job')
  j=plan['jobs'][0];require(j['profile_id']=='B36' and j['stream']=='O0' and j['duration_sec']==DURATION and j['realtime'] is True,'Original B36 O0 full source')
  require(helper in plan['sources'] and plan['timeout_sec']==DURATION+120 and plan['cleanup_max_sec']==25,'Original B36 source/time bounds')
  reserve=plan['timeout_sec']+plan['cleanup_max_sec']+60
 else:
  require(plan['schema']=='s6c-epoch4-long-native-admission.v1' and plan['actual_execution_epoch']=='epoch4','Exact C native schema/epoch')
  row=plan['profile_row'];require(row['candidate_id']==candidate and row['asr_tap']==row['identity_tap']=='O0','Exact C O0/O0 condition')
  require(helper in plan['dependencies'] and plan['duration_sec']==DURATION and plan['duration_samples']==FRAMES and plan['max_wall_sec']==7200,'Original C source/time bounds')
  reserve=DURATION+row['profile']['runtime']['lane_drain_timeout_sec']+180
 item=dict(item_id=plan['namespace'],candidate_id=candidate,helper=helper,manifest=pb,cells=1,output_root=str(path.parent),native_report_root=plan['report_root'],native_payload_root=plan['output_root'] if is_b else plan['payload_root'],source_sec=DURATION,minimum_remaining_sec=reserve)
 return item,plan

def fixed_items():
 pairs=[exact_item(*s) for s in SPECS];return [x[0] for x in pairs],[x[1] for x in pairs]

def unstarted(item,plan):
 require(not (Path(item['output_root'])/'invocations').exists(),'Prior continuous invocation requires root resolution; no resume')
 if item['candidate_id']=='B36':
  require(not (Path(plan['output_root'])/'jobs').exists() and not (Path(plan['report_root'])/'RESULT.json').exists(),'Prior historical native attempt')
 else:require(not Path(plan['report_root']).exists() and not Path(plan['payload_root']).exists(),'Prior C continuous native namespace')

def prepare(output):
 items,plans=fixed_items();before=sources()
 for i,p in zip(items,plans):unstarted(i,p)
 folder=Path(output).resolve();folder.mkdir(parents=True,exist_ok=False)
 q=dict(schema=QUEUE_SCHEMA,status='REGISTERED_FINITE_QUEUE',namespace=NAMESPACE,created_utc=D.utc(),items=items,total_sessions=5,total_source_sec=5*DURATION,source_bindings=before,scope='Exact existing five O0 continuous preparations, one session per item. No operating selection, new input, hardware or native work. The inherited dispatcher cells counter counts sessions here, never canonical scenes.')
 qb=D.save(folder/'QUEUE.json',q);require(sources()==before,'Source changed during metadata preparation')
 return D.save(folder/'PREPARATION.json',dict(status='PREPARED_NO_NATIVE_LAUNCH',queue=qb,source_bindings=before,requested_sessions=5,native_launches=0,original_manifests_unchanged=True,scope=q['scope']))

def admit(queue_binding,authority_binding):
 q,qb=D.read(queue_binding['path'],queue_binding);a,ab=D.read(authority_binding['path'],authority_binding)
 require(q['schema']==QUEUE_SCHEMA and q['status']=='REGISTERED_FINITE_QUEUE' and q['namespace']==NAMESPACE,'Exact finite continuous queue')
 items,plans=fixed_items();require(q['items']==items and q['total_sessions']==5 and q['total_source_sec']==5*DURATION and q['source_bindings']==sources(),'Exact unchanged five manifests/order/sources')
 require(a['schema']==AUTH_SCHEMA and a['status']=='AUTHORIZED_SERIAL_QUIET_LONG' and a['queue']==qb and a['dispatcher']==D.binding(__file__),'Exact root continuous queue/source authority')
 require(a['all_other_model_hil_work_stopped'] is True and a['all_heavy_analysis_stopped'] is True,'Root must establish quiet period')
 require(datetime.now(timezone.utc)<D.dt(a['expires_utc'])<=D.DEADLINE,'Original stage deadline')
 return q,qb,a,ab,plans

def quiet_payload(item,plan,deadline,ab,qb,owner):
 payload=dict(status='AUTHORIZED_FOR_QUIET_LONG_B36' if item['candidate_id']=='B36' else 'AUTHORIZED_FOR_QUIET_LONG_NATIVE',all_other_model_hil_work_stopped=True,all_heavy_analysis_stopped=True,expires_utc=deadline.isoformat(),root_authority=ab,queue=qb,dispatcher_owner=owner,item_id=item['item_id'],created_utc=D.utc())
 payload.update({'manifest':item['manifest']} if item['candidate_id']=='B36' else {'manifest_sha256':item['manifest']['sha256']})
 return payload

def ensure_start(item,plan,deadline,folder):
 unstarted(item,plan);require(datetime.now(timezone.utc)+timedelta(seconds=item['minimum_remaining_sec'])<deadline,'Original full-source/drain/closure reserve cannot fit')
 require(not (REPORT/'PACED_QUIET_OWNER.json').exists(),'Active quiet lease blocks next continuous session')
 before=[] if item['candidate_id']=='B36' else sorted(str(p.resolve()) for p in (REPORT/'observer_fast_v2/attempts').glob('*.json'))
 require(len(before)<=20000,'Bounded observer filename baseline')
 D.save(folder/'OBSERVER_BASELINE.json',dict(manifest=item['manifest'],paths=before,scope='Filename-only pre-launch baseline; no observer body/payload read.'))

def closed(owners,inspect):
 observations=[]
 for o in owners:
  require(D.finite_owner(o),'Exact recorded owner identity');v=inspect(o);require(v==dict(alive=False,error=None),'Recorded owner live/unknown/error');observations.append(dict(owner=o,observation=v))
 return observations

def scan_counters(rows):
 require(isinstance(rows,dict) and {str(Path(p).resolve()) for p in rows}=={str(p.resolve()) for p in (REPORT,STAGING,PAYLOAD)},'Exact three observer roots')
 for r in rows.values():
  for k in ('calls','successful','failed'):require(type(r[k]) is int and r[k]>=0,'Integer scan counter')
  require(r['calls']==r['successful']+r['failed'] and r['successful']>0 and type(r['last_bytes']) is int and r['last_bytes']>=0,'Actual scan count relationship')
  for k in ('total_wall_sec','total_cpu_sec','max_wall_sec'):require(type(r[k]) in (int,float) and math.isfinite(r[k]) and r[k]>=0,'Finite observer clock')

def observer(item,plan,owner,quiet):
 if item['candidate_id']=='B36':paths=list((Path(plan['report_root'])/'observer_invocations').glob('*/SCANNER_OUTCOME.json'))
 else:
  baseline,_=D.read(Path(quiet['path']).parent/'OBSERVER_BASELINE.json');require(baseline['manifest']==item['manifest'],'Exact observer baseline manifest')
  paths=[p for p in (REPORT/'observer_fast_v2/attempts').glob('*.json') if str(p.resolve()) not in set(baseline['paths'])]
 require(len(paths)==1,'One newly emitted run observer receipt')
 value,b=D.read(paths[0]);D.same_owner(value['owner'],owner)
 require(value['owner']['argv']==owner['argv'] and value['manifest']==item['manifest'] and value['wrapper']==item['helper'] and value['entry']=='run' and value['error'] is None,'Exact run observer identity')
 if item['candidate_id']=='B36':
  require(value['schema']=='s6c-historical-fast-observer-outcome.v1' and value['status']=='NATIVE_COMPLETE' and type(value['coordinator_pid']) is int and value['coordinator_pid']==owner['pid'] and value['sources_before']==value['sources_after']==plan['fast_observer']['sources'] and value['sources_unchanged'] is True,'Original B36 observer completion')
  scan_counters(value['storage_scans'])
 else:
  require(value['schema']=='s6c.fast_resource_observer_exit.v1' and value['status']=='RESTORED' and value['policy']==plan['observer_policy'] and value['installations'],'Original C observer restoration')
  spec,_=D.read(plan['execution_manifest']['path'],plan['execution_manifest']);common=[b for b in spec['execution_files'] if Path(b['path']).name=='s6c_common.py'];require(len(common)==1,'Exact frozen common')
  for r in value['installations']:
   require(r['common']==common[0] and r['restored'] is True and r['protected_admission_unchanged'] is True and r['original_callable']=='tree_bytes' and r['scanner_callable']=='ScanMeter(tree_bytes)','Original scanner installation restoration')
   scan_counters(r['scan_observations'])
 return b

def release_check(folder,item,owner,admission_binding,closure):
 r=closure['lease_release'];archive=folder/'QUIET_LEASE_RELEASED.json'
 require(r['status']=='RELEASED' and r['released'] is True and r['error'] is None and D.canonical(r['requested_archive'])==D.canonical(archive),'Exact original verified release')
 lease,b=D.read(archive,r['archived_binding']);D.same_owner(lease,owner)
 require(r['source']=={**b,'path':str(REPORT/'PACED_QUIET_OWNER.json')} and lease['manifest']==item['manifest'],'Original lease byte/manifest lineage')
 if item['candidate_id']!='B36':require(lease['kind']=='S6C_EPOCH4_LONG_NATIVE' and lease['admission']==admission_binding,'Original C lease admission')
 else:require(lease['kind']=='S6C_EXACT_HISTORICAL_B36_CONTINUOUS_FAST','Original B36 continuous lease kind')
 return lease,b

def c_complete(item,plan,owner,admission,ab,outcome,nb,closure,cb,inspect):
 for value in (admission,outcome,closure):
  D.same_owner(value['owner'],owner);require(value['owner']['argv']==owner['argv'][2:] and value['manifest']==item['manifest'],'Original C sys.argv/manifest')
 require(admission['status']=='ADMITTED_NOT_YET_COMPLETED' and outcome['status']=='NATIVE_COMPLETE_RELEASE_PENDING' and closure['status']=='NATIVE_COMPLETE_QUIET_LEASE_RELEASED','Original C completion statuses')
 require(closure['pre_release_outcome']==nb and outcome['admission']==closure['admission']==ab,'Original C outcome chain')
 for value in (outcome,closure):
  require(value['error'] is None and value['protected_functions_restored'] is True and value['original_result_not_rewritten'] is True,'Original C native/protected closure')
  require(value['source_composition_epoch']=='epoch2' and value['actual_execution_epoch']=='epoch4','Original C source/native epochs')
  for k,expected in [('profile_row',plan['profile_row']),('gallery',plan['gallery']),('source_composition',plan['composition']),('actual_execution_manifest',plan['execution_manifest']),('imports',plan['imports'])]:require(value[k]==expected,'Original C closure '+k)
 require(outcome['original_native_result']==closure['original_native_result'],'One bound C native result')
 n,b=D.read(outcome['original_native_result']['path'],outcome['original_native_result']);D.same_owner(n['owner'],owner)
 require(Path(plan['report_root']) in Path(b['path']).parents and n['schema']=='s6c_continuous_paced_native.v1' and n['status']=='COMPLETE' and n['profile']==plan['profile_row'] and n['composition']==plan['composition'],'Exact C native result/source/condition')
 require(n['source_duration_sec']==DURATION and n['long_session_gallery_condition']==plan['gallery_row'] and n['gallery_index']==plan['gallery_index'] and n['resident_bundle_loads']==n['resident_sessions_created']==1 and not n['live_owned_lanes'] and n['hardware_invocations']==0 and n['final_telemetry']['asr_cursor_sec']==DURATION,'Complete C source/roster/resident session')
 journals=n['native_journals'];require(set(journals)=={'audio_spool.pcm16','identity_audio_spool.pcm16'},'Original paired journals')
 for name,tap in [('audio_spool.pcm16',plan['profile_row']['asr_tap']),('identity_audio_spool.pcm16',plan['profile_row']['identity_tap'])]:require(journals[name]['bytes']==FRAMES*2 and journals[name]['sha256']==plan['pcm_sha256'][tap] and journals[name] in n['native_artifacts'],'Declared whole-source paired PCM')
 finals=[x for x in n['native_artifacts'] if Path(x['path']).name=='session_finalization_v3.json'];require(len(finals)==1,'Original C finalization declaration');f,fb=D.read(finals[0]['path'],finals[0])
 require(f['state']=='COMPLETED' and f['finalization_error'] is None and not f['live_lanes_at_finalization'] and not f['resident_bundle_lease_retained'] and f['event_and_transcript_handles_closed'] is True,'Original C finalized session')
 return [b,fb],closed([owner],inspect)

def b_complete(item,plan,owner,admission,ab,outcome,nb,closure,cb,inspect):
 for v in (admission,outcome,closure):D.same_owner(v['owner'],owner);require(v['owner']==owner and v['manifest']==item['manifest'],'Original B36 coordinator identity')
 require(admission['status']=='STARTED' and outcome['status']=='NATIVE_COMPLETE' and closure['status']=='NATIVE_COMPLETE_QUIET_RELEASED' and outcome['error'] is closure['error'] is None and closure['pre_release_outcome']==nb and outcome['continuous_result']==closure['continuous_result'],'Original B36 successful closure chain')
 result,rb=D.read(closure['continuous_result']['path'],closure['continuous_result']);job=plan['jobs'][0]
 require(Path(rb['path'])==Path(plan['report_root'])/'RESULT.json' and result['schema']=='s6c-exact-historical-b36-continuous-fast-result.v1' and result['status']=='COMPLETE_NATIVE_AND_OWNED_CHILD_CLOSED' and result['manifest']==item['manifest'] and result['owner']==owner and result['job']==job and result['original_worker_unchanged'] is True and result['all_owned_processes_closed'] is True,'Original B36 continuous result')
 require(result['composition']==plan['composition'] and result['historical_epoch']==plan['historical_epoch'] and result['source_duration_sec']==DURATION and result['source_duration_samples']==FRAMES,'Original B36 epoch/full source')
 require(result['owned_processes']==outcome['owned_processes']==closure['owned_processes'] and all(x['alive'] is False for x in result['owned_processes']),'Original B36 descendant closure')
 observations=closed([owner]+result['owned_processes'],inspect)
 out=Path(plan['output_root'])/'jobs'/job['job_id'];native,nativeb=D.read(result['native_result']['path'],result['native_result']);require(Path(nativeb['path'])==out/'WORKER_RESULT.json','Original B36 worker result path')
 ns=dict(require=require,Path=Path,DURATION=DURATION,FRAMES=FRAMES)
 node=next(n for n in ast.parse(pinned('s6c_long_b36_v1.py').read_bytes()).body if isinstance(n,ast.FunctionDef) and n.name=='validate_worker_result')
 exec(compile(ast.Module(body=[node],type_ignores=[]),str(HERE/'s6c_long_b36_v1.py'),'exec'),ns);ns['validate_worker_result'](native,job,result['native_owner'],out)
 child,childb=D.read(result['native_outcome']['path'],result['native_outcome']);require(Path(childb['path'])==out/'CONTINUOUS_OUTCOME.json' and child['schema']==result['schema'] and child['status']=='NATIVE_COMPLETE' and child['manifest']==item['manifest'] and child['native_result']==nativeb and child['job_key']==job['job_key'] and child['error'] is None and child['original_worker_function_unchanged'] is True,'Original B36 child outcome')
 require(outcome['native_result']==nativeb,'Original B36 parent/child native binding')
 expected=[str(D.EDGE),str(HERE/B_HELPER),'worker','--manifest',item['manifest']['path'],'--owner-lease',str(REPORT/'PACED_QUIET_OWNER.json')]
 require(child['owner']['argv']==expected,'Original B36 native child command')
 child_admission,cab=D.read(out/'CONTINUOUS_ADMISSION.json');launch,lb=D.read(out/'LAUNCH.json');D.same_owner(launch,child['owner'])
 require(child_admission['owner']==child['owner'] and child_admission['manifest']==item['manifest'] and child_admission['job']==job and child_admission['quiet_lease']==admission['quiet_lease'] and launch['argv']==expected and launch['manifest']==item['manifest'] and launch['job_key']==job['job_key'],'Original B36 child admission/launch/lease')
 D.same_owner(child['owner'],result['native_owner']);require(any(D.finite_owner(o) and (o['pid'],o['creation_time'])==(child['owner']['pid'],child['owner']['creation_time']) for o in result['owned_processes']),'Bound native child included in closed roster')
 return [rb,nativeb,childb,cab,lb],observations

def completion(item,plan,owner,quiet_binding,inspect=D.state):
 closed([owner],inspect);require(not (REPORT/'PACED_QUIET_OWNER.json').exists(),'Active lease blocks next session')
 folders=list((Path(item['output_root'])/'invocations').iterdir());require(len(folders)==1 and folders[0].is_dir(),'One original continuous invocation');folder=folders[0]
 admission,ab=D.read(folder/'ADMISSION.json');outcome,nb=D.read(folder/'NATIVE_OUTCOME.json');closure,cb=D.read(folder/'CLOSURE.json')
 require(admission['quiet_admission']==quiet_binding,'Original exact root-derived quiet authority');lease,lb=release_check(folder,item,owner,ab,closure)
 if item['candidate_id']=='B36':require(admission['quiet_lease']==closure['lease_release']['source'] and lease['quiet_admission']==quiet_binding,'Original B36 lease/admission');bindings,owners=b_complete(item,plan,owner,admission,ab,outcome,nb,closure,cb,inspect)
 else:bindings,owners=c_complete(item,plan,owner,admission,ab,outcome,nb,closure,cb,inspect)
 ob=observer(item,plan,owner,quiet_binding)
 return dict(status='ORIGINAL_LONG_SESSION_COMPLETE_AND_OWNERS_CLOSED',manifest=item['manifest'],cells=1,candidate_id=item['candidate_id'],invocation=str(folder),bindings=[ab,nb,cb,lb,ob]+bindings,owners=owners,scope='One exact continuous session transition. Journal hashes are native declarations; no audio/event payload reopened. Scientific diagnostics and final inventory remain separate.')

def execution_context():
 ns=dict(vars(D));ns.update(__file__=str(Path(__file__).resolve()),admit=admit,completion=completion,quiet_payload=quiet_payload,ensure_start=ensure_start)
 node=copy.deepcopy(next(n for n in ast.parse(pinned('s6c_paced_dispatch_v3.py').read_bytes()).body if isinstance(n,ast.FunctionDef) and n.name=='run'))
 changes=[]
 class Delta(ast.NodeTransformer):
  def visit_Constant(self,n):
   values={'serial_paced_dispatcher':'serial_long_dispatcher','README_S6C_PACED_DISPATCH_V3.md':'README_S6C_SERIAL_LONG_DISPATCH_V1.md','s6c-serial-paced-dispatch-result.v1':'s6c-serial-long-dispatch-result.v1'}
   if isinstance(n.value,str) and n.value in values:changes.append(n.value);return ast.copy_location(ast.Constant(values[n.value]),n)
   return n
  def visit_Assign(self,n):
   if len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='quiet':
    changes.append('quiet_payload');n=copy.deepcopy(n);n.value.args[1]=ast.parse('quiet_payload(item,plan,deadline,ab,qb,owner)',mode='eval').body
    return [ast.copy_location(ast.parse('ensure_start(item,plan,deadline,folder)').body[0],n),n]
   return self.generic_visit(n)
 node=Delta().visit(node);require(sorted(changes)==sorted(['serial_paced_dispatcher','README_S6C_PACED_DISPATCH_V3.md','s6c-serial-paced-dispatch-result.v1','quiet_payload']),'Only exact serial long run adaptations')
 exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),str(Path(__file__).resolve()),'exec'),ns)
 ns['_run_ast']=node;return types.SimpleNamespace(**ns)

def main():
 p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);p.add_argument('action',choices=['prepare','run']);p.add_argument('--output',type=Path);p.add_argument('--queue',nargs=2);p.add_argument('--authority',nargs=2);a=p.parse_args()
 if a.action=='prepare':require(a.output is not None,'Fresh metadata output required');result=prepare(a.output)
 else:require(a.queue is not None and a.authority is not None,'Exact root queue/authority bindings required');result=execution_context().run(a)
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
