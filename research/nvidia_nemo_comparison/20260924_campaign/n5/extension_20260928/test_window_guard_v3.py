"""V3 budget boundary checks; README_WINDOW_V3.md."""
import unittest
from window_guard_v3 import budget, window, GIB

class BudgetChecks(unittest.TestCase):
    def test_new_capacity_and_old_constraints(self):
        w=window();self.assertEqual(w['maximum_new_output_bytes'],4*GIB)
        self.assertEqual(w['checkpoint_utc'],'2026-10-01T17:47:34Z')
        self.assertEqual(w['logical_cpus_total'],2);self.assertEqual(w['GPU'],'OFF')
        self.assertFalse(w['new_downloads'])
        r=budget(40*GIB,GIB,700*1024**2,{'C:':100*GIB,'G:':100*GIB},50)
        self.assertEqual(r['window_maximum_bytes'],4*GIB)
        self.assertEqual(r['retained_reservations_bytes'],int(2.5*GIB))
    def test_exact_and_excess_limit(self):
        free={'C:':100*GIB,'G:':100*GIB}
        budget(40*GIB,4*GIB-1,1,free,50)
        with self.assertRaises(ValueError):budget(40*GIB,4*GIB,1,free,50)
    def test_payload_floor_and_invalid_bytes(self):
        free={'C:':100*GIB,'G:':100*GIB}
        for args in [(48*GIB,GIB,1,free,50),(40*GIB,GIB,1,{'C:':50*GIB,'G:':100*GIB},50),(40*GIB,GIB,1,{'C:':100*GIB,'G:':75*GIB},50),(40*GIB,-1,1,free,50),(40*GIB,GIB,0,free,50)]:
            with self.assertRaises(ValueError):budget(*args)

if __name__=='__main__':unittest.main()
