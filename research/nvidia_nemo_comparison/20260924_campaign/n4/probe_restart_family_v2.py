"""Bounded restart lineage compatibility. README_RESTART_FAMILY_V2.md."""
import argparse
from datetime import datetime,timezone
import io
from pathlib import Path
import sys
import time
import unittest

from common import bind,freeze,load,verify
from metric_process import identity,pin
from probe_scoring_history_v3 import active_bank
from review_scoring_bank_v3 import guard,shared_allowance
from review_scoring_bank import require
from scoring_bank_v3 import writer_lock
from paced_panel_plan_v4 import application_qualification
from probe_restart_plan import actual_anchors
import restart_family_v2 as family
import restart_application_runner_v2 as runner
import test_paced_panel_plan_v3 as panel_fixture
import test_restart_plan_v2 as plan_tests
import test_restart_runner_v2 as runner_tests
import test_restart_run_review_v2 as stopped_tests
import test_restart_content_run_v2 as content_tests
import test_restart_family_v2 as family_tests


def suite(cls,output):
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
    path=output/(cls.__name__+'.txt');path.write_text(stream.getvalue(),encoding='utf-8')
    require(result.wasSuccessful() and not result.skipped,'Restart family check failed: '+cls.__name__)
    return dict(suite=cls.__name__,tests=result.testsRun,log=bind(path))


def run(output):
    process=pin();started=time.monotonic();local=family.LOCAL
    require(not output.exists() and output.resolve().is_relative_to(local/'n4'),'Fresh private restart family probe required')
    with writer_lock(local/'n4/metric-scoring.owner.lock'):
        checkpoint=lambda:guard(output,local,started,1200)
        checkpoint();resources=shared_allowance(local);active=active_bank(local)
        freeze(output/'PROBE_OWNER.json',dict(owner=identity(process),utc=datetime.now(timezone.utc).isoformat()))
        snapshots=[];checks=[]
        for name in family.OWN:
            path=output/'source'/name;path.parent.mkdir(exist_ok=True);path.write_bytes((family.HERE/name).read_bytes())
            require(bind(path)['sha256']==bind(family.HERE/name)['sha256'],'Attempt source differs');snapshots.append(bind(path))
        try:
            code,child,exe,script=runner.qualified_manifests();ab,app,context=application_qualification()
            lifecycle,_=plan_tests.subject.lifecycle_qualification();anchors=actual_anchors()
            # Use saved asset metadata for the real input-schema gate. No weights
            # are loaded and this does not qualify production model availability.
            main=load(active['plan']['path']);asset_metadata=[];component_admissions=[]
            models_root=None;asset_map={}
            for kind in ('ASR','D1'):
                rb=main['context']['reviews'][kind];verify(rb)
                review=load(rb['path']);verify(review['admission']);a=load(review['admission']['path'])
                require(a['component_contract']['source_receipt']==main['context']['source_receipt'],'Asset metadata source differs')
                if models_root is None:models_root=a['models_root']
                require(models_root==a['models_root'],'Asset metadata root differs')
                component_admissions.extend([rb,review['admission']])
                for b in a['component_contract']['assets']:
                    require(b['path'] not in asset_map or asset_map[b['path']]==b,'Asset metadata conflict')
                    asset_map[b['path']]=b
            asset_metadata=list(asset_map.values());require(bool(asset_metadata),'Saved asset metadata missing')
            freeze(output/'ADMISSION.json',dict(owner=identity(process),code=code,child_code=child,executable=exe,child_script=script,
                source_snapshots=snapshots,resources=resources,bank_start=active,application_qualification=ab,
                application_context=app['application_context'],source_receipt=context['source_receipt'],actual_anchors=anchors,
                lifecycle_qualification=lifecycle,maximum_seconds=1200,maximum_output_bytes=8*1024**2,
                asset_metadata_parent_receipts=component_admissions,asset_metadata=asset_metadata,
                model_asset_contents_revalidated=False,
                actual_application_or_model_started=False,
                fixture_scope='Pure synthetic V4 selected plans; mocked coordinator/child/slot/lifecycle; real native/viewport/roster readers over synthetic content; stopped owner/plan and qualification admission mocked in stopped-run fixtures'))
            panel_fixture.CONTEXT.update(source=context,source_binding=app['application_context'],app_binding=ab)
            plan_tests.CONTEXT.update(qualification=lifecycle,actual_jobs=anchors['jobs'],assets=asset_metadata,models_root=models_root)
            for module,name in ((plan_tests,'plans'),(runner_tests,'runner'),(stopped_tests,'stopped')):
                module.OUTPUT=output/'tests'/name;module.OUTPUT.mkdir(parents=True)
            # This fixture is never a production qualification and cannot pass family.qualification.
            freeze(output/'QUALIFICATION_FIXTURE.json',dict(synthetic=True,production_qualification=False))
            stopped_tests.CONTEXT['qualification_fixture']=bind(output/'QUALIFICATION_FIXTURE.json')
            content_tests.CONTEXT.update(context,output=output/'tests/content');content_tests.CONTEXT['output'].mkdir()
            family_tests.CONTEXT.update(output=output/'tests/family');family_tests.CONTEXT['output'].mkdir()
            for cls in (plan_tests.RestartPlanTests,runner_tests.RestartRunnerTests,stopped_tests.RestartPopulationTests,
                        content_tests.ContentCellTests,content_tests.ContentPopulationTests,family_tests.FamilyTests):
                checkpoint();checks.append(suite(cls,output))
            for b in code+child+snapshots+[exe,script,ab,app['application_context'],active['plan']]:verify(b)
            require('torch' not in sys.modules,'Model runtime imported by development probe')
            after=active_bank(local);require(after['plan']==active['plan'],'Main bank plan changed')
            checkpoint();end=shared_allowance(local)
            freeze(output/'RESULT.json',dict(status='PASS_V2_RESTART_FAMILY_CHECKS_ONLY',utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'),checks=checks,tests_passed=sum(r['tests'] for r in checks),
                source_snapshots=snapshots,code_records=len(code),child_code_records=len(child),bank_end=after,resources_end=end,
                route_payloads=bind(family_tests.CONTEXT['output']/'ALL_ROUTE_PAYLOAD_COUNTS.json'),
                child_and_payload_unchanged=True,collection_and_cleanup_control_flow_unchanged=True,
                actual_native_roster_viewport_readers=True,synthetic_ownership_clocks_geometry=True,
                complete_lifecycle_leaf_mocked_in_content_tests=True,
                plan_and_qualification_admission_mocked_in_stopped_run_tests=True,
                actual_application_or_model_started=False,actual_production_restart_run_reviewed=False,
                positive_production_plan_gate_executed=False,source_to_widget_latency_qualified=False,
                actual_restart_qualified=False,integrated_N4_cells=0,N4_accepted=False,N5_complete=False))
            print('PASS: restart family compatibility; no application or model launch',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_RESTART_FAMILY_V2_PROBE_PRESERVED',owner=identity(process),
                error_type=type(exc).__name__,checks_completed=checks,source_snapshots=snapshots,
                admission=bind(output/'ADMISSION.json') if (output/'ADMISSION.json').exists() else None))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
