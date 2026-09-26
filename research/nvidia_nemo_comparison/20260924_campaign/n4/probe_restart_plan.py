"""Guarded model-free restart planning checks; see README_RESTART_PLAN.md."""
import argparse
from datetime import datetime,timezone
import io
from pathlib import Path
import time
import unittest
import wave

from common import bind,fingerprint,freeze,load,verify
from metric_process import identity,pin
from probe_application_transport_review import active_d1
from review_scoring_bank import guard,require,shared_allowance
from scoring_bank import writer_lock
import restart_application_plan as subject
import test_restart_plan as tests
import test_paced_panel_plan_v3 as fixtures

HERE=Path(__file__).resolve().parent
LOCAL=subject.LOCAL


def actual_anchors():
    preparation=load(HERE/'PREPARATION_V2_CHECK.json')['preparation']; verify(preparation)
    manifest=next(b for b in load(preparation['path'])['outputs'] if Path(b['path']).name=='AUDIO_ONLY_480.json')
    verify(manifest); population=load(manifest['path'])['jobs']; jobs=[]; waveforms=[]
    for jid in subject.JOBS:
        found=[j for j in population if j['job_id']==jid]; require(len(found)==1,'Actual restart anchor missing or repeated')
        job=found[0]; subject.stop_after_samples(job); waveform=bind(job['audio_path'])
        require(waveform['sha256']==job['audio_sha256'],'Actual saved anchor changed')
        with wave.open(waveform['path'],'rb') as source:
            require((source.getnchannels(),source.getsampwidth(),source.getframerate(),source.getnframes(),source.getcomptype())
                ==(1,2,16000,job['frames'],'NONE'),'Saved anchor header differs')
        jobs.append(job); waveforms.append(waveform)
    verify(manifest); return dict(preparation=preparation,manifest=manifest,jobs=jobs,waveforms=waveforms)


def run(output):
    process=pin(); started=time.monotonic()
    require(not output.exists() and output.resolve().is_relative_to(LOCAL/'n4'),'Fresh private restart plan probe required')
    with writer_lock(LOCAL/'n4/metric-scoring.owner.lock'):
        check=lambda:guard(output,LOCAL,started,720)
        check(); inventory=shared_allowance(LOCAL); active=active_d1()
        freeze(output/'PROBE_OWNER.json',dict(owner=identity(process),utc=datetime.now(timezone.utc).isoformat()))
        (output/'source').mkdir(); snapshots=[]
        for name in subject.OWN:
            target=output/'source'/name; target.write_bytes((HERE/name).read_bytes())
            require(bind(target)['sha256']==bind(HERE/name)['sha256'],'Restart source snapshot differs'); snapshots.append(bind(target))
        try:
            code=subject.code_bindings(); qb,_=subject.lifecycle_qualification()
            ab,app,source=subject.panels.application_qualification(); anchors=actual_anchors()
            freeze(output/'ADMISSION.json',dict(owner=identity(process),code=code,source_snapshots=snapshots,inventory=inventory,
                D1_snapshot=active,lifecycle_qualification=qb,application_qualification=ab,actual_anchors=anchors,
                actual_production_plan=False,actual_source_execution=False))
            for b in code: verify(b)
            fixtures.CONTEXT.update(source=source,source_binding=app['application_context'],app_binding=ab)
            tests.CONTEXT.update(qualification=qb,actual_jobs=anchors['jobs'])
            tests.OUTPUT=output/'tests'; tests.OUTPUT.mkdir(); stream=io.StringIO()
            outcome=unittest.TextTestRunner(stream=stream,verbosity=2).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(tests.RestartPlanTests))
            (output/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
            require(outcome.wasSuccessful() and outcome.testsRun==16 and not outcome.skipped,'Restart planner regression failed')
            routes=[]
            for candidate in sorted(subject.original.COMPOSITIONS):
                chosen=[subject.original.BASELINE] if candidate==subject.original.BASELINE else [subject.original.BASELINE,candidate]
                value=tests.plan(chosen)
                for index in range(value['required']):
                    payload=subject.execution_payload(value,index)
                    require(set(payload)==set(subject.panels.execution_payload(tests.panel(chosen),0))
                        and subject.stop_after_samples(payload['job'])==value['rows'][index]['stop_after_samples'], 'Runtime controls/firewall differ')
                routes.append(dict(candidate=candidate,fixture_pairs=value['required'],plan_content_sha256=fingerprint(value)))
            for b in code+snapshots+[qb,ab,anchors['manifest'],*anchors['waveforms']]: verify(b)
            after=active_d1(); require(after['result']['child']==active['result']['child'] and after['run_id']==active['run_id'],'D1 owner changed')
            check()
            freeze(output/'RESULT.json',dict(status='PASS_RESTART_PLANNING_DEVELOPMENT_CHECKS_ONLY',utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'),tests=bind(output/'tests.txt'),tests_passed=outcome.testsRun,
                routes=routes,fixture_pairs=sum(r['fixture_pairs'] for r in routes),D1_after=after,
                actual_saved_anchors_read_only=True,actual_production_plan=False,actual_shortlist_selected=False,
                actual_GUI_or_model_started=False,actual_source_execution=False,actual_restart_qualified=False,
                integrated_N4_cells=0,N4_accepted=False))
            print('PASS: 16 restart planner checks, 62 fixture pairs, two actual saved headers/hashes; no application run',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_RESTART_PLAN_PROBE_PRESERVED',error_type=type(exc).__name__,
                owner=identity(process),source_snapshots=snapshots,
                admission=bind(output/'ADMISSION.json') if (output/'ADMISSION.json').exists() else None)); raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
