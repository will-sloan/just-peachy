"""Resource boundary regression; no model, audio or device. See README.md."""
import os
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'):os.environ[k]='1'
os.environ['CUDA_VISIBLE_DEVICES']=''
import psutil
p=psutil.Process();p.cpu_affinity([14]);p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
import unittest
from window_guard import budget,GIB


class BudgetTests(unittest.TestCase):
    def test_count_all_physical_bytes_and_retained_reservations(self):
        r=budget(35*GIB,10,128*1024**2,{'C:':100*GIB,'G:':90*GIB},50)
        self.assertEqual(r['projected_bytes'],35*GIB+128*1024**2+int(2.5*GIB))
        self.assertEqual(r['physical_bytes_credited'],0)

    def test_output_cap_and_floor_headroom_refuse(self):
        for used,requested,free in [(GIB,1,{'C:':100*GIB,'G:':90*GIB}),
            (0,1,{'C:':50*GIB,'G:':90*GIB}),(0,1,{'C:':100*GIB,'G:':75*GIB})]:
            with self.assertRaises(ValueError):budget(35*GIB,used,requested,free,50)

    def test_original_campaign_storage_ceiling_remains(self):
        with self.assertRaises(ValueError):budget(48*GIB,0,1,{'C:':100*GIB,'G:':100*GIB},50)

    def test_invalid_counts_refuse(self):
        for count in (-1,1.5,True):
            with self.assertRaises(ValueError):budget(count,0,1,{'C:':100*GIB,'G:':100*GIB},50)


if __name__=='__main__':unittest.main(verbosity=2)
