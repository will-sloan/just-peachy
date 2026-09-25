"""Aggregate reviewed ASR component timing/cell-end RSS. README_ASR_COMPONENT_REPORT.md."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import math
from pathlib import Path
import statistics
import time
from common import bind, freeze, load, verify
from metric_process import exact_process, identity, pin
from review_scoring_bank import guard, require, shared_allowance
from scoring_bank import writer_lock


def summarize(review_binding):
    verify(review_binding);review=load(review_binding['path'])
    require(review['status']=='PASS_ASR_FULL_BANK_COMPONENTS_ONLY' and review['component_cells']==1920
        and review['per_variant']==480 and len(review['cells'])==1920 and review['integrated_N4_cells']==0,'Full passed component review required')
    for b in review['code']+[review['admission'],review['final_result']]:verify(b)
    terminal=load(review['final_result']['path'])
    require(terminal['status']=='FULL_BANK_COLLECTED_REQUIRES_REVIEW' and terminal['completed']==terminal['total']==1920
        and terminal['child'] is None and exact_process(terminal['owner']) is None,'Terminal exact ASR owner must have exited')
    groups=defaultdict(list)
    for row in review['cells']:
        verify(row['result']);cell=load(row['result']['path'])
        require(cell['variant']==row['variant'] and cell['status']=='COMPLETE' and cell['actual_neural_inference'] is True
            and cell['cpu_affinity']==[4] and cell['integrated_N4_cells']==0,'Reviewed cell contract differs')
        require(type(cell['elapsed_seconds']) in (int,float) and math.isfinite(cell['elapsed_seconds']) and cell['elapsed_seconds']>0
            and type(cell['process_rss_bytes']) is int and cell['process_rss_bytes']>0,'Invalid component measurement')
        require(type(cell['job']['frames']) is int and cell['job']['frames']>0 and cell['job']['sample_rate_hz']==16000,'Invalid source duration')
        groups[row['variant']].append(cell)
    require(set(groups)=={'A0','A1','A2','A3'},'ASR variant census differs')
    rows=[];reference_jobs=None
    for variant,cells in sorted(groups.items()):
        jobs={c['job']['job_id']:c['job'] for c in cells}
        require(len(cells)==len(jobs)==480,'ASR scene/tap census differs')
        if reference_jobs is None:reference_jobs=jobs
        require(jobs==reference_jobs,'Variant audio populations differ')
        frames=sum(c['job']['frames'] for c in cells);elapsed=sum(c['elapsed_seconds'] for c in cells)
        loads=[c['model_load_seconds'] for c in cells if c['model_load_seconds'] is not None]
        require(len(loads)==1 and type(loads[0]) in (int,float) and math.isfinite(loads[0]) and loads[0]>=0,'First model-constructor observation differs')
        rows.append(dict(variant=variant,component_cells=480,source_frames=frames,source_seconds=frames/16000,
            sum_recorded_cell_elapsed_seconds=elapsed,median_recorded_cell_elapsed_seconds=statistics.median(c['elapsed_seconds'] for c in cells),
            maximum_recorded_cell_elapsed_seconds=max(c['elapsed_seconds'] for c in cells),
            recorded_compute_seconds_per_audio_second=elapsed/(frames/16000),first_model_constructor_seconds=loads[0],
            maximum_cell_end_sampled_process_rss_bytes=max(c['process_rss_bytes'] for c in cells)))
    verify(review_binding)
    return dict(status='SUMMARIZED_REVIEWED_ASR_COMPONENT_OBSERVATIONS_ONLY',review=review_binding,rows=rows,
        total_component_cells=1920,cpu_affinity=[4],model_library_threads=1,GPU_enabled=False,
        integrated_N4_cells=0,accuracy_qualified=False,source_paced_latency_qualified=False,
        controlled_whole_stack_resources_qualified=False,CM5_qualified=False,deployment_tier='UNKNOWN',
        limitations=['Accelerated stateful component inference; ratios are not source-paced end-to-end latency or full-application throughput.',
            'Only end-of-cell process RSS samples are summarized; they can miss peaks and include runtime/resident caches.',
            'RSS is not unique physical memory, USS, private commit, model file bytes or whole-stack memory.',
            'First model-constructor duration does not establish cold disk/cache behavior or complete GUI/gallery startup.',
            'No diarization/embedding/gallery/Controller/widget/OS reserve is included as a complete-stack measurement.',
            'No accuracy winner, deployment tier, physical 2-GB fit or live Pi performance is inferred.'])


def run(review_path,output):
    process=pin();started=time.monotonic();local=Path('G:/Just_Peachy_N1/20260924_campaign/local');here=Path(__file__).resolve().parent
    require(not output.exists() and output.resolve().is_relative_to(local/'n4'),'Fresh private report output required')
    with writer_lock(local/'n4/metric-scoring.owner.lock'):
        guard(output,local,started,720);inventory=shared_allowance(local)
        code=[bind(here/n) for n in ('summarize_asr_components.py','README_ASR_COMPONENT_REPORT.md','common.py','metric_process.py','review_scoring_bank.py','scoring_bank.py')]
        review_binding=bind(review_path)
        freeze(output/'ADMISSION.json',dict(owner=identity(process),review=review_binding,code=code,inventory=inventory))
        result=summarize(review_binding)
        for b in code:verify(b)
        guard(output,local,started,720)
        freeze(output/'REPORT.json',dict(result,admission=bind(output/'ADMISSION.json'),utc=datetime.now(timezone.utc).isoformat()))
        print('Summarized all 1920 reviewed ASR component cells; no whole-stack or target qualification',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.review,args.output)
