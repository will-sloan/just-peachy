"""Saved-buffer wall observer review; README_TEST_S6C_WALL_PROGRESS_COMPONENT_REVIEW.md."""
import hashlib,json,math
from pathlib import Path
import s6c_wall_progress as observer

REPORT=Path(__file__).resolve().parents[1]/'reports/S6C/20260910T123540Z'
def binding(p,raw=None):
    p=Path(p).resolve();raw=p.read_bytes() if raw is None else raw
    return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def read(b):
    raw=Path(b['path']).read_bytes();assert binding(b['path'],raw)==b
    return json.loads(raw)

def main():
    rb=binding(REPORT/'wall_progress/OBSERVER_CHECKS_V1.json');assert rb['sha256']=='f186df4f1a5989c14aa37eb97806adbd5b1e0d823824cafdb1da471732b2327b'
    receipt=read(rb)
    for b in receipt['sources']:assert binding(b['path'])==b
    assert observer.checks()==receipt['tests'] and receipt['tests']['checks']==30
    observations=[read(b) for b in receipt['actual_observations']]
    assert len(observations)==2
    checks=0
    for obs in observations:
        assert obs['sources']==receipt['sources'];checks+=1
        raw=Path(obs['retained_source']['path']).read_bytes();assert binding(obs['retained_source']['path'],raw)==obs['retained_source'];checks+=1
        assert binding(obs['source']['path'],raw)==obs['source'];checks+=1
        saved=observer.parse(raw);last=obs['history'][-1]
        reconstructed=observer.point(saved,last['source_path'],last['pid'],last['creation_time'],last['observed_utc'],last['observer_monotonic_sec'],last['boot_time'],last['owner_state'])
        assert reconstructed==last and observer.estimate(obs['history'])==obs['estimate'];checks+=2
    assert observations[0]['history']==observations[1]['history'][:-1] and observations[1]['previous']==receipt['actual_observations'][0];checks+=1
    a,b=observations[1]['history'];assert a['counters']['new_native_jobs']==297 and b['counters']['new_native_jobs']==303;checks+=1
    wall=b['observer_monotonic_sec']-a['observer_monotonic_sec'];rate=6/wall;remaining=b['counters']['requested']-b['counters']['completed']
    result=observations[1]['estimate'];assert math.isclose(result['new_completions_per_observed_wall_sec'],rate,rel_tol=1e-12);checks+=1
    assert result['heuristic_remaining_wall_sec']==remaining/rate and result['heuristic_eta_range_sec']==[remaining/rate*.5,remaining/rate*2.];checks+=1
    assert a['owner_state']['alive'] is b['owner_state']['alive'] is True and a['pid']==b['pid']==15520;checks+=1
    audit_binding=binding(REPORT/'wall_progress/NATIVE_ETA_OVERHEAD_AUDIT_V1.json');assert audit_binding['sha256']=='176c8426eda39481f6761fd0bcf8d4bae4e440c49a443b9758bb68cebe323968'
    audit=read(audit_binding)
    for b in audit['frozen_sources']:assert binding(b['path'])==b
    data=dict(status='PASS_SAVED_METADATA_WALL_OBSERVER_REVIEW',original_checks=rb,original_pure_fixtures=30,independent_saved_buffer_checks=checks,
        saved_observations=receipt['actual_observations'],source_eta_audit=audit_binding,observed_delta_jobs=6,observed_interval_sec=wall,observed_rate_per_sec=rate,
        sources=receipt['sources']+[binding(__file__),binding(Path(__file__).with_name('README_TEST_S6C_WALL_PROGRESS_COMPONENT_REVIEW.md'))],
        findings=['Two saved observations reconstruct exactly from retained progress bytes and historical recorded clock/owner fields.',
            'Rate uses new-native counter difference over monotonic observer time; reused rows are excluded and active jobs remain in remaining work.',
            'Initial/flat/stale/unverified/reset/phase/path/grid guards retain null ETA or reject; original worker-cost ETA is separately preserved.',
            'Counter publication intervals and unmeasured closure are explicit; heuristic range is not a confidence interval or durable inference count.'],
        current_progress_reads=0,current_process_inspections=0,models=0,
        scope='Source/30 pure fixtures and two exact saved-buffer reconstructions only. Historical owner-inspection results are retained as recorded, not independently re-observed. This review does not authorize a monitoring loop or certify current progress/closure.')
    output=REPORT/'independent_review/WALL_PROGRESS_COMPONENT_REVIEW_V1.json'
    with output.open('xb') as f:f.write((json.dumps(data,indent=2,allow_nan=False)+'\n').encode())
    print(json.dumps(binding(output)))

if __name__=='__main__':main()
