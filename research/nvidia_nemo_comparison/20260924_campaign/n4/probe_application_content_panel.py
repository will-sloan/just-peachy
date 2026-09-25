"""Guarded panel content wrapper tests. README_APPLICATION_CONTENT_PANEL.md."""
import argparse
from datetime import datetime, timezone
import io
from pathlib import Path
import time
import unittest

from common import bind, freeze, load, verify
from metric_process import exact_process, identity, pin
from probe_application_transport_review import active_d1
from review_scoring_bank import guard, require, shared_allowance
from scoring_bank import writer_lock
from review_application_content_panel import OWN, code_bindings
import test_application_content_panel as regression

HERE=Path(__file__).resolve().parent
LOCAL=Path('G:/Just_Peachy_N1/20260924_campaign/local')


def run(output):
    process=pin();started=time.monotonic()
    require(not output.exists() and output.resolve().is_relative_to(LOCAL/'n4'),'Fresh private probe required')
    with writer_lock(LOCAL/'n4/metric-scoring.owner.lock'):
        guard(output,LOCAL,started,720);inventory=shared_allowance(LOCAL);active=active_d1()
        freeze(output/'PROBE_OWNER.json',dict(owner=identity(process),utc=datetime.now(timezone.utc).isoformat()))
        (output/'source').mkdir();snapshots=[]
        for name in OWN:
            path=output/'source'/name;path.write_bytes((HERE/name).read_bytes())
            require(bind(path)['sha256']==bind(HERE/name)['sha256'],'Attempt snapshot differs');snapshots.append(bind(path))
        try:
            code=code_bindings()
            for b in code:verify(b)
            q=load(HERE/'APPLICATION_CONTENT_CHECK_V1.json');proof=load(q['private_receipt']['path'])
            synthetic=proof['synthetic_content'];verify(synthetic)
            old=load(HERE/'APPLICATION_CELL_REVIEW_CHECK_V2.json');verify(old['synthetic_join_review'])
            freeze(output/'ADMISSION.json',dict(owner=identity(process),code=code,source_snapshots=snapshots,
                inventory=inventory,D1_snapshot=active,synthetic_content=synthetic,synthetic_cell=old['synthetic_join_review'],
                production_plan_created=False,new_application_or_model_started=False))
            regression.CONTEXT.update(output=output,synthetic_content=synthetic)
            regression.prior.CONTEXT.update(output=output,synthetic_join=old['synthetic_join_review'])
            stream=io.StringIO();tests=unittest.TextTestRunner(stream=stream,verbosity=2).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(regression.ContentPanelTests))
            (output/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
            require(tests.wasSuccessful() and tests.testsRun==14 and not tests.skipped,'Panel content checks failed')
            for b in code+[synthetic,old['synthetic_join_review']]:verify(b)
            after=active_d1();require(after['result']['child']==active['result']['child'] and after['run_id']==active['run_id'],'D1 owner changed')
            guard(output,LOCAL,started,720)
            freeze(output/'RESULT.json',dict(status='PASS_APPLICATION_CONTENT_PANEL_CHECKS_ONLY',utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'),tests=bind(output/'tests.txt'),tests_passed=tests.testsRun,
                synthetic_compact=bind(output/'SYNTHETIC_COMPACT_CONTENT.json'),synthetic_groups=bind(output/'SYNTHETIC_GROUPED_COVERAGE.json'),
                D1_after=after,development_population_sizes=[40,240],positive_production_plan_gate_executed=False,
                actual_panel_reviewed=False,new_application_or_model_started=False,integrated_N4_cells=0,N4_accepted=False))
            print('PASS: 14 content-panel coverage and scope checks; no actual plan/panel/app/audio/model launch',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_APPLICATION_CONTENT_PANEL_PROBE_PRESERVED',error_type=type(exc).__name__,
                owner=identity(process),source_snapshots=snapshots,
                admission=bind(output/'ADMISSION.json') if (output/'ADMISSION.json').exists() else None));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
