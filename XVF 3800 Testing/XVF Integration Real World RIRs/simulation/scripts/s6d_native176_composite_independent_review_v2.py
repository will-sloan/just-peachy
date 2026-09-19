"""Focused independent composite checks; README_S6D_NATIVE176_COMPOSITE_REVIEW_V2.md."""
import argparse
import ast
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import traceback


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    out=a.output.resolve();assert out.drive.casefold()=='g:' and 'review_fixtures' in out.parts and not out.exists();out.mkdir(parents=True)
    sys.path.insert(0,str(a.source_root));spec=importlib.util.spec_from_file_location('independent_composite',a.source_root/'s6d_native176_scoring_inputs_v2.py');n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n)
    cache=n.Cache();meta=n.metadata(cache);c=meta['composite'];old=c['original'];queue=meta['data']['queue'];cp=meta['original_checkpoint'];lock=cache.verified(old['closed_lock']);closure=cache.verified(old['supervisor_closure']);launch=cache.verified(meta['original_launch_ref']);rows=[]
    def check(name,fn):
        try:fn();rows.append(dict(name=name,status='PASS'))
        except BaseException:rows.append(dict(name=name,status='FAIL',error=traceback.format_exc()))
    def rejects(fn):
        try:fn()
        except (ValueError,KeyError,TypeError):return
        raise AssertionError('Expected rejection')
    def launch_positive():
        value=n.launch_exact(launch,old['queue'],old['approval'],n.B.STATE)
        assert value=={k:lock[k] for k in ('pid','creation_time')}
    check('actual_bound_original_launch_argv_and_exact_identity',launch_positive)
    def launch_negative():
        for mode in ('duplicate_queue_flag','foreign_approval_hash','missing_owned_awake'):
            value=deepcopy(launch)
            if mode=='duplicate_queue_flag':value['argv']+=['--queue',old['queue']['path']]
            elif mode=='foreign_approval_hash':value['argv'][value['argv'].index('--approval-sha256')+1]='0'*64
            else:value['argv'].remove('--keep-awake')
            rejects(lambda:n.launch_exact(value,old['queue'],old['approval'],n.B.STATE))
    check('ambiguous_or_foreign_saved_launch_arguments_rejected',launch_negative)
    def old_resources():
        for mode in ('unreleased_lock','unowned_awake','unclosed_census'):
            value=deepcopy(closure)
            if mode=='unreleased_lock':value['owner_lock']='RETAINED'
            elif mode=='unowned_awake':value['keep_awake']['owned']=False
            else:value['payload_census_closure']['closed']=False
            rejects(lambda:n.stopped_closed(queue,old['queue'],cp,lock,value,launch))
    check('historical_blocked_state_requires_all_owned_resources_closed',old_resources)
    def exact_recovery_science():
        count=0
        for sid,context in meta['contexts'].items():
            if context['origin']!='recovery_required':continue
            original=meta['data']['declared'][sid][1];fresh=context['job'];count+=1
            assert fresh['output']!=original['output'] and {k for k in original if original[k]!=fresh[k]}=={'output'}
            assert context['qjob']['job_id']==sid+'_recover1' and fresh['job_id']==sid
            assert context['manifest_ref']!=meta['data']['declared'][sid][0]
        assert count==5
    check('five_actual_metadata_jobs_only_output_changed_with_separate_execution_ID',exact_recovery_science)
    def full_source_loop_preserved():
        # Compare the exact sensitive guard call sequence, independently of author metric AST checks.
        trees=[ast.parse(Path(p).read_bytes()) for p in (n.PARENT,Path(n.__file__))]
        guard_names={'validate_completion','admit_full_source','dispatch','validate_reference','gallery_row'}
        sequences=[]
        for tree in trees:
            build=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='build')
            loops=[x for x in build.body if isinstance(x,ast.For) and any(isinstance(z,ast.Constant) and z.value=='completion_audit' for z in ast.walk(x))]
            assert len(loops)==1
            calls=[]
            for node in ast.walk(loops[0]):
                if not isinstance(node,ast.Call):continue
                f=node.func;name=f.id if isinstance(f,ast.Name) else f.attr if isinstance(f,ast.Attribute) else f.slice.value if isinstance(f,ast.Subscript) and isinstance(f.slice,ast.Constant) else None
                if name in guard_names:calls.append(name)
            sequences.append(sorted(calls))
        assert sequences[0]==sequences[1]==sorted(['validate_completion','admit_full_source','validate_completion','dispatch','validate_reference','gallery_row'])
    check('original_per_item_full_source_completion_dispatch_reference_gallery_guards_retained',full_source_loop_preserved)
    cache.unchanged();receipt=dict(status='PASS' if all(x['status']=='PASS' for x in rows) else 'FAIL',tests=rows,passed=sum(x['status']=='PASS' for x in rows),total=len(rows),fixture=cache.binding(__file__),reviewed_builder=cache.binding(n.__file__),composite=meta['composite_ref'],historical_metadata_only=True,actual171_output_audits=False,fresh5_outputs_read=False,actual_build=False,scoring=False,process_queries=0,device_calls=0,models=0)
    n.save(out/'RECEIPT.json',receipt);print(json.dumps(receipt,indent=2));return 0 if receipt['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
