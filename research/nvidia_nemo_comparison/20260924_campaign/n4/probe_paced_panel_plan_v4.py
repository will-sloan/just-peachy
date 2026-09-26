"""Model-free V3-score planner qualification. README_PACED_PANEL_PLAN_V4.md."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import io
from pathlib import Path
import sys
import time
import unittest

from common import bind, fingerprint, freeze, load, verify
from metric_process import identity, pin
from probe_scoring_history_v3 import active_bank
from review_scoring_bank_v3 import guard, require, shared_allowance
from scoring_bank_v3 import writer_lock
import paced_panel_plan as original
import paced_panel_plan_v3 as previous
import paced_panel_plan_v4 as subject
import panel_scoring_admission_v3 as scores
import test_paced_panel_plan as base_tests
import test_paced_panel_plan_v3 as prior_tests
import test_paced_panel_plan_v4 as tests


def run(output):
    process=pin();started=time.monotonic();local=subject.LOCAL
    require(not output.exists() and output.resolve().is_relative_to(local/'n4'),'Fresh private planner probe output required')
    with writer_lock(local/'n4/metric-scoring.owner.lock'):
        check=lambda:guard(output,local,started,1200)
        check();resources=shared_allowance(local);active=active_bank(local)
        freeze(output/'PROBE_OWNER.json',dict(owner=identity(process),utc=datetime.now(timezone.utc).isoformat()))
        snapshots=[]
        for name in subject.OWN:
            path=output/'source'/name;path.parent.mkdir(exist_ok=True);path.write_bytes((subject.HERE/name).read_bytes())
            require(bind(path)['sha256']==bind(subject.HERE/name)['sha256'],'Source snapshot differs');snapshots.append(bind(path))
        try:
            code=subject.code_bindings();ab,app,source=subject.application_qualification();sb,sq=scores.qualification()
            for b in code:verify(b)
            prep_binding=load(subject.HERE/'PREPARATION_V2_CHECK.json')['preparation'];verify(prep_binding)
            prep=load(prep_binding['path']);outputs={Path(b['path']).name:b for b in prep['outputs']}
            manifest,panel,anchors=[outputs[n] for n in ('AUDIO_ONLY_480.json','PACED_AUDIO_ONLY_24.json','REGRESSION_AUDIO_ONLY_8.json')]
            for b in (manifest,panel,anchors):verify(b)
            jobs,panel_jobs,anchor_jobs=[load(b['path'])['jobs'] for b in (manifest,panel,anchors)]
            for job in panel_jobs:require(bind(job['audio_path'])['sha256']==job['audio_sha256'],'Saved panel audio changed')
            tested,a,prepared,child,lifetime,records=previous.prestart_evidence(app)
            proof=(app,tested,a,prepared,child,records,load(source['catalog']['path']),records[0][3]['source_files'])
            freeze(output/'ADMISSION.json',dict(owner=identity(process),code=code,source_snapshots=snapshots,
                resources=resources,bank_start=active,scoring_qualification=sb,application_qualification=ab,
                application_context=app['application_context'],preparation=prep_binding,
                maximum_seconds=1200,maximum_output_bytes=8*1024**2,actual_shortlist_selected=False,
                production_plan_created=False,fixture_scope='Pure full-count score-chain dictionaries plus real saved context and audio hash checks; no completed production scoring receipt exists yet'))
            prior_tests.CONTEXT.update(source=source,source_binding=app['application_context'],app_binding=ab,proof=proof)
            prior_tests.OUTPUT=output/'tests/prior';prior_tests.OUTPUT.mkdir(parents=True)
            tests.OUTPUT=output/'tests/v4';tests.OUTPUT.mkdir()
            suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls) for cls in (
                tests.ScoreAdmissionTests,tests.PanelV4Tests,prior_tests.JournalPanelPlanTests,base_tests.PacedPanelPlanTests))
            stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
            (output/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
            require(result.wasSuccessful() and result.testsRun==39 and not result.skipped,'V4 planner tests failed')
            # Recheck actual main reuse/context lineage, using an explicitly incomplete
            # modes *context fixture*. It cannot pass read_review or execute a plan.
            main=load(active['plan']['path']);mode_context=deepcopy(main['context']);mode_context.pop('reuse_review',None)
            mode_fixture=dict(scope='modes-panel',required=1536,context=mode_context,jobs=main['jobs'])
            common_context=scores.validate_review_pair(main,mode_fixture)
            require(common_context==mode_context,'Actual main context/reuse join differs')
            reviews={'main':{'development_fixture':'UNAVAILABLE'},'modes-panel':{'development_fixture':'UNAVAILABLE'}}
            scored=dict(source_receipt=source['component_source_receipt'],catalog=source['component_catalog'],
                gallery_preparation=source['component_gallery_preparation'],runtimes={Path(b['path']).name:b for b in source['runtimes']},
                manifest=manifest,panel=panel)
            common=dict(manifest=manifest,panel=panel,regression=anchors,models_root='NO_MODEL_PAYLOAD',assets=[],
                planner_qualification={'development_fixture':'NOT_YET_QUALIFIED'},code=code)
            context=subject.application_context(scored,source,app['application_context'],ab,common)
            catalog=load(source['catalog']['path']);checks=[]
            for candidate in sorted(original.COMPOSITIONS):
                check();chosen=[original.BASELINE] if candidate==original.BASELINE else [original.BASELINE,candidate]
                plan=subject.build_plan(base_tests.selection(chosen,reviews),reviews,jobs,panel_jobs,anchor_jobs,catalog,context)
                for index,row in enumerate(plan['rows']):
                    payload=subject.execution_payload(plan,index)
                    require(payload['source_receipt']==source['source_receipt'] and payload['catalog']==source['catalog']
                        and payload['gallery_preparation']==source['gallery_preparation'] and payload['job']==row['job']
                        and payload['source_execution_authorized'] is False and len(payload)==13
                        and not set(payload)&{'reviews','selection','scoring_review_policy','truth','reference','application_source_context'},
                        'V4 inference allowlist differs')
                checks.append(dict(candidate=candidate,fixture_cells=plan['required'],plan_content_sha256=fingerprint(plan),
                    source_seconds_per_candidate=plan['source_seconds_per_candidate'],production_admission=False))
            for b in code+snapshots+[prep_binding,ab,sb,active['plan']]:verify(b)
            require('torch' not in sys.modules,'Planner imported a model runtime')
            after=active_bank(local);require(after['plan']==active['plan'],'Active bank plan changed')
            check();resources_end=shared_allowance(local)
            freeze(output/'RESULT.json',dict(status='PASS_V3_SCORED_PANEL_PLANNING_CHECKS_ONLY',utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'),tests=bind(output/'tests.txt'),tests_passed=result.testsRun,
                source_snapshots=snapshots,checks=checks,fixture_payloads=sum(r['fixture_cells'] for r in checks),
                bank_end=after,resources_end=resources_end,prepared_backends_reverified=len(records),
                actual_main_reuse_context_verified=True,modes_context_is_fixture_only=True,
                production_full_review_gate_executed=False,actual_shortlist_selected=False,production_plan_created=False,
                downstream_runner_and_restart_rebound=False,actual_application_or_model_started=False,
                integrated_N4_cells=0,N4_accepted=False,N5_complete=False))
            print('PASS: 39 planner/review tests and 1,240 saved-panel fixture payloads; no model or application execution',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_V4_PANEL_PLANNER_PROBE_PRESERVED',owner=identity(process),
                error_type=type(exc).__name__,source_snapshots=snapshots,
                admission=bind(output/'ADMISSION.json') if (output/'ADMISSION.json').exists() else None))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
