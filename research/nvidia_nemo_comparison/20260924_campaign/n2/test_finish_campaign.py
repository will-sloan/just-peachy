"""Post-run admission/publication tests without models or UI. See README_FINISH.md."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('n2_finish_under_test',Path(__file__).with_name('finish_campaign.py'))
finish=importlib.util.module_from_spec(spec);spec.loader.exec_module(finish)
save=finish.campaign.atomic


class FinisherTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='N2 private finisher fixture ');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'frozen/prototype'
        self.source.mkdir(parents=True)
        for name in ('app/ui.py','main.py','tests/test_fixture.py'):
            p=self.source/name;p.parent.mkdir(exist_ok=True);p.write_text('# fixture\n')
        files={str(p.relative_to(self.source)).replace('\\','/'):finish.public_binding(p) for p in self.source.rglob('*') if p.is_file()}
        archive=self.root/'frozen.zip';archive.write_bytes(b'fixture immutable source archive')
        self.source_receipt=self.root/'SOURCE_RECEIPT.json'
        runtime=finish.runtime_files(files);ui={'app/ui.py':files['app/ui.py']['sha256']}
        save(self.source_receipt,dict(schema='just-peachy.n1.frozen-source.v1',prototype=str(self.source),files=files,file_count=len(files),
            frontend_runtime_sha256=finish.campaign.canonical(runtime),common_ui_source_sha256=finish.campaign.canonical(ui),common_ui_files=ui,archive=finish.binding(archive)))
        self.runtime=runtime;self.jobs=[]
        evaluation=self.root/'evaluation';evaluation.mkdir()
        for kind,count in (('screen',96),('regression',8)):
            manifest=evaluation/('AUDIO_ONLY.json' if kind=='screen' else 'REGRESSION_AUDIO_ONLY.json')
            rows=[dict(job_id=kind+'_'+str(i)) for i in range(count)];save(manifest,dict(jobs=rows))
            for combo in finish.COMBINATIONS:
                key=kind+'-'+combo;result=self.root/'children'/key/'RESULT_INDEX.json'
                contract=dict(combination=combo,source_bindings=runtime,manifest=finish.binding(manifest),
                    supervisor_sha256=finish.campaign.digest(finish.HERE.parent/'supervision/supervisor.py'))
                checksum=finish.campaign.canonical(contract)
                save(result.with_name('ADMISSION.json'),dict(contract=contract,contract_sha256=checksum))
                save(result,dict(status='COMPLETE',completed={row['job_id']:'private transcript path' for row in rows},failed={},total=count,contract_sha256=checksum))
                self.jobs.append(dict(id=key,argv=[sys.executable,'--source',str(self.source)],cwd=str(self.root),cells=count,
                    result=str(result),result_kind='controller',device='cpu',timeout_seconds=120))
        save(evaluation/'EVALUATOR_TRUTH.json',dict(fixture=True))
        save(evaluation/'ROSTERS.json',dict(fixture=True));save(evaluation/'MANIFEST_RECEIPT.json',dict(fixture=True))
        gui=self.root/'gui/GUI_PANEL_REPORT.json';save(gui,dict(status='COMPLETE',cells=[dict(status='COMPLETE') for _ in range(6)]))
        self.jobs.append(dict(id='gui-panel',argv=[sys.executable],cwd=str(self.root),cells=6,result=str(gui),result_kind='gui',device='cpu',timeout_seconds=120))
        self.coordinator=self.root/'coordinator';self.coordinator.mkdir();(self.coordinator/'owner.lock').touch()
        self.spec_path=self.root/'spec.json';self.document=dict(schema='n2-numerical-coordinator-v1',lanes=[dict(cpu=4,jobs=self.jobs)])
        save(self.spec_path,self.document)
        contract=dict(spec=self.document,runner_sha256=finish.campaign.digest(finish.HERE/'run_campaign.py'),
            io_version=finish.campaign.IO_VERSION,io_helper_sha256=finish.campaign.digest(finish.HERE/'io_utils.py'),
            supervisor_sha256=finish.campaign.digest(finish.HERE.parent/'supervision/supervisor.py'))
        checksum=finish.campaign.canonical(contract)
        save(self.coordinator/'ADMISSION.json',dict(contract=contract,contract_sha256=checksum))
        self.result=dict(schema='n2-numerical-coordinator-result-v1',status='COMPLETE',pid=2147483000,contract_sha256=checksum,
            completed=422,total=422,active=[],errors=[],jobs={job['id']:dict(status='COMPLETE',exit_code=0,cells=job['cells'],
                owner={'pid':2147483001,'create_time':1.},result=finish.campaign.completion(job)) for job in self.jobs})
        save(self.coordinator/'RESULT.json',self.result)
        tests=self.root/'tests.json';save(tests,dict(fixture=True))
        self.args=SimpleNamespace(spec=self.spec_path,coordinator_result=self.coordinator/'RESULT.json',source_receipt=self.source_receipt,
            test_report=tests,gui_report=gui,output=self.root/'private_output',public_out=self.root/'public_output')
        self.identity=patch.object(finish.campaign,'process_identity_state',return_value='ABSENT');self.identity.start();self.addCleanup(self.identity.stop)

    def summary(self,indexes,truth,out,public,manifest,scope):
        count=96 if scope=='screen48' else 8
        result=dict(status='COMPLETE',collection_status='COMPLETE',scored_total_cells=count*4,expected_total_cells=count*4,
            matched_four_way_cells=count,ASR_invariance_status='PASS_ALL_MATCHED',caption_invariance_status='PASS_OBSERVED_ONLY',failure_counts={})
        save(public/'SCREEN_SUMMARY.json',result);(public/'SCREEN_SUMMARY.md').write_text('Redacted fixture summary\n')
        save(out/'SCREEN_EVIDENCE.json',dict(private='private transcript path'))
        return result

    def patches(self,summary=None):
        from contextlib import ExitStack
        stack=ExitStack()
        stack.enter_context(patch.object(finish,'validate_gui',return_value=dict(status='COMPLETE',cells=6,archive_integrity_passed=True)))
        stack.enter_context(patch.object(finish,'validate_tests',return_value=dict(status='COMPLETE',tests=5,skipped=0)))
        aggregate=stack.enter_context(patch.object(finish,'summarize',side_effect=summary or self.summary))
        return stack,aggregate

    def test_complete_exact_population_writes_two_summaries_and_redacted_hashes(self):
        stack,aggregate=self.patches()
        with stack:self.assertEqual(finish.run(self.args),0)
        self.assertEqual(aggregate.call_count,2)
        report=finish.load(self.args.public_out/'FINAL_CHECKS.json')
        self.assertEqual(report['status'],'PASS');self.assertEqual(len(report['job_result_hashes']),9)
        self.assertFalse(report['model_calls']);self.assertFalse(report['stage_completion_claimed'])
        for path in self.args.public_out.iterdir():
            content=path.read_text();self.assertNotIn(str(self.root),content);self.assertNotIn('private transcript',content)
        self.assertEqual(set(p.name for p in self.args.public_out.iterdir()),set(finish.PUBLIC_NAMES))

    def test_quality_failure_preserves_both_summaries_and_nonzero_exit(self):
        def failed(*args):
            result=self.summary(*args)
            if args[-1]=='screen48':result.update(status='FAILED_ASR_INVARIANCE',ASR_invariance_status='FAILED');save(args[3]/'SCREEN_SUMMARY.json',result)
            return result
        stack,aggregate=self.patches(failed)
        with stack:self.assertEqual(finish.run(self.args),2)
        self.assertEqual(aggregate.call_count,2)
        result=finish.load(self.args.public_out/'FINAL_CHECKS.json');self.assertEqual(result['summaries']['regression']['status'],'COMPLETE')
        self.assertEqual(result['failures'][0]['stage'],'screen_quality')
        self.assertTrue((self.args.output/'screen/SCREEN_EVIDENCE.json').is_file())

    def test_summary_exception_does_not_drop_other_population_or_leak_private_error(self):
        def failed(*args):
            if args[-1]=='screen48':raise ValueError('private transcript at '+str(self.root))
            return self.summary(*args)
        stack,aggregate=self.patches(failed)
        with stack:self.assertEqual(finish.run(self.args),2)
        self.assertEqual(aggregate.call_count,2)
        self.assertIn('private transcript',(self.args.output/'PRIVATE_ERRORS.json').read_text())
        self.assertNotIn('private transcript',(self.args.public_out/'FINAL_CHECKS.json').read_text())
        self.assertTrue((self.args.public_out/'REGRESSION_SUMMARY.json').is_file())

    def test_running_coordinator_lock_refuses_without_output_or_wait(self):
        with finish.campaign.lock(self.coordinator/'owner.lock'):
            with self.assertRaises(BlockingIOError):finish.run(self.args)
        self.assertFalse(self.args.output.exists())

    def test_live_or_unverified_owner_refused(self):
        for state in ('ALIVE','UNVERIFIED'):
            with patch.object(finish.campaign,'process_identity_state',return_value=state),self.assertRaisesRegex(ValueError,'still active'):
                finish.validate_coordinator(self.spec_path,self.args.coordinator_result)

    def test_changed_result_spec_denominator_and_missing_job_refused(self):
        result_path=Path(self.jobs[0]['result']);result_path.write_text(result_path.read_text()+' ')
        with self.assertRaisesRegex(ValueError,'hash changed'):finish.validate_coordinator(self.spec_path,self.args.coordinator_result)
        for mutate in (lambda d:d['lanes'][0]['jobs'].pop(),lambda d:d['lanes'][0]['jobs'][0].update(cells=95)):
            document=deepcopy(self.document);mutate(document);save(self.spec_path,document)
            with self.assertRaises(ValueError):finish.validate_coordinator(self.spec_path,self.args.coordinator_result)

    def test_partial_or_failed_coordinator_never_scores(self):
        result=deepcopy(self.result);result.update(status='INCOMPLETE',completed=421);save(self.args.coordinator_result,result)
        stack,aggregate=self.patches()
        with stack:self.assertEqual(finish.run(self.args),2)
        aggregate.assert_not_called()

    def test_source_file_drift_and_other_controller_population_refused(self):
        finish.validate_source(self.source_receipt)
        finish.validate_controller_inputs({job['id']:job for job in self.jobs},self.source,self.runtime)
        (self.source/'app/ui.py').write_text('changed source')
        with self.assertRaisesRegex(ValueError,'source file changed'):finish.validate_source(self.source_receipt)
        path=Path(self.jobs[0]['result']);index=finish.load(path);index['completed']['unadmitted']='private';save(path,index)
        with self.assertRaisesRegex(ValueError,'exact completed population'):finish.validate_controller_inputs({job['id']:job for job in self.jobs},self.source,self.runtime)

    def test_existing_public_reports_and_private_public_overlap_refused(self):
        self.args.public_out.mkdir();(self.args.public_out/'FINAL_CHECKS.json').write_text('preserve')
        with self.assertRaisesRegex(ValueError,'already exist'):finish.run(self.args)
        self.assertEqual((self.args.public_out/'FINAL_CHECKS.json').read_text(),'preserve')
        self.args.public_out=self.args.output/'public'
        with self.assertRaisesRegex(ValueError,'separate'):finish.run(self.args)

    def test_suite_validation_redacts_skip_reasons_and_bound_private_paths(self):
        counts=dict(status='COMPLETE',successful=True,requested_modules=46,finished_modules=46,successful_modules=46,
            tests=500,planned_tests=500,failures=0,errors=0,skipped=2,expected_failures=0,unexpected_successes=0)
        private=dict(counts,skipped_tests=[{'reason':'private path '+str(self.root)}],report={'path':str(self.root)})
        module=SimpleNamespace(validate_completed_report=lambda report,source:private)
        with patch.object(finish,'file_module',return_value=module):
            self.assertEqual(finish.validate_tests(self.args.test_report,self.source_receipt),counts)

    def test_auxiliary_source_files_are_bound_and_cannot_escape_release(self):
        auxiliary=self.source.parent/'research/scoring.py';auxiliary.parent.mkdir();auxiliary.write_text('# scoring fixture\n')
        receipt=finish.load(self.source_receipt);receipt['auxiliary_files']={'research/scoring.py':finish.public_binding(auxiliary)}
        save(self.source_receipt,receipt);finish.validate_source(self.source_receipt)
        auxiliary.write_text('# changed scorer\n')
        with self.assertRaisesRegex(ValueError,'auxiliary file changed'):finish.validate_source(self.source_receipt)
        receipt['auxiliary_files']={'../escape.py':{'sha256':'0'*64,'bytes':1}};save(self.source_receipt,receipt)
        with self.assertRaisesRegex(ValueError,'auxiliary path escaped'):finish.validate_source(self.source_receipt)


if __name__=='__main__':unittest.main()
