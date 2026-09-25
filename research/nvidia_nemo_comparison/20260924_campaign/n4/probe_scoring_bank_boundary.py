"""Actual V2 method-bank/scorer boundary, no inference. README_SCORING_BANK_BOUNDARY.md."""
import argparse
from copy import deepcopy
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import time
from common import bind,fingerprint,freeze,load,verify
from metric_process import identity,pin
from scoring_bank import prediction,admit
from integrated_scoring_adapter import convert,read_artifact,read_component_events
from probe_integrated_scoring import guard,private_bytes


def run(args):
    p=pin();here=Path(__file__).resolve().parent;started=time.monotonic()
    public=load(here/'APPLICATION_PUBLICATION_CHECK_V1.json');verify(public['private_receipt'])
    previous=load(public['private_receipt']['path']);source_binding=public['source_receipt'];verify(source_binding)
    source=load(source_binding['path']);root=Path(source['prototype']);local=Path(source_binding['path']).parents[2]
    for rel,b in source['files'].items():verify(dict(path=str((root/rel).resolve()),**b))
    sys.path[:0]=[str(root),str(root/'vendor')]
    from integrated_bank import predict_cell
    from mode_galleries import backend_contract
    gallery=public['gallery_preparation'];verify(gallery);catalog_binding=load(gallery['path'])['catalog'];verify(catalog_binding)
    catalog=load(catalog_binding['path']);wiring=load(here/'ACCEPTED_SOURCE_CATALOG_CHECK.json')
    context=dict(gallery_preparation=gallery,runtimes={Path(b['path']).name:b for b in wiring['inputs']
        if Path(b['path']).name in ('n2_runtime.json','n3_runtime.json')})
    for b in context['runtimes'].values():verify(b)
    empty_public=load(here/'EMPTY_CONTROLLER_CHECK_V1.json');verify(empty_public['private_receipt'])
    empty=load(empty_public['private_receipt']['path'])
    higher=next(r['key'] for r in catalog['backends'] if r['implemented'] and
        tuple(backend_contract(catalog,r['key'],'open_with_names')[k] for k in ('variant','diarization','encoder'))==('A3','D1','E1'))
    entries=[next(r for r in previous['checks'] if r['backend']==backend and r['mode']=='open_with_names' and r['tap']=='O0')
        for backend in ('baseline',higher)]
    entries.append(dict(empty['checks'][0],backend='baseline',consumer_closure=empty['checks'][0]['closure']))
    policy=load(local/'supervision/campaign.json')
    if args.output.exists() or not args.output.resolve().is_relative_to((local/'n4').resolve()):raise ValueError('Fresh private N4 output required')
    guard(args.output,policy,started);size=private_bytes(local)
    if size+6*1024**3+256*1024**2>min(50,policy['resource_policy']['new_payload_allowance_gib'])*1024**3:
        raise ValueError('Shared allowance unavailable')
    qualified=load(here/'INTEGRATED_BANK_IMPLEMENTATION_V1.json')
    for b in qualified['code']:verify(b)
    code=qualified['code']+[bind(here/n) for n in ('scoring_bank.py','integrated_scoring_adapter.py',
        'probe_scoring_bank_boundary.py','README_SCORING_BANK_BOUNDARY.md')]
    args.output.mkdir(parents=True,exist_ok=False)
    freeze(args.output/'ADMISSION.json',dict(owner=identity(p),code=code,source=source_binding,cases=3,
        parents=[public['private_receipt'],empty_public['private_receipt']],private_bytes_at_start=size,models_loaded=0))
    checks=[]
    try:
        for i,entry in enumerate(entries):
            guard(args.output,policy,started);parents=[]
            for b in entry['inputs']:
                verify(b);c=load(b['path']);parents.append(dict(result=b,cache_key=c['cache_key'],events=c['events']))
            a,s=[load(b['path']) for b in entry['inputs']];job=a['job']
            contract=backend_contract(catalog,entry['backend'],entry['mode'])
            row=dict(cell_id=f'development-scoring-boundary-{i}',job_id=job['job_id'],contract=contract,parents=parents,
                cache_key=fingerprint(parents),D0_E1_association_qualification='FROZEN_NOMINAL')
            cell_dir=args.output/f'{i:02d}';cell=predict_cell(row,job,context,cell_dir)
            actual=prediction(cell,row,job)
            expected=convert(read_artifact(entry['publication']),read_artifact(entry['projection']),
                read_component_events(s),job,contract['diarization'])
            if actual!=expected:raise ValueError('V2 bank boundary changed the qualified prediction')
            changed=deepcopy(cell);changed['raw_observations']+=1
            try:prediction(changed,row,job)
            except ValueError:pass
            else:raise ValueError('Changed method closure count was accepted')
            freeze(cell_dir/'RESULT.json',cell)
            checks.append(dict(result=bind(cell_dir/'RESULT.json'),actual_prediction_sha256=fingerprint(actual),
                exact_conversion_equal=True,changed_count_rejected=True))
        pending=local/'n4/integrated-main-v1'
        if pending.exists():raise ValueError('Unexpected production bank; inspect before admission test')
        try:admit(pending)
        except FileNotFoundError:pass
        else:raise ValueError('Missing production bank admitted')
        for b in code:verify(b)
        freeze(args.output/'RESULT.json',dict(status='PASS_3_ACTUAL_V2_BANK_SCORING_BOUNDARIES',utc=datetime.now(timezone.utc).isoformat(),
            admission=bind(args.output/'ADMISSION.json'),checks=checks,missing_production_bank_rejected=True,
            production_bank_admitted=False,models_loaded=0,integrated_N4_cells=0))
        print(json.dumps(dict(result=bind(args.output/'RESULT.json'))))
    except BaseException as exc:
        freeze(args.output/'FAILED.json',dict(status='FAILED_PRESERVED',error_type=type(exc).__name__,checks=checks));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args())
