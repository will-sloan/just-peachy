"""Motion/seat safety only; synthetic events and people, no physical sensor."""
from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import time
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'vendor')]
from app.motion import MotionEvent,MotionSafety
from app.controller import Controller
from app.paths import default_models_root,sha256
from app.seats import SeatSession
from test_people import quality,ROUTE


class MotionTests(unittest.TestCase):
    def setUp(self):
        self.gate=MotionSafety(clock=lambda:10_000_000_000)
        self.event=MotionEvent('moving',9_500_000_000,9_600_000_000,.9,True)

    def test_moving_settling_uncertain_and_stale_invalidate(self):
        for change in ({},{'state':'settling'},{'state':'stationary','quality':.1},
                       {'state':'stationary','translation_or_range_unknown':True},
                       {'state':'stationary','source_monotonic_ns':1}):
            with self.subTest(change=change):
                gate=MotionSafety(clock=self.gate.clock)
                self.assertTrue(gate.accept(replace(self.event,**change))['invalidate'])

    def test_no_out_of_order_restore_or_position_claim(self):
        self.assertTrue(self.gate.accept(self.event)['invalidate'])
        self.assertFalse(self.gate.accept(replace(self.event,state='stationary'))['accepted'])
        self.assertFalse(self.gate.accept(replace(self.event,state='stationary',source_monotonic_ns=9_600_000_000))['invalidate'])
        state=self.gate.snapshot()
        self.assertEqual(state['source'],'mock')
        self.assertFalse(state['absolute_position_or_yaw'])
        self.assertFalse(state['automatic_reanchor'])
        self.assertFalse(state['hardware_opened'])

    def test_invalid_clocks_values_and_provenance_refused(self):
        for change in ({'state':'located'},{'quality':float('nan')},{'quality':True},
                       {'clock_domain':'device_ticks'},{'received_monotonic_ns':11_000_000_000},
                       {'source_monotonic_ns':9_700_000_000},{'simulated':1},
                       {'translation_or_range_unknown':None}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                self.gate.accept(replace(self.event,**change))

    def test_controller_preserves_people_and_stationary_does_not_reanchor(self):
        with tempfile.TemporaryDirectory() as td:
            c=Controller(Path(td)/'data',default_models_root())
            try:
                v=np.zeros(192,np.float32);v[0]=1
                pid=c.store.save('Synthetic motion fixture',v,quality(),ROUTE)['id']
                rows=[dict(person_id=pid,angle_deg=30.)]
                c.seats=SeatSession(rows)
                before={str(p):sha256(p) for p in (c.data_root/'people').rglob('*') if p.is_file()}
                for state in ('moving','settling','stationary'):
                    now=time.monotonic_ns()
                    c.motion_event(MotionEvent(state,now,now,.9,True))
                    c.commands.join()
                    self.assertIsNone(c.error)
                    self.assertFalse(c.seating_snapshot()['valid'])
                self.assertEqual(before,{str(p):sha256(p) for p in (c.data_root/'people').rglob('*') if p.is_file()})
                self.assertEqual(c.models.asr_loads+c.models.speaker_loads,0)
                self.assertEqual(c.state,'IDLE')
                self.assertIn('fresh voice and direction',c.status)
            finally:
                c.close();c.commands.join();c.worker.join(10)


if __name__=='__main__':unittest.main()
