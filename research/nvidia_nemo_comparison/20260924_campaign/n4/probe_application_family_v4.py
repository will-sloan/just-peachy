"""Bounded model-free runner/reviewer compatibility. README_APPLICATION_FAMILY_V4.md."""
import argparse
from datetime import datetime, timezone
import io
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from common import bind, freeze, load, verify
from metric_process import exact_process, identity, pin
from paced_panel_plan_v4 import application_qualification
from probe_scoring_history_v3 import active_bank
from review_scoring_bank_v3 import guard, require, shared_allowance
from scoring_bank_v3 import writer_lock
import application_family_v4 as family
from paced_application_runner_v4 import qualified_interpreter
import test_paced_child_admission_v2 as gate_tests
import test_paced_application_runner_v4 as runner_tests
import test_application_transport_review_v4 as transport_tests
import test_application_cell_review_v4 as cell_tests
import test_application_panel_review_v4 as panel_tests
import test_application_family_v4 as family_tests


def suite(cls,output):
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
    path=output/(cls.__module__+'.txt');path.write_text(stream.getvalue(),encoding='utf-8')
    require(result.wasSuccessful() and not result.skipped,'Application family check failed: '+cls.__module__)
    return dict(suite=cls.__module__,tests=result.testsRun,log=bind(path))


def run(output):
    process=pin();started=time.monotonic();local=family.LOCAL;sys.path.insert(0,str(family.HERE.parents[3]))
    require(not output.exists() and output.resolve().is_relative_to(local/'n4'),'Fresh private family probe output required')
    with writer_lock(local/'n4/metric-scoring.owner.lock'):
        checkpoint=lambda:guard(output,local,started,1200)
        checkpoint();resources=shared_allowance(local);active=active_bank(local)
        freeze(output/'PROBE_OWNER.json',dict(owner=identity(process),utc=datetime.now(timezone.utc).isoformat()))
        snapshots=[]
        for name in family.OWN:
            path=output/'source'/name;path.parent.mkdir(exist_ok=True);path.write_bytes((family.HERE/name).read_bytes())
            require(bind(path)['sha256']==bind(family.HERE/name)['sha256'],'Attempt source differs');snapshots.append(bind(path))
        checks=[]
        try:
            code=family.code_bindings();exe=qualified_interpreter();ab,app,source=application_qualification()
            prototype=Path(load(source['source_receipt']['path'])['prototype'])
            native=load(family.HERE/'PRIVATE_PROCESS_CHECK_V3.json');verify(native['private_receipt'])
            saved=load(native['private_receipt']['path'])['fixture_lifetimes']
            for b in saved:verify(b);require(exact_process(load(b['path'])['owner']) is None,'Saved fixture owner remains active')
            closure=load(family.HERE/'APPLICATION_CLOSURE_CHECK_V2.json');verify(closure['private_receipt'])
            prior=load(closure['private_receipt']['path']);verify(prior['admission']);old=load(prior['admission']['path'])
            require(exact_process(old['owner']) is None,'Historical closure helper remains active');case=old['cases'][0]
            for name in ('finalization','consumer','archive'):verify(case[name])
            freeze(output/'ADMISSION.json',dict(owner=identity(process),code=code,source_snapshots=snapshots,executable=exe,
                resources=resources,bank_start=active,application_qualification=ab,application_context=app['application_context'],
                source_receipt=source['source_receipt'],saved_native_lifetimes=saved,historical_closure_admission=prior['admission'],
                maximum_seconds=1200,maximum_output_bytes=8*1024**2,actual_application_or_model_started=False,
                fixture_scope='Mocked runner/child/slot lifecycle; real lease writer, RAM source and evidence readers with synthetic owner/clock/resource/viewport facts; seven historical native lifetimes'))
            fixtures=output/'temporary-fixtures';fixtures.mkdir()
            runner_root=output/'runner';runner_root.mkdir()
            runner_tests.CONTEXT.update(output=runner_root,prototype=prototype,checkpoint=checkpoint)
            runner_tests.delivery_tests.CONTEXT.update(output=runner_root,prototype=prototype,checkpoint=checkpoint)
            runner_tests.delivery_tests.source_tests.CONTEXT.update(output=runner_root,prototype=prototype,checkpoint=checkpoint)
            transport_tests.SAVED=saved;transport_tests.SOURCE=source['source_receipt'];transport_tests.OUTPUT=output/'transport';transport_tests.OUTPUT.mkdir()
            cell_tests.CONTEXT.update(output=output/'cell',case=case,source=source['source_receipt'],
                catalog=source['catalog'],galleries=source['gallery_preparation'],runtimes=source['runtimes'])
            cell_tests.CONTEXT['output'].mkdir()
            family_tests.CONTEXT.update(code=code,output=output/'family');family_tests.CONTEXT['output'].mkdir()
            with patch.object(tempfile,'tempdir',str(fixtures)):
                for cls in (gate_tests.ChildAdmissionTests,runner_tests.RunnerTests,transport_tests.TransportReviewTests,cell_tests.CellReviewTests):
                    checkpoint();checks.append(suite(cls,output))
                joined=bind(output/'cell/test_all_real_readers_compose_with_synthetic_facts/SYNTHETIC_COMPLETE_JOIN_REVIEW.json')
                panel_tests.CONTEXT.update(output=output/'panel',synthetic_join=joined);panel_tests.CONTEXT['output'].mkdir()
                for cls in (panel_tests.PanelReviewTests,family_tests.FamilyTests):
                    checkpoint();checks.append(suite(cls,output))
            require(sum(r['tests'] for r in checks)==76,'Family test denominator differs')
            for b in code+snapshots+[exe,ab,active['plan']]:verify(b)
            require('torch' not in sys.modules,'Model runtime imported by family development probe')
            after=active_bank(local);require(after['plan']==active['plan'],'Main plan changed during compatibility checks')
            checkpoint();resources_end=shared_allowance(local)
            freeze(output/'RESULT.json',dict(status='PASS_V4_APPLICATION_FAMILY_CHECKS_ONLY',utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'),checks=checks,tests_passed=sum(r['tests'] for r in checks),
                source_snapshots=snapshots,code_records=len(code),synthetic_join_review=joined,
                saved_lifetimes_reviewed=len(saved),bank_end=after,resources_end=resources_end,
                expanded_dependency_manifest_tested=256,maximum_permit_bytes=256*1024,lease_seconds=5,
                child_gate_AST_cap_only_verified=True,runner_collection_and_child_control_flow_unchanged=True,
                mocked_coordinator_and_child_lifecycle=True,actual_application_or_model_started=False,
                actual_saved_audio_executed=False,positive_production_plan_gate_executed=False,
                successful_supervised_application_admission=False,actual_panel_reviewed=False,
                semantic_content_and_resource_acceptance=False,restart_family_rebound=False,
                integrated_N4_cells=0,N4_accepted=False,N5_complete=False))
            print('PASS: 76 V4 child/runner/transport/cell/population/family checks; no application or model launch',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_APPLICATION_FAMILY_V4_PROBE_PRESERVED',owner=identity(process),
                error_type=type(exc).__name__,checks_completed=checks,source_snapshots=snapshots,
                admission=bind(output/'ADMISSION.json') if (output/'ADMISSION.json').exists() else None))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
