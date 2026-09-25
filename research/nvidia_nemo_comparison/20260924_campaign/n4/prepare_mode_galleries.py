"""Prepare fixed N2 galleries for N4 modes. See README_MODE_GALLERIES.md."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
from unittest.mock import patch

for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'): os.environ[_key]='1'
os.environ['CUDA_VISIBLE_DEVICES']=''

from common import bind, freeze, load, verify
from mode_galleries import (CONDITIONS, verified_primary, materialize_baseline, backend_contract,
    load_prepared_gallery, configure_actual_mode)


def check_routes(preparation_binding):
    """Exercise actual begin() on all catalog/mode/tap combinations, no models."""
    from app.pipeline import effective_profile
    from edge_speech_pipeline.research_s6d import S6DSettings, build_s6d_scheduler
    from edge_speech_pipeline.research_s7_policy import ObservedClock
    from component_s7_replay import ReplayClock
    prepared=load(preparation_binding['path']); catalog=load(prepared['catalog']['path']); checks=[]
    for backend in catalog['backends']:
        if not backend['implemented']: continue
        for mode in CONDITIONS:
            contract=backend_contract(catalog,backend['key'],mode)
            for tap in ('O0','O1'):
                gallery,condition=load_prepared_gallery(preparation_binding,contract)
                profile=effective_profile('balanced',mode,tap)
                clock=ReplayClock(); observed=ObservedClock(clock=clock); observed.set_origin(0.)
                dispatcher=build_s6d_scheduler(profile,gallery,None,lambda r:None,S6DSettings(
                    text_delivery=True,boundary_repair=True,max_display_rows=512),observed_clock=observed)
                try:
                    harness=configure_actual_mode(dispatcher,observed,profile,gallery,contract)
                    # Actual annotation behavior is an independently recorded
                    # output; it never mutates the caption state in this harness.
                    raw=dict(text='protocol only',source_start_sec=0.,source_end_sec=1.,voice_available=False,
                        naming_state='unknown',known_profile_id=None,segments=[])
                    annotated=harness.prototype_identity.annotate_caption(raw) if harness.prototype_identity else raw
                    choice=annotated.get('closed_display_assignment')
                    checks.append(dict(contract=contract,tap=tap,available_profiles=condition['available_size'],
                        intended_profiles=condition['intended_size'],unavailable_profiles=condition['unavailable_count'],
                        missing_voice_closed_fallback=bool(choice),
                        fallback_verified=choice.get('voice_identity_verified',choice.get('verified')) if choice else None,
                        start_event_types=[r['event_type'] for r in harness.start_events]))
                finally: dispatcher.worker.close(timeout=5.)
    if len(checks)!=160: raise ValueError('Expected 16 catalog tuples x 5 modes x 2 taps')
    return checks


def main(args):
    import psutil
    proc=psutil.Process(); proc.cpu_affinity([14])
    if os.name=='nt': proc.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    if args.output.exists(): raise ValueError('Preserve previous preparation; use a fresh output')
    for drive,floor in [('C:\\',50),('G:\\',75)]:
        if shutil.disk_usage(drive).free < floor*1024**3+16*1024**2:
            raise ValueError('Insufficient free space for the 16-MiB gallery preparation reservation')
    prior=load(Path(__file__).with_name('COMPONENT_D1_REPLAY_CHECK_V1.json'))
    verify(prior['source_receipt']); source_receipt=load(prior['source_receipt']['path'])
    source=Path(source_receipt['prototype'])
    for rel,b in source_receipt['files'].items(): verify(dict(path=str((source/rel).resolve()),**b))
    sys.path[:0]=[str(source),str(source/'vendor')]
    catalog_path=source/'config/backends.json'; catalog=load(catalog_path)
    contracts=[backend_contract(catalog,r['key'],'anonymous_conversation') for r in catalog['backends'] if r['implemented']]
    if {(c['variant'],c['diarization'],c['encoder']) for c in contracts}!={(a,d,e) for a in ('A0','A1','A2','A3') for d in ('D0','D1') for e in ('E0','E1')}:
        raise ValueError('Require the exact 16-tuple admitted catalog')
    selections={}; inputs=[]
    for encoder in ('E0','E1'):
        receipt=bind(Path(__file__).resolve().parent.parent/'n2/evaluation'/f'{encoder}_COMPONENT_RECEIPT.json')
        original_result=load(receipt['path'])['private_result']
        index=bind(Path(original_result['path']).with_name('RUNTIME_GALLERY_INDEX_SAFE.json'))
        selections[encoder]=verified_primary(index,receipt,encoder); inputs.extend([receipt,index,original_result])
    for mode in set(CONDITIONS.values()):
        left,right=selections['E0'][mode],selections['E1'][mode]
        keys=('profile_id','name','unique_sec','provenance')
        if ([{k:p[k] for k in keys} for p in left['document']['profiles']]
                != [{k:p[k] for k in keys} for p in right['document']['profiles']]
                or {k:v for k,v in left['condition'].items() if k!='gallery'} != {k:v for k,v in right['condition'].items() if k!='gallery'}):
            raise ValueError('Encoder rosters or actual E support differ')
    import onnxruntime
    with patch.object(onnxruntime,'InferenceSession',side_effect=AssertionError('No model inference in gallery preparation')):
        args.output.mkdir(parents=True,exist_ok=False)
        try:
            encoders={}
            for encoder,rows in selections.items():
                conditions={}
                for mode,row in rows.items():
                    converted=materialize_baseline(row,args.output/'baseline'/mode) if encoder=='E0' else None
                    conditions[mode]={k:row[k] for k in ('condition','namespace','source_gallery')}
                    conditions[mode]['baseline_manifest']=converted
                encoders[encoder]=dict(conditions=conditions)
            bundle=dict(schema='n4-fixed-mode-galleries-v1',status='PREPARED_VERIFIED_RESEARCH_GALLERIES_ONLY',
                source_receipt=prior['source_receipt'],catalog=bind(catalog_path),inputs=inputs,encoders=encoders,
                processed_query_calibration='UNQUALIFIED; N2NameMap retains reject-all; baseline original nominal behavior preserved',
                selected_missing_references='retained in denominators; only existing available references enter the fixed gallery',
                model_inference=False,training=False,adaptation=False,human_enrollment=False,integrated_N4_cells=0)
            freeze(args.output/'GALLERIES.json',bundle)
            checks=check_routes(bind(args.output/'GALLERIES.json'))
            total=sum(p.stat().st_size for p in args.output.rglob('*') if p.is_file())
            if total+1024**2>16*1024**2: raise ValueError('Gallery allocation exceeded')
            receipt=dict(status='PASS_FIXED_GALLERIES_AND_ACTUAL_MODE_BEGIN_METHODS_ONLY',
                utc=datetime.now(timezone.utc).isoformat(),preparation=bind(args.output/'GALLERIES.json'),
                source_receipt=prior['source_receipt'],code=[bind(Path(__file__).with_name(n)) for n in (
                    'mode_galleries.py','prepare_mode_galleries.py','test_mode_galleries.py','README_MODE_GALLERIES.md',
                    'component_s7_replay.py','common.py')],checks=checks,checks_count=len(checks),
                resolver_counts=dict(Counter(r['contract']['resolver'] for r in checks)),
                gallery_payload_bytes=total,models_loaded=0,integrated_N4_cells=0,observed_Controller_parity=False,
                scope='Actual application begin() resolver/tracker/annotator routing at scheduler seam; no audio query, full Controller, visible caption, GUI or accuracy qualification')
            freeze(args.output/'RESULT.json',receipt)
            print(json.dumps(dict(status=receipt['status'],checks=len(checks),receipt=bind(args.output/'RESULT.json')),indent=2))
        except BaseException as exc:
            freeze(args.output/'FAILED.json',dict(status='FAILED_PRESERVED',error=repr(exc)))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',required=True,type=Path)
    main(parser.parse_args())
