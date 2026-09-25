"""Re-score 51 existing saved checks through owned metric IPC. README_SCORING_BANK.md."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import time
from common import bind,fingerprint,freeze,load,verify
from integrated_scoring_adapter import read_artifact,read_component_events,convert
from metric_process import MetricProcess,identity,pin
from probe_integrated_scoring import verify_environment,private_bytes,guard
from scoring_bank import code_bindings,writer_lock


def run(args):
    p=pin();here=Path(__file__).resolve().parent
    qualification=load(here/'INTEGRATED_SCORING_CHECK_V1.json')
    parent_binding=qualification['private_receipt'];verify(parent_binding);parent=load(parent_binding['path'])
    if parent['status']!='PASS_51_DEVELOPMENT_METHOD_SCORING_CHECKS' or parent['cases']!=51:raise ValueError('Saved qualification differs')
    verify(parent['admission']);admission=load(parent['admission']['path'])
    for b in parent['code']:verify(b)
    local=Path(parent_binding['path']).parents[2];policy=load(local/'supervision/campaign.json');started=time.monotonic()
    if args.output.exists() or not args.output.resolve().is_relative_to((local/'n4').resolve()):raise ValueError('Fresh private output required')
    with writer_lock(local/'n4/metric-scoring.owner.lock'):
        checked=verify_environment(admission['environment']);verify(admission['truth'])
        truths={r['job_id']:r for r in load(admission['truth']['path'])['cells']}
        guard(args.output,policy,started);size=private_bytes(local)
        if size+6*1024**3+256*1024**2>min(50,policy['resource_policy']['new_payload_allowance_gib'])*1024**3:
            raise ValueError('Shared payload allowance unavailable')
        code=code_bindings();args.output.mkdir(parents=True,exist_ok=False)
        freeze(args.output/'ADMISSION.json',dict(owner=identity(p),parent=parent_binding,code=code,
            environment=admission['environment'],environment_files_verified=checked,truth=admission['truth'],cases=51,
            cell_timeout_seconds=30,private_bytes_at_start=size,models_loaded=0,integrated_N4_cells=0))
        c=MetricProcess();checks=[]
        try:
            hello=c.start()
            for i,b in enumerate(parent['results']):
                guard(args.output,policy,started);verify(b);r=load(b['path'])
                for bound in [*r['inputs'],r['consumer_closure']]:verify(bound)
                a,s=[load(v['path']) for v in r['inputs']];job=a['job']
                if s['job']!=job or not load(r['consumer_closure']['path'])['full_event_consumer_drained']:
                    raise ValueError('Saved prediction is not closed or joined')
                pub=read_artifact(r['publication']);proj=read_artifact(r['projection'])
                pred=convert(pub,proj,read_component_events(s),job,pub['contract']['diarization'])
                before=time.monotonic();response=c.score(truths[job['job_id']],pred,timeout_seconds=30)
                if response['score']!=r['score']:raise ValueError('Process scorer changed an existing metric')
                checks.append(dict(expected=b,input_sha256=response['input_sha256'],score_sha256=fingerprint(response['score']),
                    exact_score_equal=True,worker=response['owner'],sequence=response['sequence'],seconds=time.monotonic()-before))
                if (i+1)%8==0:print(json.dumps(dict(completed=i+1,total=51)),flush=True)
            closure=c.close()
            for b in code:verify(b)
            freeze(args.output/'RESULT.json',dict(status='PASS_51_OWNED_PROCESS_SCORING_CHECKS',utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(args.output/'ADMISSION.json'),checks=checks,worker=hello,closure=closure,models_loaded=0,
                exact_metric_parity_cases=len(checks),integrated_N4_cells=0,scope='Saved development evidence only, no production bank'))
            print(json.dumps(dict(result=bind(args.output/'RESULT.json'))))
        except BaseException as exc:
            closure=c.close();freeze(args.output/'FAILED.json',dict(status='FAILED_PRESERVED',error_type=type(exc).__name__,
                completed=len(checks),checks=checks,closure=closure));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args())
