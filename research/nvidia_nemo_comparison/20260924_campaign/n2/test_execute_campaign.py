"""Model-free execution-chain ownership and failure tests. See README_EXECUTE.md."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import psutil

spec = importlib.util.spec_from_file_location('n2_execute_under_test', Path(__file__).with_name('execute_campaign.py'))
execute = importlib.util.module_from_spec(spec)
spec.loader.exec_module(execute)
save = execute.campaign.atomic


class ChainTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='N2 private chain fixture ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        process = psutil.Process()
        self.affinity, self.priority = process.cpu_affinity(), process.nice()
        self.addCleanup(lambda: process.cpu_affinity(self.affinity))
        self.addCleanup(lambda: process.nice(self.priority))
        self.args = SimpleNamespace(spec=self.root/'spec.json', output=self.root/'coordinator',
            state=self.root/'state', source_receipt=self.root/'SOURCE_RECEIPT.json',
            test_report=self.root/'tests.json', analysis_output=self.root/'analysis',
            public_out=self.root/'public', wait_for_existing=False)
        for name in ('spec', 'source_receipt', 'test_report'):
            save(getattr(self.args, name), {'fixture': name})
        self.contract = dict(schema='fixture', inputs={name: execute.finish.binding(getattr(self.args, name))
            for name in ('spec', 'source_receipt', 'test_report')}, tools={},
            interpreter=execute.finish.binding(sys.executable), gui_report=str(self.root/'gui/GUI_PANEL_REPORT.json'))
        self.plan = dict(lanes=[dict(jobs=[dict(timeout_seconds=1)])])

    def harness(self, codes, *, wait=False, bad_coordinator=False, write_final=True):
        self.args.wait_for_existing = wait
        events = []
        contract = deepcopy(self.contract)
        contract['existing_coordinator'] = {'fixture': True}

        def coordinator(*args):
            if bad_coordinator:
                raise ValueError('incomplete coordinator fixture')
            events.append('validated')
            return {}, {}

        codes_iter = iter(codes)
        def launch_fixed(argv, log, timeout, started):
            code = next(codes_iter)
            phase = 'coordinator' if Path(argv[2]).name == 'run_campaign.py' else 'final_checks'
            events.append(phase); started(dict(pid=123456, create_time=1.0))
            if phase == 'final_checks' and write_final:
                save(self.args.analysis_output/'FINAL_CHECKS.json', {'status': 'PASS' if code == 0 else 'FAILED'})
                for name in execute.finish.PUBLIC_NAMES: save(self.args.public_out/name, {'fixture': name})
            return code
        with patch.object(execute, 'admit', return_value=(contract, self.plan)), \
             patch.object(execute, 'launch', side_effect=launch_fixed), \
             patch.object(execute, 'wait_existing', side_effect=lambda *a: events.append('waited')), \
             patch.object(execute.finish, 'validate_coordinator', side_effect=coordinator):
            code = execute.run(self.args)
        return code, events, execute.finish.load(self.args.output/'CHAIN_RESULT.json')

    def test_coordinator_failure_prevents_finalizer(self):
        code, events, result = self.harness([7])
        self.assertEqual((code, events, result['status']), (2, ['coordinator'], 'INCOMPLETE'))
        self.assertFalse(self.args.analysis_output.exists())

    def test_sequential_success_requires_complete_coordinator_and_final_reports(self):
        code, events, result = self.harness([0, 0])
        self.assertEqual(events, ['coordinator', 'validated', 'final_checks'])
        self.assertEqual((code, result['status']), (0, 'READY_FOR_REVIEW'))
        self.assertFalse(result['stage_completion_claimed'])
        self.assertEqual(len(result['published_reports']), 6)

    def test_finalizer_nonzero_preserves_failed_output(self):
        code, _, result = self.harness([0, 2])
        self.assertEqual((code, result['status']), (2, 'FAILED_FINAL_CHECKS'))
        self.assertTrue((self.args.analysis_output/'FINAL_CHECKS.json').is_file())

    def test_zero_exit_without_final_checks_is_failure(self):
        code, _, result = self.harness([0, 0], write_final=False)
        self.assertEqual((code, result['status']), (2, 'FAILED_FINAL_CHECKS'))

    def test_incomplete_coordinator_receipt_blocks_finisher_after_zero_exit(self):
        code, events, result = self.harness([0], bad_coordinator=True)
        self.assertEqual((code, events, result['status']), (2, ['coordinator'], 'INCOMPLETE'))

    def test_existing_mode_launches_only_finalizer_after_observed_exit(self):
        code, events, result = self.harness([0], wait=True)
        self.assertEqual(events, ['waited', 'validated', 'final_checks'])
        self.assertEqual((code, result['status']), (0, 'READY_FOR_REVIEW'))

    def test_failed_preflight_never_launches(self):
        with patch.object(execute, 'admit', side_effect=ValueError('test suite incomplete')), \
             patch.object(execute, 'launch') as launch:
            self.assertEqual(execute.run(self.args), 2)
            launch.assert_not_called()
        self.assertEqual(execute.finish.load(self.args.output/'CHAIN_RESULT.json')['status'], 'INCOMPLETE')

    def test_live_or_unverified_prior_child_rejects_restart(self):
        for state in ('ALIVE', 'UNVERIFIED'):
            with self.subTest(state=state), patch.object(execute.campaign, 'process_identity_state', return_value=state):
                with self.assertRaises(RuntimeError):
                    execute.reject_live({'child': {'pid': 42, 'create_time': 1.0}})

    def test_contract_drift_and_existing_reports_rejected(self):
        save(self.args.spec, {'changed': True})
        with self.assertRaises(ValueError): execute.verify_contract(self.contract)
        self.args.analysis_output.mkdir()
        with self.assertRaises(ValueError): execute.require_fresh_reports(self.args)

    def test_exact_422_plan_rejects_wrong_source_partial_population_and_kind(self):
        source=self.root/'source'; source.mkdir()
        jobs=[]
        for key,count in execute.finish.EXPECTED.items():
            gui=key=='gui-panel'; out=self.root/key
            argv=[sys.executable,'-B',str(execute.HERE/('gui/panel.py' if gui else 'run_screen.py')),
                  '--source',str(source),'--output',str(out),'--cpu','4']
            if not gui:
                manifest=self.root/(key+'.json');save(manifest,dict(jobs=[dict(job_id=str(i)) for i in range(count)]))
                argv+=['--combination',key.split('-',1)[1],'--profile','low_latency','--device','cpu','--manifest',str(manifest)]
            jobs.append(dict(id=key,cells=count,argv=argv,cwd=str(self.root),device='cpu',timeout_seconds=10,
                result_kind='gui' if gui else 'controller',result=str(out/('GUI_PANEL_REPORT.json' if gui else 'RESULT_INDEX.json'))))
        last=jobs.pop();last['argv'][last['argv'].index('--cpu')+1]='14'
        plan=dict(schema='n2-numerical-coordinator-v1',lanes=[dict(cpu=4,jobs=jobs),dict(cpu=14,jobs=[last])])
        self.assertEqual(len(execute.validate_plan(plan,source)),9)
        for mutate in (lambda j:j.update(cells=95),lambda j:j.update(result_kind='native'),
                       lambda j:j['argv'].extend(['--limit','1']),
                       lambda j:j['argv'].__setitem__(j['argv'].index('--source')+1,str(self.root/'other'))):
            changed=deepcopy(plan);mutate(changed['lanes'][0]['jobs'][0])
            with self.assertRaises(ValueError):execute.validate_plan(changed,source)

    def test_existing_admission_binds_exact_supervisor_command_identity_and_contract(self):
        argv=[sys.executable,'-B',str(execute.HERE/'run_campaign.py'),'--spec',str(self.args.spec),
              '--output',str(self.args.output),'--state',str(self.args.state)]
        save(self.args.state/'worker_spec.json',dict(argv=argv,cwd=str(self.root)))
        worker=dict(pid=43,create_time=2.0,child_pid=42,child_create_time=1.0,child_launch_pending=False,
            run_id='fixture',status='COMPLETED',argv_sha256=hashlib.sha256(json.dumps(argv).encode()).hexdigest())
        save(self.args.state/'worker.json',worker)
        save(self.args.state/'campaign.json',dict(target_utc=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),packaging_reserve_hours=1))
        contract=dict(spec=execute.finish.load(self.args.spec),runner_sha256=execute.campaign.digest(execute.HERE/'run_campaign.py'),
            io_version=execute.campaign.IO_VERSION,io_helper_sha256=execute.campaign.digest(execute.HERE/'io_utils.py'),
            supervisor_sha256=execute.campaign.digest(execute.HERE.parent/'supervision/supervisor.py'))
        save(self.args.output/'ADMISSION.json',dict(contract_sha256=execute.campaign.canonical(contract),contract=contract))
        with patch.object(execute.campaign,'process_identity_state',return_value='ABSENT'):
            binding=execute.existing_coordinator(self.args)
            self.assertEqual(binding['child'],dict(pid=42,create_time=1.0))
            worker['argv_sha256']='changed';save(self.args.state/'worker.json',worker)
            with self.assertRaises(ValueError):execute.existing_coordinator(self.args)

    def test_waiter_checks_exact_identity_and_zero_exit_without_process_actions(self):
        worker = dict(run_id='fixture', argv_sha256='argv', child_pid=42, child_create_time=1.0,
                      status='RUNNING', exit_code=None)
        save(self.args.state/'worker.json', worker)
        save(self.args.state/'campaign.json', {'fixture': True})
        stamp = self.root/'immutable.json'; save(stamp, {'fixture': True})
        binding = dict(child={'pid': 42, 'create_time': 1.0}, run_id='fixture', argv_sha256='argv',
                       packaging_cutoff_utc=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),
                       worker_spec=execute.finish.binding(stamp), coordinator_admission=execute.finish.binding(stamp))
        def end(_):
            worker.update(status='COMPLETED', exit_code=0); save(self.args.state/'worker.json', worker)
        with patch.object(execute.campaign, 'process_identity_state', side_effect=['ALIVE', 'ABSENT']), \
             patch.object(execute.campaign, 'disk_reserves', return_value=({}, [])), \
             patch.object(execute.time, 'sleep', side_effect=end) as sleep, \
             patch.object(execute.campaign, 'stop_owned_tree') as stop, patch.object(execute.subprocess, 'Popen') as launch:
            execute.wait_existing(self.args, binding)
            sleep.assert_called_once_with(5); stop.assert_not_called(); launch.assert_not_called()
        worker.update(status='FAILED', exit_code=9); save(self.args.state/'worker.json', worker)
        with patch.object(execute.campaign, 'process_identity_state', return_value='ABSENT'):
            with self.assertRaises(RuntimeError): execute.wait_existing(self.args, binding)
        worker['child_create_time'] = 2.0; save(self.args.state/'worker.json', worker)
        with self.assertRaises(RuntimeError): execute.wait_existing(self.args, binding)

    def test_waiter_disk_deadline_leave_external_process_untouched(self):
        worker = dict(run_id='fixture', argv_sha256='argv', child_pid=42, child_create_time=1.0, status='RUNNING')
        save(self.args.state/'worker.json', worker); save(self.args.state/'campaign.json', {})
        stamp = self.root/'immutable.json'; save(stamp, {})
        binding = dict(child={'pid': 42, 'create_time': 1.0}, run_id='fixture', argv_sha256='argv',
            packaging_cutoff_utc=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),
            worker_spec=execute.finish.binding(stamp), coordinator_admission=execute.finish.binding(stamp))
        with patch.object(execute.campaign, 'process_identity_state', return_value='ALIVE'), \
             patch.object(execute.campaign, 'disk_reserves', return_value=({}, ['G:'])), \
             patch.object(execute.campaign, 'stop_owned_tree') as stop:
            with self.assertRaises(RuntimeError): execute.wait_existing(self.args, binding)
            binding['packaging_cutoff_utc']=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
            with self.assertRaises(TimeoutError): execute.wait_existing(self.args, binding)
            stop.assert_not_called()

    def test_real_harmless_child_exit_is_waited_and_identity_recorded(self):
        owners = []
        code = execute.launch([sys.executable, '-B', '-c', 'print("harmless chain fixture")'],
                              self.root/'child.log', 10, owners.append)
        self.assertEqual(code, 0)
        self.assertEqual(len(owners), 1)
        self.assertIn(execute.campaign.process_identity_state(owners[0]['pid'], owners[0]['create_time']), ('ABSENT', 'PID_REUSED'))
        self.assertIn('harmless chain fixture', (self.root/'child.log').read_text())


if __name__ == '__main__': unittest.main()
