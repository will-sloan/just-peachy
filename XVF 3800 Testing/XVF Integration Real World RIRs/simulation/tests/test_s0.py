"""Failure-oriented S0 contract checks; no audio, device, or model inference."""
import copy, hashlib, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from s0_catalog import angle_interval, corrected_distance
from s0_common import HashCache, safe_child, parse_sums

class BindingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def test_missing_and_hash_mismatch_are_explicit(self):
        c=HashCache();c.rows={}
        self.assertEqual(c.bind(self.root/'missing','0'*64)['status'],'MISSING')
        p=self.root/'input';p.write_bytes(b'expected')
        self.assertEqual(c.bind(p,'0'*64)['status'],'HASH_MISMATCH')
    def test_cache_reuse_and_changed_input_invalidation(self):
        c=HashCache();c.rows={};p=self.root/'input';p.write_bytes(b'abc')
        good=hashlib.sha256(b'abc').hexdigest()
        self.assertEqual(c.bind(p,good)['status'],'BOUND')
        self.assertEqual(c.bind(p,good)['status'],'BOUND');self.assertEqual(c.fresh,1)
        p.write_bytes(b'corrupt')
        self.assertEqual(c.bind(p,good)['status'],'HASH_MISMATCH');self.assertEqual(c.fresh,2)
    def test_manifest_path_cannot_escape_root(self):
        with self.assertRaises(ValueError):safe_child(self.root,'../escape.wav')
    def test_duplicate_manifest_entry_is_rejected(self):
        p=self.root/'sums';p.write_text('a  input\nb  input\n')
        with self.assertRaises(ValueError):parse_sums(p)

class GeometryTests(unittest.TestCase):
    def setUp(self):
        self.row={'run_id':'A','recorded_utc':'T','parent_manifest_sha256':'H',
                  'source_distance_m_original':100,'source_distance_m_effective':1.0}
        self.req={'setup':{'source':{'distance_to_array_m':100}}}
        self.result={'recorded_utc':'T'};self.binding={'sha256':'H','status':'BOUND'}
        self.c=[{'run_id':'A','recorded_utc':'T','parent_manifest_sha256':'H','original_value':100,'effective_value':1.0}]
    def test_repeated_load_never_divides_effective_distance(self):
        for _ in range(2):self.assertEqual(corrected_distance(self.row,self.req,self.result,self.binding,self.c)['effective_m'],1)
        self.assertEqual(self.req['setup']['source']['distance_to_array_m'],100)
    def test_wrong_timestamp_or_manifest_rejects_correction(self):
        for result,binding in [({'recorded_utc':'WRONG'},self.binding),(self.result,{'sha256':'WRONG','status':'BOUND'}),(self.result,{'sha256':'H','status':'HASH_MISMATCH'})]:
            with self.assertRaises(ValueError):corrected_distance(self.row,self.req,result,binding,self.c)
    def test_unexplained_or_out_of_range_distance_rejected(self):
        with self.assertRaises(ValueError):corrected_distance(self.row,self.req,self.result,self.binding,[])
        for bad in [0,-1,5.01,float('nan')]:
            row={**self.row,'source_distance_m_original':bad,'source_distance_m_effective':bad}
            req={'setup':{'source':{'distance_to_array_m':bad}}}
            with self.assertRaises(ValueError):corrected_distance(row,req,self.result,self.binding,[])
    def test_degree_intervals_wrap_without_changing_center(self):
        self.assertEqual(angle_interval(179)['segments_deg'],[[174,180],[-180,-176]])
        self.assertEqual(angle_interval(-179)['segments_deg'],[[176,180],[-180,-174]])
        self.assertEqual(angle_interval(-40)['segments_deg'],[[-45,-35]])
        self.assertEqual(angle_interval(-179)['center_original_deg'],-179)

if __name__=='__main__':unittest.main()
