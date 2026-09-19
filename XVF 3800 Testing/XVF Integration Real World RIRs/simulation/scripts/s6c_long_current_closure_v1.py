"""Current original-five closure audit; see README_S6C_LONG_CURRENT_CLOSURE_V1.md."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,importlib.util,json
HERE=Path(__file__).resolve().parent
REPORT=HERE.parent/'reports/S6C/20260910T123540Z'
SOURCE=HERE/'s6c_serial_long_dispatch_v1.py'
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()=='717767989610d84b40271ede22730804837fb02391baf0536d3e92a2d4830155'
spec=importlib.util.spec_from_file_location('_held_serial_long_current',SOURCE)
L=importlib.util.module_from_spec(spec);spec.loader.exec_module(L)
D=L.D
def run(output):
 output=Path(output).resolve()
 L.require(output.is_relative_to(REPORT.resolve()) and not output.exists(),'Fresh report metadata output')
 result,rb=D.read(REPORT/'serial_long_dispatcher/five_prepared_long_v1/RESULT.json')
 L.require(rb['sha256']=='ae6f4de9e2769b4505f32bbfa59fbef4288b54f4120554ed1cbe91746ddd0466','Exact original dispatcher result')
 L.require(result['status']=='DISPATCH_QUEUE_COMPLETE' and result['completed_batches']==result['requested_batches']==result['completed_cells']==5 and result['error'] is None and result['possible_child'] is None,'All original five dispatch transitions')
 dispatcher=L.closed([result['owner']],D.state)
 L.require(not (REPORT/'PACED_QUIET_OWNER.json').exists(),'No shared lease')
 items,plans=L.fixed_items();rows=[];observers=[]
 L.require(len(result['completed'])==5,'Exactly five completed records')
 for item,plan,record in zip(items,plans,result['completed']):
  L.require(record['item_id']==item['item_id'] and record['manifest']==item['manifest'] and record['candidate_id']==item['candidate_id'],'Original ordered condition')
  parent=REPORT/'serial_long_dispatcher/five_prepared_long_v1'/item['item_id']
  exit_record,eb=D.read(parent/'PARENT_EXIT.json')
  L.require(exit_record['returncode']==0,'Original observed parent exit0')
  owner=exit_record['owner'];L.closed([owner],D.state)
  quiet,qb=D.read(parent/'QUIET_ADMISSION.json')
  invocation=Path(record['invocation'])
  L.require(invocation.parent==Path(item['output_root'])/'invocations','Original invocation root')
  L.require(list(invocation.parent.iterdir())==[invocation],'One original invocation')
  admission,ab=D.read(invocation/'ADMISSION.json');outcome,nb=D.read(invocation/'NATIVE_OUTCOME.json');closure,cb=D.read(invocation/'CLOSURE.json')
  L.require(admission['quiet_admission']==qb,'Exact original derived quiet admission')
  lease,lb=L.release_check(invocation,item,owner,ab,closure)
  if item['candidate_id']=='B36':
   L.require(admission['quiet_lease']==closure['lease_release']['source'] and lease['quiet_admission']==qb,'Original B36 lease authority')
   bindings,owners=L.b_complete(item,plan,owner,admission,ab,outcome,nb,closure,cb,D.state)
  else:bindings,owners=L.c_complete(item,plan,owner,admission,ab,outcome,nb,closure,cb,D.state)
  # The dispatcher validated observer enumeration at each original transition.
  # Later C observers now exist, so use the exact immutable observer binding
  # admitted at that transition instead of repeating a time-relative baseline.
  obs=[b for b in record['bindings'] if Path(b['path']).name=='SCANNER_OUTCOME.json' or Path(b['path']).parent==REPORT/'observer_fast_v2/attempts']
  L.require(len(obs)==1,'One exact transition-admitted observer')
  ob,obb=D.read(obs[0]['path'],obs[0]);D.same_owner(ob['owner'],owner)
  L.require(ob['manifest']==item['manifest'] and ob['wrapper']==item['helper'] and ob['entry']=='run' and ob['error'] is None,'Original observer binding/identity')
  if item['candidate_id']=='B36':
   L.require(ob['status']=='NATIVE_COMPLETE' and ob['sources_unchanged'] is True and ob['sources_before']==ob['sources_after']==plan['fast_observer']['sources'],'Original historical observer sources')
   L.scan_counters(ob['storage_scans'])
  else:
   L.require(ob['status']=='RESTORED' and ob['policy']==plan['observer_policy'] and ob['installations'],'Original C observer restoration')
   for install in ob['installations']:
    L.require(install['restored'] is True and install['protected_admission_unchanged'] is True,'Original scanner/protected restoration')
    L.scan_counters(install['scan_observations'])
  for b in record['bindings']:D.read(b['path'],b)
  L.require(record['bindings']==[ab,nb,cb,lb,obb]+bindings,'Original transition proof unchanged')
  observers.append(obb)
  rows.append(dict(candidate_id=item['candidate_id'],manifest=item['manifest'],invocation=str(invocation),parent_exit=eb,original_returncode=exit_record['returncode'],quiet=qb,admission=ab,observer=obb,bindings=record['bindings'],current_owners=owners))
 L.require(len({b['path'] for b in observers})==5,'Five distinct original observers')
 receipt=dict(schema='s6c-original-five-long-current-closure.v1',status='ALL_FIVE_ORIGINAL_LONG_CLOSURES_CURRENTLY_VERIFIED',checked_utc=datetime.now(timezone.utc).isoformat(),dispatcher_result=rb,dispatcher_current=dispatcher,original_tool_session=92251,original_tool_session_exit=0,sessions=rows,original_observers=observers,shared_lease_present=False,source=D.binding(__file__),held_source=D.binding(SOURCE),readme=D.binding(HERE/'README_S6C_LONG_CURRENT_CLOSURE_V1.md'),new_native_sessions=0,scope='Exact original five metadata/native declarations/observer hashes/current owners and original exit0. Original transition-time observer proof remains bound; later observers do not replace it. No raw audio/events read and no scientific, diagnostic or full-study acceptance.')
 return D.save(output,receipt)
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);p.add_argument('--output',required=True,type=Path);a=p.parse_args();print(json.dumps(run(a.output),indent=2))

