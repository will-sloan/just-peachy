"""Future-admission boundaries; README_WINDOW_V4.md."""
import unittest
import psutil
psutil.Process().cpu_affinity([14])
from window_guard_v4 import budget, window, GIB
class BudgetChecks(unittest.TestCase):
    def test_authority_and_retained_constraints(self):
        w=window(); self.assertEqual(w['maximum_total_payload_gib'],52)
        self.assertEqual(w['maximum_new_output_bytes'],4*GIB)
        self.assertEqual(w['checkpoint_utc'],'2026-10-01T17:47:34Z')
        self.assertEqual(w['logical_cpus_total'],2); self.assertEqual(w['GPU'],'OFF')
        self.assertFalse(w['new_downloads']); self.assertTrue(w['prior_admissions_unchanged'])
    def test_exact_total_and_reservations(self):
        free={'C:':100*GIB,'G:':100*GIB}
        r=budget(int(49.5*GIB)-1,GIB,1,free,52)
        self.assertEqual(r['projected_bytes'],52*GIB)
        self.assertEqual(r['retained_reservations_bytes'],int(2.5*GIB))
        with self.assertRaises(ValueError):budget(int(49.5*GIB),GIB,1,free,52)
    def test_existing_usage_not_reset(self):
        free={'C:':100*GIB,'G:':100*GIB}
        budget(45*GIB,4*GIB-1,1,free,52)
        with self.assertRaises(ValueError):budget(45*GIB,4*GIB,1,free,52)
    def test_drive_floors_invalid_and_old_admission(self):
        free={'C:':100*GIB,'G:':100*GIB}
        for args in [(45*GIB,GIB,1,free,50),(45*GIB,GIB,1,{'C:':50*GIB,'G:':100*GIB},52),(45*GIB,GIB,1,{'C:':100*GIB,'G:':75*GIB},52),(45*GIB,-1,1,free,52),(45*GIB,GIB,0,free,52)]:
            with self.assertRaises(ValueError):budget(*args)
if __name__=='__main__': unittest.main()
