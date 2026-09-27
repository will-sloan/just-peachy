"""Model-free packaging boundary tests; README_REVIEWED_HANDOFF_V2.md."""
import unittest
from package_reviewed_handoff_v2 import collect,relative


class Boundaries(unittest.TestCase):
    def test_explicit_small_selection(self):
        names=[f'n5/report_{i}.md' for i in range(27)]
        self.assertEqual(len(collect(names,lambda _:b'fixture')),27)
    def test_path_escape_binary_and_duplicate_refused(self):
        for name in ['../private.md','/absolute.json','C:/data.md','n5\\secret.json','n5//x.md','n5/./x.md','n5/model.onnx','n5/audio.wav','GITHUB_BACKUP_RECEIPT.json','HANDOFF_MANIFEST.json']:
            with self.subTest(name=name),self.assertRaises(ValueError):relative(name)
        with self.assertRaises(ValueError):collect(['n5/same.md']*27,lambda _:b'fixture')
    def test_oversized_and_empty_refused(self):
        names=[f'n5/report_{i}.md' for i in range(27)]
        for data in [b'',b'x'*(2*1024**2+1)]:
            with self.assertRaises(ValueError):collect(names,lambda _:data)
    def test_population_limits(self):
        for count in [0,26,58]:
            with self.assertRaises(ValueError):collect([f'n5/r{i}.md' for i in range(count)],lambda _:b'x')


if __name__=='__main__':unittest.main()
