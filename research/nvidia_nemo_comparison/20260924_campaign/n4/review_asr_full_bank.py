"""Review terminal full-bank ASR components. See README_ASR_FULL_BANK.md."""
import argparse
from collections import Counter
from datetime import datetime,timezone
import json
import os
from pathlib import Path
from common import audio_only,bind,freeze,fingerprint,load,verify
from asr_full_bank import component_key,verify_admission
from review_asr_components import scan_events


def review(root,output):
    import psutil
    if output.exists():raise ValueError('Preserve previous review; choose fresh output')
    final_binding=bind(root/'RESULT.json');final=load(final_binding['path'])
    if final['status']!='FULL_BANK_COLLECTED_REQUIRES_REVIEW' or final['completed']!=1920 or final['total']!=1920:
        raise ValueError('Complete 1920-cell full bank required before review')
    try:
        if psutil.Process(final['owner']['pid']).create_time()==final['owner']['create_time']:
            raise ValueError('Exact numerical coordinator is still active')
    except psutil.NoSuchProcess:pass
    contract=verify_admission(root/'ADMISSION.json');admission=bind(root/'ADMISSION.json')
    if (final['admission']!=admission or final.get('child') is not None or final['integrated_N4_cells']!=0
            or contract['total']!=1920 or len(contract['jobs'])!=480 or contract['variants']!=['A0','A1','A2','A3']
            or len(final['variants'])!=4):raise ValueError('Full-bank admission/census disagreement')
    cells=[];bindings=[];totals=Counter();per_variant_counts=Counter()
    for variant,binding in zip(contract['variants'],final['variants']):
        verify(binding)
        if Path(binding['path']).resolve()!=(root/variant/'RESULT.json').resolve():raise ValueError('Wrong variant result path')
        index=load(binding['path']);progress=load(root/variant/'RESULT_INDEX.json')
        if (index['status']!='COMPLETE' or index['variant']!=variant or index['completed']!=480 or index['total']!=480
                or index['cpu_affinity']!=[4] or set(index['cells'])!={j['job_id'] for j in contract['jobs']}
                or progress['cells']!=index['cells'] or progress['completed']!=480 or progress['total']!=480):
            raise ValueError('Variant index is incomplete or changed')
        bindings.extend([binding,bind(root/variant/'RESULT_INDEX.json')])
        for job in contract['jobs']:
            audio_only(job);result_binding=index['cells'][job['job_id']];verify(result_binding)
            cell=load(result_binding['path']);profile=contract['profiles'][job['tap']]
            if (Path(result_binding['path']).resolve()!=(root/variant/job['job_id']/'RESULT.json').resolve()
                    or cell['schema']!='n4-asr-component-cell-v1' or cell['status']!='COMPLETE'
                    or cell['job']!=job or cell['variant']!=variant or cell['admission_sha256']!=admission['sha256']
                    or cell['profile_sha256']!=fingerprint(profile) or cell['cache_key']!=component_key(contract,job,variant,profile)
                    or cell['actual_neural_inference'] is not True or cell['cpu_affinity']!=[4] or cell['integrated_N4_cells']!=0):
                raise ValueError('Cell contract/cache differs')
            if Path(cell['events']['path']).resolve()!=(root/variant/job['job_id']/'ASR_EVENTS.jsonl.gz').resolve():
                raise ValueError('Wrong cell event path')
            if bind(job['audio_path'])['sha256']!=job['audio_sha256']:raise ValueError('Audio bytes changed')
            scan=scan_events(cell,round(profile['asr']['journal_read_ms']*16))
            cells.append(dict(variant=variant,result=result_binding,scan=scan));bindings.append(result_binding)
            per_variant_counts[variant]+=1
            for key in ('dispatches','source_samples','raw_observations','final_utterances','raw_final_words','expanded_bytes'):totals[key]+=scan[key]
    for binding in [final_binding,admission,*bindings]:verify(binding)
    receipt=dict(schema='n4-asr-full-bank-review-v1',status='PASS_ASR_FULL_BANK_COMPONENTS_ONLY',utc=datetime.now(timezone.utc).isoformat(),
        component_cells=1920,per_variant=480,component_contract_sha256=fingerprint(contract['component_contract']),
        admission=admission,final_result=final_binding,cells=cells,integrated_N4_cells=0,
        full_bank_component_coverage=True,Controller_or_widget_parity_qualified=False,live_latency_qualified=False,
        notes='Native application ASR-loop evidence only. Actual text remains private; formatting quality needs separate metrics.',
        code=[bind(Path(__file__).with_name(n)) for n in ('review_asr_full_bank.py','test_review_asr_full_bank.py','README_ASR_FULL_BANK.md')])
    output.mkdir(parents=True,exist_ok=False);freeze(output/'REVIEW.json',receipt)
    redacted={k:v for k,v in receipt.items() if k!='cells'}
    redacted.update(totals=dict(totals),per_variant_counts=dict(per_variant_counts),private_review=bind(output/'REVIEW.json'))
    freeze(output/'REDACTED_REVIEW.json',redacted)
    return redacted


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('run','output'):p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args()
    import psutil
    process=psutil.Process();process.cpu_affinity([14])
    if os.name=='nt':process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    print(json.dumps(review(args.run,args.output),indent=2))
