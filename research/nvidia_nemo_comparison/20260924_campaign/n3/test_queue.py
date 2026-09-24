"""Model-free prerequisite/receipt tests; see README_QUEUE.md."""
import importlib.util
import json
import hashlib
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('n3_queue_under_test',Path(__file__).with_name('supervise_n3.py'))
queue=importlib.util.module_from_spec(spec);spec.loader.exec_module(queue)


class GateTests(unittest.TestCase):
    def test_freeze_ignores_mutable_bytecode_caches(self):
        spec=importlib.util.spec_from_file_location('n3_prepare_under_test',Path(__file__).with_name('prepare.py'))
        preparation=importlib.util.module_from_spec(spec);spec.loader.exec_module(preparation)
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);work=base/'work';local=base/'local';prototype=work/'prototype'
            inputs={'main.py':b'# fixture\n','config/ui.json':b'{}\n','app/n3_models.py':b'VALUE=1\n',
                    'app/__pycache__/n3_models.cpython-311.pyc':b'mutable-cache',
                    'app/n3_models.pyc':b'legacy-cache'}
            for name,data in inputs.items():
                path=prototype/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
            previous=local/'releases/n2-common-v7/SOURCE_RECEIPT.json';previous.parent.mkdir(parents=True)
            files={name:dict(sha256=hashlib.sha256(inputs[name]).hexdigest(),bytes=len(inputs[name]))
                   for name in ('main.py','config/ui.json')}
            previous.write_text(json.dumps(dict(files=files,auxiliary_files={},
                common_ui_files={'main.py':files['main.py']['sha256']},frontend_hash_scope='fixture')))
            with patch.object(preparation,'WORKTREE',work),patch.object(preparation,'LOCAL',local):
                frozen=preparation.freeze(local/'releases/n3-test')
            receipt=json.loads((frozen.parent/'SOURCE_RECEIPT.json').read_text())
            self.assertEqual(set(receipt['files']),{'main.py','config/ui.json','app/n3_models.py'})
            self.assertEqual((frozen/'app/n3_models.py').read_bytes(),inputs['app/n3_models.py'])
            self.assertFalse((frozen/'app/__pycache__').exists())

    def test_script_directory_does_not_shadow_standard_queue(self):
        folder=str(Path(__file__).resolve().parent)
        code='import sys; sys.path.insert(0,sys.argv[1]); import queue; assert hasattr(queue,"Queue") and hasattr(queue,"Empty")'
        subprocess.run([sys.executable,'-B','-c',code,folder],check=True,capture_output=True)

    def setUp(self):
        self.expected=dict(numerical_contract='n',chain_contract='c')
        self.numerical=dict(contract_sha256='n',status='COMPLETE',completed=422,total=422)
        self.chain=dict(contract_sha256='c',status='READY_FOR_REVIEW')

    def test_only_complete_matching_pair_is_ready(self):
        self.assertEqual(queue.prerequisite(self.numerical,self.chain,self.expected),'READY')
        self.numerical['completed']=421
        self.assertEqual(queue.prerequisite(self.numerical,self.chain,self.expected),'WAITING_N2')

    def test_different_contract_blocks_even_when_complete(self):
        self.numerical['contract_sha256']='another run'
        self.assertEqual(queue.prerequisite(self.numerical,self.chain,self.expected),'BLOCKED_CONTRACT_CHANGED')

    def test_finalizer_failure_never_dispatches(self):
        for status in ('INCOMPLETE','FAILED_FINAL_CHECKS','FAILED'):
            self.chain['status']=status
            self.assertEqual(queue.prerequisite(self.numerical,self.chain,self.expected),'BLOCKED_N2_FAILURE')

    def test_numerical_terminal_incomplete_never_waits_forever(self):
        self.numerical['status']='INCOMPLETE'
        self.assertEqual(queue.prerequisite(self.numerical,self.chain,self.expected),'BLOCKED_N2_FAILURE')

    def test_live_or_unverified_process_blocks_handoff(self):
        for status,expected in [('ALIVE',False),('UNVERIFIED',False),('ABSENT',True),('PID_REUSED',True)]:
            with patch.object(queue.supervisor,'process_identity_state',return_value=status):
                self.assertEqual(queue.owner_gone(dict(pid=1,create_time=2)),expected)

    def test_zero_exit_needs_complete_declared_denominator(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'RESULT.json';job=dict(result=str(path),expected_cells=96)
            self.assertFalse(queue.accepted(job,0)[0])
            for value in [dict(status='COMPLETE',completed=95,total=96),dict(status='FAILED',completed=96,total=96),
                          dict(status='COMPLETE',completed=96,total=96,successful=False)]:
                path.write_text(json.dumps(value),encoding='utf-8');self.assertFalse(queue.accepted(job,0)[0])
            path.write_text(json.dumps(dict(status='COMPLETE',completed=96,total=96)),encoding='utf-8')
            self.assertTrue(queue.accepted(job,0)[0]);self.assertFalse(queue.accepted(job,1)[0])

    def test_changed_admitted_file_stops_execution(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'source.py';path.write_text('first')
            document=dict(bindings=[dict(path=str(path),sha256=queue.sha(path))])
            queue.verify(document);path.write_text('second')
            with self.assertRaisesRegex(ValueError,'Admission changed'):queue.verify(document)


if __name__=='__main__':unittest.main()
