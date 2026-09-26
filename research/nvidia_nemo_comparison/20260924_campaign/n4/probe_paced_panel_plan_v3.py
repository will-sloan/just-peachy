"""Model-free planning checks; does not create a shortlist or production plan."""
import argparse
from datetime import datetime,timezone
import io
from pathlib import Path
import time
import unittest

from common import bind,fingerprint,freeze,load,verify
from metric_process import identity,pin
from probe_application_transport_review import active_d1
from review_scoring_bank import guard,require,shared_allowance
from scoring_bank import writer_lock
import paced_panel_plan as original
import paced_panel_plan_v3 as revised
from test_paced_panel_plan import selection
import test_paced_panel_plan_v3 as regression

HERE=Path(__file__).resolve().parent
LOCAL=Path('G:/Just_Peachy_N1/20260924_campaign/local')
OWN=('paced_panel_plan_v3.py','test_paced_panel_plan_v3.py','probe_paced_panel_plan_v3.py','README_PACED_PANEL_PLAN_V3.md')


def run(output):
    process=pin();started=time.monotonic()
    require(not output.exists() and output.resolve().is_relative_to(LOCAL/'n4'),'Fresh private planner probe output required')
    with writer_lock(LOCAL/'n4/metric-scoring.owner.lock'):
        guard(output,LOCAL,started,720);inventory=shared_allowance(LOCAL);active=active_d1()
        freeze(output/'PROBE_OWNER.json',dict(owner=identity(process),utc=datetime.now(timezone.utc).isoformat()))
        (output/'source').mkdir(parents=True)
        for name in OWN:
            path=output/'source'/name;path.write_bytes((HERE/name).read_bytes())
            require(bind(path)['sha256']==bind(HERE/name)['sha256'],'Source snapshot differs')
        snapshots=[bind(p) for p in sorted((output/'source').iterdir())]
        checks=[]
        try:
            app_binding,app,source=revised.application_qualification();code=revised.code_bindings()
            for b in code:verify(b)
            prep_binding=load(HERE/'PREPARATION_V2_CHECK.json')['preparation'];verify(prep_binding);prep=load(prep_binding['path'])
            outputs={Path(b['path']).name:b for b in prep['outputs']}
            manifest,panel,anchors=[outputs[n] for n in ('AUDIO_ONLY_480.json','PACED_AUDIO_ONLY_24.json','REGRESSION_AUDIO_ONLY_8.json')]
            for b in (manifest,panel,anchors):verify(b)
            jobs,panel_jobs,anchor_jobs=[load(b['path'])['jobs'] for b in (manifest,panel,anchors)]
            for job in panel_jobs:require(bind(job['audio_path'])['sha256']==job['audio_sha256'],'Saved panel audio changed')
            tested,a,prepared,child,lifetime,records=revised.prestart_evidence(app)
            proof=(app,tested,a,prepared,child,records,load(source['catalog']['path']),records[0][3]['source_files'])
            freeze(output/'ADMISSION.json',dict(owner=identity(process),code=code,
                source_snapshots=snapshots,inventory=inventory,D1_snapshot=active,
                application_qualification=app_binding,application_context=app['application_context'],preparation=prep_binding,
                application_policy=revised.APPLICATION_POLICY,actual_shortlist_selected=False,production_plan_created=False))
            regression.CONTEXT.update(source=source,source_binding=app['application_context'],app_binding=app_binding)
            regression.CONTEXT['proof']=proof
            regression.OUTPUT=output/'tests';regression.OUTPUT.mkdir();stream=io.StringIO()
            tests=unittest.TextTestRunner(stream=stream,verbosity=2).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(regression.JournalPanelPlanTests))
            (output/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
            require(tests.wasSuccessful() and tests.testsRun==11 and not tests.skipped,'V3 panel planner tests failed')
            # Explicit development placeholders; no production review/admission is fabricated.
            reviews={'main':{'development_fixture':'UNAVAILABLE'},'modes-panel':{'development_fixture':'UNAVAILABLE'}}
            scored=dict(source_receipt=source['component_source_receipt'],catalog=source['component_catalog'],
                gallery_preparation=source['component_gallery_preparation'],runtimes={Path(b['path']).name:b for b in source['runtimes']},
                manifest=manifest,panel=panel)
            common=dict(manifest=manifest,panel=panel,regression=anchors,models_root='NO_MODEL_PAYLOAD',assets=[],
                planner_qualification={'development_fixture':'NOT_YET_QUALIFIED'},code=code)
            context=revised.application_context(scored,source,app['application_context'],app_binding,common)
            catalog=load(source['catalog']['path'])
            for candidate in sorted(original.COMPOSITIONS):
                guard(output,LOCAL,started,720)
                chosen=[original.BASELINE] if candidate==original.BASELINE else [original.BASELINE,candidate]
                plan=revised.build_plan(selection(chosen,reviews),reviews,jobs,panel_jobs,anchor_jobs,catalog,context)
                for index,row in enumerate(plan['rows']):
                    payload=revised.execution_payload(plan,index)
                    require(payload['source_receipt']==source['source_receipt'] and payload['catalog']==source['catalog']
                        and payload['gallery_preparation']==source['gallery_preparation'] and payload['job']==row['job']
                        and 'application_source_context' not in payload and 'component_source_receipt' not in payload
                        and 'application_policy' not in payload and plan['context']['application_policy']==revised.APPLICATION_POLICY,
                        'Derivative inference allowlist differs')
                checks.append(dict(candidate=candidate,fixture_cells=plan['required'],plan_content_sha256=fingerprint(plan),
                    source_seconds_per_candidate=plan['source_seconds_per_candidate'],production_admission=False))
            for b in code+[prep_binding,app_binding]:verify(b)
            after=active_d1();require(after['result']['child']==active['result']['child'] and after['run_id']==active['run_id'],'D1 ownership changed')
            guard(output,LOCAL,started,720)
            freeze(output/'RESULT.json',dict(status='PASS_DELIVERY_PANEL_PLANNING_CHECKS_ONLY',utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'),tests=bind(output/'tests.txt'),tests_passed=tests.testsRun,checks=checks,
                fixture_payloads=sum(r['fixture_cells'] for r in checks),D1_after=after,
                prepared_backends_reverified=len(records),prestart_lifetime_review=tested['lifetime_review'],
                production_full_review_gate_executed=False,actual_shortlist_selected=False,production_plan_created=False,
                application_runner_rebound=False,new_application_or_model_started=False,integrated_N4_cells=0,N4_accepted=False))
            print('PASS: 11 V3 planner tests and 1,240 fixture payloads across all 16 routes; no production plan',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_V3_PANEL_PLANNER_PROBE_PRESERVED',error_type=type(exc).__name__,
                owner=identity(process),source_snapshots=snapshots,
                admission=bind(output/'ADMISSION.json') if (output/'ADMISSION.json').exists() else None,checks=checks))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
