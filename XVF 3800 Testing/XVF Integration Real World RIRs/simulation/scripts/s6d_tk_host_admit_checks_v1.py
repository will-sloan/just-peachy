"""Tiny metadata-only Tk/HOST admission checks; see README_S6D_TK_HOST_ADMIT_V1.md."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

def main(source_root,output):
    if output.exists():raise ValueError('Fresh G fixture output required')
    if output.drive.upper()!='G:':raise ValueError('G-only fixture output')
    source=source_root/'s6d_tk_host_admit_v1.py'
    spec=importlib.util.spec_from_file_location('tk_host_under_review',source);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    # Copied-source review uses canonical metadata discovery, without changing any gate.
    m.SIM=Path(r'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation')
    m.R=m.SIM/'reports/S6D/20260913T195357Z';m.P=m.R/'runner/native_execution_queue_preparation_v1'
    c12=m.R/'runner/beam_C_queue_proposed_v4/ROOT_ALL12_ACCEPTANCE.json'
    results=[]
    def check(name,fn):
        try:fn();results.append(dict(name=name,status='PASS'))
        except BaseException as e:results.append(dict(name=name,status='FAIL',error=repr(e)))
    def must(ok):
        if not ok:raise AssertionError('Predicate failed')
    def rejects(fn):
        try:fn()
        except (ValueError,KeyError,TypeError):return
        raise AssertionError('Unexpected admission')
    def actual_c12():
        b=m.bound(c12);must(b['sha256']==m.C12_SHA);doc=m.verified(b)
        must(doc['accepted']==doc['planned']==12 and doc['old_failure_credit']==0 and doc['all_owners_closed'] is True)
        for phase in doc['phase_closures']:m.phase_closure(phase)
        must(len(m.closed_instances(doc,14))==14)
    check('actual_bound_C12_two_saved_FINISH_phases_and14_identities',actual_c12)
    original={n:getattr(m,n) for n in ('verified','bound','read','plan','context','fresh','module','save')}
    docs={};base={'group':'tk8','C12':{'path':'C12'},'physical_bank':{'path':'BANK'},'queue':{'path':'QUEUE','sha256':'q'},'q':{'jobs':[{'job_id':'a'}]},'a':{},'manifests':{},'runner':{'path':'SYNTHETIC_RUNNER'}}
    fixed_plan={'group':'tk8','state_dir':'G:/synthetic_uncreated'}
    def phase(prefix,count):
        ids=[prefix+str(i) for i in range(count)];state='G:/synthetic_'+prefix
        q={'path':state+'/QUEUE.json','sha256':prefix};cb={'path':state+'/CHECKPOINT.json'};sb={'path':state+'/CLOSURE.json'}
        docs[q['path']]={'jobs':[{'job_id':i} for i in ids]}
        docs[cb['path']]={'run_id':'20260913T195357Z','queue_sha256':prefix,'status':'FINISH','active':None,'completed':{i:{'exit_code':0,'status':'DECLARED_ARTIFACTS_VERIFIED','identity':{'job_id':i}} for i in ids}}
        docs[sb['path']]={'run_id':'20260913T195357Z','result':{'action':'FINISH','done':count,'total':count},'owner_lock':'RELEASED_TO_IMMUTABLE_CLOSED_RECEIPT','keep_awake':{'restored':True},'hardware_restoration_unresolved':False,'payload_census_closure':{'closed':True,'snapshot':{'running':False,'error':None,'violation_latched':False}}}
        return {'queue':q,'state_dir':state,'checkpoint':cb,'supervisor_closure':sb}
    def instances(n):return [{'pid':100+i,'creation_time':1000.+i} for i in range(n)]
    phases=[phase('p',1),phase('r',11)];tkphase=phase('tk',8)
    docs['C12']={'status':'ROOT_ACCEPTED_C12_ALL12_COLLECTION','owner_thread_id':m.THREAD,'run_id':'20260913T195357Z','accepted':12,'planned':12,'old_failure_credit':0,'all_owners_closed':True,'phase_closures':phases,'closed_instances':instances(14)}
    docs['BANK_CLOSED']={'status':'ROOT_ACCEPTED_BANK_CLOSED','owner_thread_id':m.THREAD,'run_id':'20260913T195357Z','queue':base['physical_bank'],'all_owners_closed':True,'closed_instances':[{'pid':200,'creation_time':2000.}]}
    tq={'path':str(m.P/'tk8/QUEUE.json'),'sha256':'tk'}
    tkphase['queue']=tq;docs[tq['path']]={'jobs':[{'job_id':'tk'+str(i)} for i in range(8)]}
    docs['TK_CLOSED']={'status':'ROOT_ACCEPTED_TK8_FULL_SOURCE_UI_AND_OWNER_CLOSURE','owner_thread_id':m.THREAD,'run_id':'20260913T195357Z','queue':tq,'accepted':8,'planned':8,'all_owners_closed':True,'full_source_evidence_validated':True,'all_declared_Tk_view_evidence_validated':True,'phase_closure':tkphase,'closed_instances':instances(9)}
    review={'status':'ROOT_ACCEPTED_EXACT_TK_HOST_GROUP_FOR_ADMISSION','owner_thread_id':m.THREAD,'run_id':'20260913T195357Z','plan':fixed_plan,'allow_admission':True,'maximum_NN_stacks':1,'physical_supervisor_overlap':False,'prerequisite_acceptances':{'C12':base['C12'],'PhysicalBank':{'binding':{'path':'BANK_CLOSED'},'expected_status':'ROOT_ACCEPTED_BANK_CLOSED'}}}
    m.verified=lambda b:copy.deepcopy(docs[b['path']]);m.bound=lambda p:tq if Path(p)==m.P/'tk8/QUEUE.json' else {'path':str(p),'sha256':'review'}
    m.read=lambda p:copy.deepcopy(docs[str(p)]);m.plan=lambda c:copy.deepcopy(fixed_plan)
    def mutation(target,key,value,fn):
        old=copy.deepcopy(target);target[key]=value
        try:rejects(fn)
        finally:target.clear();target.update(old)
    gate=lambda:m.review_gate(review,base)
    check('Tk_positive_exact_predecessor_metadata',lambda:must(len(gate()[1])==15))
    check('unapproved_proposal_rejected',lambda:mutation(review,'allow_admission',False,gate))
    check('physical_overlap_rejected',lambda:mutation(review,'physical_supervisor_overlap',True,gate))
    check('omitted_physical_closure_rejected',lambda:mutation(review,'prerequisite_acceptances',{'C12':base['C12']},gate))
    check('foreign_C12_binding_rejected',lambda:mutation(review['prerequisite_acceptances'],'C12',{'path':'foreign'},gate))
    check('bank_unclosed_rejected',lambda:mutation(docs['BANK_CLOSED'],'all_owners_closed',False,gate))
    check('duplicate_closed_identity_rejected',lambda:mutation(docs['C12'],'closed_instances',[instances(1)[0]]*14,gate))
    check('predecessor_active_checkpoint_rejected',lambda:mutation(docs[phases[0]['checkpoint']['path']],'active',{'job_id':'p0'},gate))
    check('predecessor_open_census_rejected',lambda:mutation(docs[phases[0]['supervisor_closure']['path']]['payload_census_closure'],'closed',False,gate))
    host=copy.deepcopy(base);host['group']='host2';hr=copy.deepcopy(review);hr['prerequisite_acceptances']['Tk8']={'path':'TK_CLOSED'}
    hg=lambda:m.review_gate(hr,host)
    check('HOST_positive_requires_exact_Tk_source_UI_closure',lambda:must(len(hg()[1])==24))
    check('HOST_missing_UI_proof_rejected',lambda:mutation(docs['TK_CLOSED'],'all_declared_Tk_view_evidence_validated',False,hg))
    check('HOST_foreign_Tk_queue_rejected',lambda:mutation(docs['TK_CLOSED'],'queue',{'path':'foreign'},hg))
    # Exercise real admit orchestration. All service calls and writes are intercepted;
    # no ROOT_ADMISSION/APPROVAL file, scan, disk query or process is created.
    docs['ROOT_REVIEW']=review;m.context=lambda _:base;m.fresh=lambda _:None;calls=[]
    m.save=lambda p,v:(calls.append(('save',Path(p).name,copy.deepcopy(v))) or {'path':str(Path(p).resolve()),'bytes':len(m.encoded(v)),'sha256':hashlib.sha256(m.encoded(v)).hexdigest()})
    m.shutil.disk_usage=lambda _:SimpleNamespace(free=100*2**30)
    def services(reject_at=None):
        def decision(*args):
            calls.append(('allocation',))
            must(len(args[2])==15)
            if reject_at=='allocation':raise ValueError('Synthetic competing physical worker')
            return {'status':'SYNTHETIC_ONLY'}
        def validate(*args):
            calls.append(('V4_validation',))
            if reject_at=='V4':raise ValueError('Synthetic V4 rejection')
        return lambda p,*_:SimpleNamespace(runtime_snapshot=lambda:({'complete':True},{'pid':999}),allocation_decision=decision) if p==m.ALLOC else SimpleNamespace(validate_queue=validate)
    def transaction(reject_at=None):
        calls.clear();m.module=services(reject_at)
        if reject_at:rejects(lambda:m.admit('tk8','ROOT_REVIEW','review'));must(not any(x[0]=='save' for x in calls))
        else:
            m.admit('tk8','ROOT_REVIEW','review')
            must([x[0] for x in calls]==['allocation','V4_validation','save','save','save'])
            must([x[1] for x in calls if x[0]=='save']==['ADMISSION_PREFLIGHT.json','ROOT_ADMISSION.json','APPROVAL.json'])
    check('admit_validates_all_before_approval_written_last_intercepted',transaction)
    check('admit_V4_reject_writes_nothing',lambda:transaction('V4'))
    check('admit_competing_physical_reject_writes_nothing',lambda:transaction('allocation'))
    output.mkdir(parents=True);receipt={'status':'PASS' if all(x['status']=='PASS' for x in results) else 'FAIL','fixture_only':True,'tests':results,'count':len(results),'source':original['bound'](source),'real_process_or_device_queries':0,'actual_authority_files_created':0}
    (output/'RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt,indent=2))
    if receipt['status']!='PASS':raise SystemExit(1)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.source_root,a.output)
