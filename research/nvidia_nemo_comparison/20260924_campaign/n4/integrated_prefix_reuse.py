"""Verify and reuse an immutable method prefix. README_INTEGRATED_PREFIX_REUSE.md."""
import argparse
import ast
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
import time

from common import bind,fingerprint,freeze,load,verify
from metric_process import exact_process,identity,pin
from scoring_bank_v2 import admit,prediction,verify_bindings,writer_lock
from review_scoring_bank import guard,shared_allowance

HERE=Path(__file__).resolve().parent
STATUS='PASS_REUSABLE_V2_METHOD_PREFIX_ONLY'


def cap_only_sources():
    """Permit only declared constant/doc changes in event-producing methods."""
    records=[]
    for before,after,changes in (
        ('application_publication_v2.py','application_publication_v3.py',
         [('self.bytes>24*1024**2','self.bytes>64*1024**2')]),
        ('controller_projection_v2.py','controller_projection_v3.py',
         [('history_bytes>24*1024**2','history_bytes>64*1024**2'),('exceeds 24-MiB bound','exceeds 64-MiB bound')]),
        ('method_artifact_v2.py','method_artifact_v3.py',[('64 * 1024**2','128 * 1024**2'),('64*1024**2','128*1024**2')])):
        old=(HERE/before).read_text();new=(HERE/after).read_text()
        for a,b in changes:old=old.replace(a,b)
        def structure(text):
            tree=ast.parse(text)
            if isinstance(tree.body[0],ast.Expr) and isinstance(tree.body[0].value,ast.Constant):tree.body=tree.body[1:]
            return ast.dump(tree,include_attributes=False)
        if structure(old)!=structure(new):raise ValueError('Reuse requires exclusively declared history/artifact bound changes')
        records.extend([bind(HERE/before),bind(HERE/after)])
    return records


def validate_join(new,old,receipt):
    if (receipt.get('status')!=STATUS or new['scope']!=old['scope'] or new['jobs']!=old['jobs']
            or new['required']!=old['required'] or len(new['rows'])!=len(old['rows'])
            or len(receipt['cells'])!=receipt['completed'] or not 0<receipt['completed']<old['required']
            or len({b['path'] for b in receipt['cells']})!=receipt['completed']):
        raise ValueError('Reuse population differs')
    def context(c):return {k:v for k,v in c.items() if k not in ('code','qualification','reuse_review')}
    if context(new['context'])!=context(old['context']):raise ValueError('Reuse component/source/roster context differs')
    for current,previous in zip(new['rows'],old['rows']):
        if {k:v for k,v in current.items() if k!='cache_key'}!={k:v for k,v in previous.items() if k!='cache_key'}:
            raise ValueError('Reuse row contract/parent/order differs')


def load_reuse(plan):
    binding=plan['context'].get('reuse_review')
    if binding is None:return None
    if load(HERE/'INTEGRATED_HISTORY_CHECK_V3.json').get('private_prefix_review')!=binding:
        raise ValueError('Prefix reuse review is not the qualified exact receipt')
    verify(binding);receipt=load(binding['path']);verify(receipt['plan']);verify(receipt['terminal'])
    terminal=load(receipt['terminal']['path']);old=load(receipt['plan']['path'])
    if (exact_process(terminal['owner']) is not None or terminal['status']!='FAILED_PRESERVED'
            or terminal['plan']!=receipt['plan'] or terminal['cells']!=receipt['cells']
            or terminal['completed']!=receipt['completed']):raise ValueError('Reuse terminal is changed or active')
    if receipt['cap_only_sources']!=cap_only_sources():raise ValueError('Reuse history implementation changed')
    verify_bindings(receipt);validate_join(plan,old,receipt)
    return receipt


def reuse_cell(row,plan_binding,receipt,index):
    if not 0<=index<receipt['completed']:raise ValueError('Outside reviewed reusable prefix')
    b=receipt['cells'][index];verify(b);old=load(b['path'])
    if any(old[k]!=row[k] for k in ('cell_id','job_id','parents','contract')):raise ValueError('Reused cell differs')
    if old['plan']!=receipt['plan']:raise ValueError('Reused producer plan differs')
    verify_bindings(old)
    result=deepcopy(old);result.update(plan=plan_binding,cache_key=row['cache_key'],reused_from=b,
        execution_source='REUSED_VERIFIED_V2_METHOD_PREFIX')
    return result


def validate_reused(cell,row,plan_binding,receipt,index):
    if cell!=reuse_cell(row,plan_binding,receipt,index):raise ValueError('Reused receipt lost original producer provenance')


def review(run,output):
    process=pin();started=time.monotonic();bundle=admit(run);terminal=bundle['terminal'];plan=bundle['plan']
    local=Path(plan['context']['source_receipt']['path']).parents[2]
    if terminal['status']!='FAILED_PRESERVED' or terminal['completed']<=0:raise ValueError('Stopped preserved prefix required')
    if output.exists() or not output.resolve().is_relative_to((local/'n4').resolve()):raise ValueError('Fresh private review required')
    with writer_lock(local/'n4/metric-scoring.owner.lock'):
        guard(output,local,started,1800);inventory=shared_allowance(local);caps=cap_only_sources()
        code=[bind(HERE/n) for n in ('integrated_prefix_reuse.py','test_integrated_prefix_reuse.py','README_INTEGRATED_PREFIX_REUSE.md')]
        freeze(output/'ADMISSION.json',dict(owner=identity(process),terminal=bundle['terminal_binding'],plan=terminal['plan'],
            code=code,cap_only_sources=caps,inventory=inventory,maximum_seconds=1800,integrated_N4_cells=0))
        checked=0;digests=[]
        try:
            for row,b in zip(plan['rows'],terminal['cells']):
                guard(output,local,started,1800);verify(b)
                pred=prediction(load(b['path']),row,bundle['jobs'][row['job_id']])
                digests.append(fingerprint(pred));checked+=1
                if checked%128==0:print('Verified reusable prefix '+str(checked)+'/'+str(terminal['completed']),flush=True)
            for b in code+caps+[bundle['terminal_binding']]:verify(b)
            if exact_process(terminal['owner']) is not None:raise ValueError('Old worker reappeared')
            freeze(output/'RESULT.json',dict(status=STATUS,utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'),terminal=bundle['terminal_binding'],plan=terminal['plan'],
                completed=checked,cells=terminal['cells'],prediction_digests=digests,cap_only_sources=caps,
                all_full_artifacts_closures_and_conversion_verified=True,failed=terminal['failed'],
                not_tested=terminal['not_tested'],integrated_N4_cells=0,models_loaded=0,physical_widget_observed=False))
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(error_type=type(exc).__name__,checked=checked,admission=bind(output/'ADMISSION.json')))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();review(args.run,args.output)
