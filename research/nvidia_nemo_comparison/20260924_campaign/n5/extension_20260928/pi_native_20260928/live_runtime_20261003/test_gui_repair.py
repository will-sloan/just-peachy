"""Actual-label and finite GUI workflow regression contracts. README_NATIVE_GUI_DRIVER.md."""
import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
import native_gui_driver as driver


class RepairTests(unittest.TestCase):
    def test_actual_operator_sources_have_no_mojibake_and_driver_targets_real_labels(self):
        root=Path(__file__).parent
        trees={name:ast.parse((root/name).read_text(encoding='utf-8')) for name in
            ('launcher.py','runtime_ui.py','runtime_ui_channel.py','native_gui_driver.py')}
        for name,tree in trees.items():
            for node in ast.walk(tree):
                if isinstance(node,ast.Constant) and isinstance(node.value,str):
                    self.assertNotIn('\xe2\u20ac',node.value,name)
        visible={keyword.value.value for node in ast.walk(trees['launcher.py']) if isinstance(node,ast.Call)
            for keyword in node.keywords if keyword.arg=='text' and isinstance(keyword.value,ast.Constant)
            and isinstance(keyword.value.value,str)}
        driver_strings={node.value for node in ast.walk(trees['native_gui_driver.py'])
            if isinstance(node,ast.Constant) and isinstance(node.value,str)}
        for text in ('Sparse refresh interval in seconds (0.5-120)','Label revision window in seconds (1-300)','Choose saved WAV...'):
            self.assertIn(text,visible);self.assertIn(text,driver_strings)

    def test_policy_auto_stop_and_raw_save_are_explicit_live_only_300s(self):
        self.assertEqual(driver.validate_plan({},'capture-save-replay-discard',300,stop_mode='policy',save_raw=True)['input_source'],'live')
        driver.validate_plan({},'capture-save-replay-discard',300,stop_mode='button')
        for selection,seconds,mode,raw in [({},45,'policy',False),({'input_source':'saved'},300,'policy',False),
            ({'input_source':'saved'},45,'button',True),({},301,'button',False),({},300,'missing',False)]:
            with self.assertRaises(ValueError):driver.validate_plan(selection,'capture-save-replay-discard',seconds,'source.wav' if selection else None,stop_mode=mode,save_raw=raw)

    def test_auto_stop_proves_actual_samples_and_no_injected_stop(self):
        row=dict(status='stopped',processed_samples=4800000,spec=dict(duration_seconds=300))
        self.assertEqual(driver.require_policy_boundary(row,0),4800000)
        for changed,calls in [(dict(row,processed_samples=4799999),0),(row,1),(dict(row,status='failed'),0),(dict(row,spec=dict(duration_seconds=60)),0)]:
            with self.assertRaises(RuntimeError):driver.require_policy_boundary(changed,calls)

    def test_actual_raw_save_must_be_qualified_kept_and_exact_clock(self):
        row=dict(status='kept',include_raw=True,processed_samples=4800000,raw_samples=4800000,
            spec=dict(mode='raw_processed',sample_rate=16000,raw=dict(sample_rate=16000,qualification=dict(qualified=True))))
        driver.require_kept_choice(row,True)
        for changed in [dict(row,include_raw=False),dict(row,raw_samples=4799999),dict(row,status='stopped')]:
            with self.assertRaises(RuntimeError):driver.require_kept_choice(changed,True)
        changed=deepcopy(row);changed['spec']['raw']['qualification']['qualified']=False
        with self.assertRaises(RuntimeError):driver.require_kept_choice(changed,True)

    def test_replay_boundary_waits_natural_eof_without_injecting_stop(self):
        manager=SimpleNamespace(process=object(),poll=lambda:None,active_session_id=lambda:'replay',
            store=SimpleNamespace(read=lambda identifier:dict(processed_samples=4800000)))
        runner=driver.GuiDriver(manager,dict(input_source='saved'),'capture-save-replay-discard',300,Path('synthetic'),lambda *a:None)
        runner.root=SimpleNamespace(after=Mock());runner.stage='replay-running';runner.replay_frames=4800000
        runner.invoke=Mock();runner.tick()
        runner.invoke.assert_not_called();self.assertEqual(runner.stage,'replay-running');runner.root.after.assert_called_once()

if __name__=='__main__':unittest.main()
