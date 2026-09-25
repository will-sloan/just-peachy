"""Full-bank admission/storage tests. See README_ASR_FULL_BANK.md."""
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import asr_full_bank as runner
import test_asr_lane_components as fixtures


def bank():
    return [dict(job_id=f'test_{i:03d}_{tap}', audio_path='test.wav', audio_sha256='test',
        frames=3205, sample_rate_hz=16000, gain=1, reset_between_scenes=True, tap=tap)
        for i in range(240) for tap in ('O0','O1')]


class TestFullBank(unittest.TestCase):
    def test_full_population_not_smoke_or_duplicate(self):
        jobs=bank();self.assertEqual(len(runner.check_bank(jobs)),480)
        for bad in (jobs[:2],jobs[:-1]+[jobs[0]]):
            with self.assertRaises(ValueError):runner.check_bank(bad)
        jobs[-1]['tap']='O0'
        with self.assertRaisesRegex(ValueError,'tap'):runner.check_bank(jobs)

    def test_reference_or_gain_cannot_enter_full_bank(self):
        for field,value in [('reference','test'),('gain',1.4125),('reset_between_scenes',False)]:
            jobs=bank();jobs[0][field]=value
            with self.assertRaises(ValueError):runner.check_bank(jobs)

    def test_utf8_budget_stops_before_partial_event(self):
        output=io.StringIO();writer=runner.BoundedTextWriter(output,limit=5)
        writer.write('éé')
        with self.assertRaises(RuntimeError):writer.write('é')
        self.assertEqual(output.getvalue(),'éé');self.assertEqual(writer.written,4)
        writer.write('x');self.assertEqual(writer.written,5)

    def test_actual_loop_endpoint_and_tail_survive_bounded_writer(self):
        fixtures.TestRealASRLoops.setUpClass()
        t=fixtures.TestRealASRLoops();capture=t.capture()
        output=io.StringIO();capture.log=runner.BoundedTextWriter(output)
        t.base._asr_loop(capture,fixtures.BaselineStub())
        summary=capture.finish_capture()
        rows=[json.loads(s) for s in output.getvalue().splitlines()]
        self.assertEqual(summary['input_samples'],3205)
        self.assertEqual(summary['final_utterances'],['test words','tail word'])
        self.assertEqual(sum(r['event_type']=='research_asr_tail_dispatch' for r in rows),1)

    def test_inventory_counts_all_bytes_without_dedup(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'a').write_bytes(b'123');(root/'sub').mkdir()
            (root/'sub/b').write_bytes(b'123')
            result=runner.payload_inventory(root)
            self.assertEqual(result['total_logical_bytes'],6);self.assertEqual(result['files'],2)

    def test_storage_and_reserve_deadline_stop(self):
        policy={'target_utc':'2026-09-28T14:48:19+00:00'}
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with patch.object(runner,'load',return_value=policy),patch.object(runner.supervisor,'disk_reserves',return_value=({},[])):
                runner.resource_guard(root,root)
                with patch.object(runner,'ALLOCATION',1):
                    with self.assertRaisesRegex(RuntimeError,'allocation'):runner.resource_guard(root,root)
                with patch.object(runner.supervisor,'disk_reserves',return_value=({},['G:'])):
                    with self.assertRaisesRegex(RuntimeError,'reserve'):runner.resource_guard(root,root)
                policy['target_utc']='2020-01-01T00:00:00+00:00'
                with self.assertRaises(TimeoutError):runner.resource_guard(root,root)

    def test_failed_or_incomplete_smoke_not_admitted(self):
        good=dict(schema='n4-asr-smoke-review-v1',status='PASS_ASR_COMPONENT_SMOKE',
            component_cells=8,per_variant=2,cells=[{}]*8,integrated_N4_cells=0,
            Controller_or_widget_parity_qualified=False)
        for key,value in [('status','READY_FOR_REVIEW'),('component_cells',7),('cells',[{}]*7),
                ('integrated_N4_cells',8),('Controller_or_widget_parity_qualified',True)]:
            bad=deepcopy(good);bad[key]=value
            with patch.object(runner,'load',return_value=bad):
                with self.assertRaises(ValueError):runner.verify_smoke_review(Path('unused'))


if __name__=='__main__':unittest.main()
