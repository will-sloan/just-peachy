"""Focused synthetic checks for whole54 physical bank closure; see README_S6D_TK_HOST_ADMIT_V2.md."""
import argparse
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

def main(source_root,output):
    if output.exists() or output.drive.upper()!='G:':raise ValueError('Fresh G-only fixture output required')
    source=source_root/'s6d_tk_host_admit_v2.py'
    spec=importlib.util.spec_from_file_location('tk_host_f1_v2',source);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    docs={};state=m.BANK_STATE;nonce='a'*32
    qb={'path':str(m.BANK),'bytes':123,'sha256':m.BANK_SHA}
    ids=['synthetic_bank_stage_'+str(i) for i in range(54)]
    cp_ref={'path':str(state/'CHECKPOINT.json')};cl_ref={'path':str(state/('SUPERVISOR_CLOSURE_'+nonce+'.json'))};lock_ref={'path':str(state/('CLOSED_LOCK_'+nonce+'.json'))}
    roots=['SYNTHETIC_REPORT_ROOT','SYNTHETIC_G_ROOT','SYNTHETIC_LISTENING_ROOT']
    docs[qb['path']]={'schema':'s6d_approved_job_queue_v1','run_id':'20260913T195357Z','owner_thread_id':m.THREAD,'owner_session_id':m.THREAD,'runner_sha256':m.RUNNER_SHA,'jobs':[{'job_id':jid,'kind':'hardware'} for jid in ids],'payload_policy':{'new_payload_roots':roots,'max_new_payload_bytes':40*2**30}}
    children=[{'run_id':'20260913T195357Z','job_id':jid,'pid':1000+i,'creation_time':2000.+i} for i,jid in enumerate(ids)]
    docs[cp_ref['path']]={'run_id':'20260913T195357Z','queue_sha256':m.BANK_SHA,'status':'FINISH','active':None,'completed':{jid:{'identity':identity,'exit_code':0,'status':'DECLARED_ARTIFACTS_VERIFIED'} for jid,identity in zip(ids,children)}}
    docs[cl_ref['path']]={'run_id':'20260913T195357Z','result':{'run_id':'20260913T195357Z','action':'FINISH','done':54,'total':54,'job_id':None,'checkpoint_path':cp_ref['path']},'owner_lock':'RELEASED_TO_IMMUTABLE_CLOSED_RECEIPT','keep_awake':{'requested':True,'owned':True,'restored':True,'status':'RESTORED'},'hardware_restoration_unresolved':False,'payload_census_closure':{'closed':True,'snapshot':{'running':False,'error':None,'violation_latched':False,'has_complete':True,'stale':False,'pending':False,'logical_roots':roots,'accounted_bytes':12345}}}
    owner={'run_id':'20260913T195357Z','queue_sha256':m.BANK_SHA,'pid':9000,'creation_time':9000.25,'owner_nonce':nonce}
    docs[lock_ref['path']]=owner
    phase={'queue':qb,'state_dir':str(state),'checkpoint':cp_ref,'supervisor_closure':cl_ref,'closed_owner_lock':lock_ref}
    bank={'status':m.BANK_FINISH_STATUS,'owner_thread_id':m.THREAD,'run_id':'20260913T195357Z','queue':qb,'accepted':54,'planned':54,'all_owners_closed':True,'phase_closure':phase,'closed_instances':children+[owner]}
    docs['SYNTHETIC_BANK_ROOT']=bank
    proof={'binding':{'path':'SYNTHETIC_BANK_ROOT'},'expected_status':m.BANK_FINISH_STATUS};context={'physical_bank':qb}
    original_verified=m.verified;m.verified=lambda binding:deepcopy(docs[binding['path']])
    results=[]
    def must(ok):
        if not ok:raise AssertionError('Unexpected result')
    def reject(fn):
        try:fn()
        except (ValueError,KeyError,TypeError):return
        raise AssertionError('Unexpected acceptance')
    def check(name,fn):
        try:fn();results.append({'name':name,'status':'PASS'})
        except BaseException as exc:results.append({'name':name,'status':'FAIL','error':repr(exc)})
    gate=lambda:m.physical_bank_closure(proof,context)
    def mutation(target,key,value):
        prior=deepcopy(target);target[key]=value
        try:reject(gate)
        finally:target.clear();target.update(prior)
    def missing(target,key):
        prior=deepcopy(target);target.pop(key)
        try:reject(gate)
        finally:target.clear();target.update(prior)
    check('exact_complete54_existing_V4_shapes_accept55_closed_instances',lambda:must(len(gate())==55))
    check('old_partial_owner_only_status_rejected',lambda:mutation(proof,'expected_status','ROOT_ACCEPTED_BANK_CLOSED'))
    check('missing_phase_rejected',lambda:missing(bank,'phase_closure'))
    check('unlaunched_R_state_path_rejected',lambda:mutation(bank['phase_closure'],'state_dir',str(m.BANK.parent/'state')))
    check('root_accepted53_rejected',lambda:mutation(bank,'accepted',53))
    check('root_planned53_rejected',lambda:mutation(bank,'planned',53))
    cp=docs[cp_ref['path']]
    check('FINISH_but_only53_completed_jobs_rejected',lambda:mutation(cp,'completed',{k:v for k,v in cp['completed'].items() if k!=ids[-1]}))
    check('active_job_even_with54_completed_rejected',lambda:mutation(cp,'active',{'job_id':ids[-1]}))
    check('paused_checkpoint_rejected',lambda:mutation(cp,'status','REPORT_BLOCKED'))
    cl=docs[cl_ref['path']]
    check('supervisor_done53_rejected',lambda:mutation(cl['result'],'done',53))
    check('supervisor_points_to_foreign_checkpoint_rejected',lambda:mutation(cl['result'],'checkpoint_path','SYNTHETIC_FOREIGN_CHECKPOINT'))
    check('owner_lock_retained_rejected',lambda:mutation(cl,'owner_lock','RETAINED_UNRESOLVED_HARDWARE'))
    check('hardware_restoration_unresolved_rejected',lambda:mutation(cl,'hardware_restoration_unresolved',True))
    check('keepawake_unrestored_rejected',lambda:mutation(cl['keep_awake'],'restored',False))
    check('open_census_rejected',lambda:mutation(cl['payload_census_closure'],'closed',False))
    snapshot=cl['payload_census_closure']['snapshot']
    check('census_without_complete_accounting_rejected',lambda:mutation(snapshot,'has_complete',False))
    check('stale_census_rejected',lambda:mutation(snapshot,'stale',True))
    check('wrong_census_roots_rejected',lambda:mutation(snapshot,'logical_roots',['SYNTHETIC_SUBTREE_ONLY']))
    check('physical_shared40_exceeded_rejected',lambda:mutation(snapshot,'accounted_bytes',40*2**30+1))
    check('missing_immutable_owner_receipt_rejected',lambda:missing(bank['phase_closure'],'closed_owner_lock'))
    check('mismatched_owner_nonce_rejected',lambda:mutation(docs[lock_ref['path']],'owner_nonce','b'*32))
    check('missing_final_supervisor_identity_rejected',lambda:mutation(bank,'closed_instances',children))
    check('missing_completed_child_identity_rejected',lambda:mutation(bank,'closed_instances',children[1:]+[owner]))
    check('foreign_phase_queue_rejected',lambda:mutation(bank['phase_closure'],'queue',{'path':'FOREIGN','sha256':'0'*64}))
    check('duplicate_completed_child_process_identity_rejected',lambda:mutation(cp['completed'][ids[1]],'identity',{**children[1],'pid':children[0]['pid'],'creation_time':children[0]['creation_time']}))
    # Additional root-closed historical owners may coexist with the mandatory54+1.
    def extra_owner():
        prior=deepcopy(bank['closed_instances']);bank['closed_instances']=prior+[{'pid':9999,'creation_time':9999.5}]
        try:must(len(gate())==56)
        finally:bank['closed_instances']=prior
    check('additional_explicitly_closed_historical_owner_allowed',extra_owner)
    m.verified=original_verified
    output.mkdir(parents=True)
    receipt={'status':'PASS' if all(r['status']=='PASS' for r in results) else 'FAIL','fixture_only':True,'count':len(results),'checks':results,'source':m.bound(source),'scope':'Only synthetic PhysicalBank F1 closure shapes; no real current phase/lock/census read, context/admit call, inventory, disk query, device/model call or production authority write. Original16 V1 checks are preserved and not rerun.','actual_production_actions':0}
    (output/'RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':receipt['status'],'count':len(results),'receipt':m.bound(output/'RECEIPT.json')}))
    if receipt['status']!='PASS':raise SystemExit(1)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.source_root,a.output)
