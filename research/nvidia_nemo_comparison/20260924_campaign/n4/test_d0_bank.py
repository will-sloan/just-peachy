"""Component cache, gzip integrity and quota tests. README_D0_BANK.md."""
from copy import deepcopy
import gzip
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import d0_bank_components as bank


class TestBank(unittest.TestCase):
    def job(self):return dict(job_id='N2_S45_01_01_O0',audio_path='not-opened.wav',audio_sha256='0'*64,
        frames=16000,sample_rate_hz=16000,gain=1,reset_between_scenes=True,tap='O0')
    def test_cache_separates_exact_contract_model_audio_profile(self):
        job=self.job();base=bank.cell_key('a',job,'E0',{'cadence':'fixed'})
        for admission,j,encoder,profile in [('b',job,'E0',{'cadence':'fixed'}),
            ('a',dict(job,audio_sha256='1'*64),'E0',{'cadence':'fixed'}),
            ('a',job,'E1',{'cadence':'fixed'}),('a',job,'E0',{'cadence':'changed'})]:
            self.assertNotEqual(base,bank.cell_key(admission,j,encoder,profile))
    def test_truth_and_gain_rejected(self):
        for job in [dict(self.job(),reference='forbidden'),dict(self.job(),gain=2),dict(self.job(),reset_between_scenes=False)]:
            with self.assertRaises(ValueError):bank.cell_key('a',job,'E0',{})
    def test_gzip_crc_and_exact_expanded_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'events.gz';value='{"test":"\u00e9"}\n'.encode('utf-8')
            with gzip.open(path,'wb') as stream:stream.write(value)
            self.assertEqual(bank.event_digest(path),dict(uncompressed_sha256=hashlib.sha256(value).hexdigest(),uncompressed_bytes=len(value)))
            data=path.read_bytes();path.write_bytes(data[:-2])
            with self.assertRaises(EOFError):bank.event_digest(path)
    def test_quota_and_disk_floor_fail_before_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);policy=dict(target_utc='2099-01-01T00:00:00+00:00')
            with patch.object(bank,'load',return_value=policy),patch.object(bank.supervisor,'disk_reserves',return_value=({},[])):
                bank.resource_guard(root,root)
                with patch.object(bank,'LIMIT',32*1024**2-1):
                    with self.assertRaisesRegex(RuntimeError,'allocation'):bank.resource_guard(root,root)
            with patch.object(bank,'load',return_value=policy),patch.object(bank.supervisor,'disk_reserves',return_value=({},['G:'])):
                with self.assertRaisesRegex(RuntimeError,'reserve'):bank.resource_guard(root,root)
    def test_packaging_cutoff(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(bank,'load',return_value=dict(target_utc='2000-01-01T00:00:00+00:00')):
            with self.assertRaises(TimeoutError):bank.resource_guard(Path(tmp),Path(tmp))


if __name__=='__main__':unittest.main()
