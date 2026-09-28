"""Create an aggregate-only pre-Pi evidence receipt. See README_SUMMARY.md."""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent.parent/'n4'))
from common import bind,freeze,load,verify
from metric_process import pin,exact_process

RUNS={
    'a0-d1-e0-v2':'PASS_PREPI_ONE_FILE_WINDOWS_LIFECYCLE_ONLY',
    'a2-d1-e0-v1':'PASS_PREPI_ONE_FILE_WINDOWS_LIFECYCLE_ONLY',
    'a0-restart-v1':'PASS_PREPI_TWO_CYCLE_WINDOWS_RESTART_ONLY',
    'a2-restart-v1':'PASS_PREPI_TWO_CYCLE_WINDOWS_RESTART_ONLY',
    'a0-shadow-v1':'PASS_PREPI_ONE_FILE_WINDOWS_SHADOW_ONLY',
    'a2-shadow-v1':'PASS_PREPI_ONE_FILE_WINDOWS_SHADOW_ONLY',
    'a0-e0-runtime-v1':'PASS_PREPI_E0_RUNTIME_WINDOWS_SHADOW_ONLY',
    'a2-e0-runtime-v1':'PASS_PREPI_E0_RUNTIME_WINDOWS_SHADOW_ONLY',
}


def summarize(output):
    pin();base=HERE.parent.parents[4]/'local/n5/prepi-20260928'
    regressions=[]
    for name,count in [('shutdown-tests-v1/derivative-tests.txt',4),
                       ('shutdown-tests-v1/existing-lifecycle.txt',10),('e0-tests-v1/tests.txt',6)]:
        path=base/name;text=path.read_text(encoding='utf-8')
        if 'Ran '+str(count)+' tests' not in text or not text.strip().endswith('OK'):
            raise ValueError('Regression log is not a passing result: '+name)
        regressions.append(dict(log=bind(path),tests=count,status='PASS_MODEL_FREE_ONLY'))
    rows=[]
    for name,expected in RUNS.items():
        review_path=base/(name+'-REVIEW.json');review=load(review_path)
        if review['status']!=expected or not review['all_owners_exited']:
            raise ValueError('Missing independent qualification: '+name)
        for b in [review['admission'],review['terminal'],review['source_receipt']]:verify(b)
        admission=load(review['admission']['path'])
        for who in review['closed_owners']:
            if exact_process(who) is not None:raise RuntimeError('Owner reappeared: '+name)
        for phase in review['phases']:
            verify(phase['result']);verify(phase['lifetime'])
            if exact_process(load(phase['result']['path'])['owner']) is not None:
                raise RuntimeError('Application still active: '+name)
        summary=review['summary'];infer=load(review['phases'][0]['result']['path'])
        row=dict(name=name,status=expected,backend_key=review['backend_key'],review=bind(review_path),
                 source_receipt=review['source_receipt'],expected_samples=summary['expected_samples'],
                 source_seconds=summary['expected_samples']/16000,embedding_calls=summary['embedding_calls'],
                 model_cache=summary['model_cache'],activity_frames=summary['activity_frame_count'],
                 inference_session_elapsed_wall_seconds=infer['telemetry']['elapsed_wall_sec'],
                 scope=review['scope'],source_files_verified=review['source_files_verified'],
                 all_audio_retained=True,all_owners_exited=True)
        if 'shadow' in summary:
            shadow=summary['shadow']
            row['shadow']=dict(observer_wall_seconds=shadow['observer_wall_seconds'],
                exact_zero_fraction=shadow['proposed_methods']['G01']['below_threshold_samples']/shadow['samples'],
                actually_skipped_samples=0,methods={k:dict(proposed_skip_fraction=v['proposed_skip_fraction'],
                    proposed_skip_samples=v['proposed_skip_samples'],energy_duty_cycle=v['above_threshold_duty_cycle'])
                    for k,v in shadow['proposed_methods'].items()})
        rows.append(row)
    receipt=dict(schema='just-peachy.prepi-check-summary.v1',utc=datetime.now(timezone.utc).isoformat(),
        status='EIGHT_NARROW_WINDOWS_RUNS_INDEPENDENTLY_REVIEWED',window=bind(HERE/'WINDOW.json'),
        runs=rows,model_free_regression_logs=regressions,unique_source_files=1,source_is_saved_synthetic=True,
        N4_accepted=False,N5_complete=False,CM5_tested=False,independent_real_world_validation=False,
        applied_silence_gate_qualified=False,real_time_throughput_qualified=False,
        limitations=['Same saved source reused; run count is not independent scene coverage',
            'Elapsed session wall time includes pacing/drain; it is not isolated inference service time',
            'Zero/energy duty and proposed skips are conditional diagnostics, not speech accuracy or saved compute',
            'Original partial N4 panel, full ARM64 stack and native held-out/endurance gates remain open'],
        generator=bind(__file__))
    freeze(output,receipt)
    print(dict(status=receipt['status'],output=str(output),runs=len(rows)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();summarize(a.output)
