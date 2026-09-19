"""Offline noise intake regressions; see README_S45_NOISE.md."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import s45_noise as n

class NoiseTests(unittest.TestCase):
    def test_archive_paths_reject_traversal_drive_and_windows_separators(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ('../escape','/absolute','C:/escape','musan/../../escape',r'musan\..\escape'):
                with self.subTest(name=name), self.assertRaises(ValueError):n.safe_member(name,tmp)
            self.assertEqual(n.safe_member('musan/noise/test.wav',tmp),Path(tmp).resolve()/'musan/noise/test.wav')

    def test_mono_selection_preserves_original_channel_and_level(self):
        x=np.column_stack((np.array([.1,-.2,.3],dtype=np.float32),np.ones(3,dtype=np.float32)))
        self.assertTrue(np.array_equal(n.convert_mono(x,16000),x[:,0]))
        self.assertTrue(np.array_equal(n.convert_mono(x,16000,1),x[:,1]))

    def test_antialiasing_rejects_above_output_nyquist(self):
        rate=48000;t=np.arange(rate)/rate
        low=n.convert_mono(.1*np.sin(2*np.pi*3000*t),rate)
        high=n.convert_mono(.1*np.sin(2*np.pi*14000*t),rate)
        self.assertEqual(len(low),16000)
        self.assertLess(float(np.std(high[100:-100])),float(np.std(low[100:-100]))*.01)

    def test_nonfinite_is_not_a_usable_noise_source(self):
        for x in ([0,float('nan')],[float('inf')]):
            with self.assertRaises(ValueError):n.convert_mono(x,16000)

    def test_atomic_manifest_retries_transient_windows_reader(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'status.json';path.write_text('{"old":true}',encoding='utf-8')
            original=n.os.replace;calls=[]
            def replacing(a,b):
                calls.append(1)
                if len(calls)<3:raise PermissionError('sharing violation')
                original(a,b)
            with patch.object(n.os,'replace',side_effect=replacing),patch.object(n.time,'sleep'):
                n.save(path,{'new':True})
            self.assertEqual(n.read(path),{'new':True});self.assertEqual(len(calls),3)

    def fixture(self,root):
        metadata=root/'LICENSE';metadata.write_text('fixture-license',encoding='utf-8')
        rows=[]
        for i in range(2):
            rows.append({'parent_id':f'p{i}','group_id':f'group{i}','split':'development' if i==0 else 'reserve',
                'dataset':'MUSAN','member_name':f'musan/music/fma/file{i}.wav','category':'instrumental_music',
                'category_evidence':'genre annotation','speech_content':'absent_documented',
                'speech_content_evidence':'vocals N','strict_nonspeech_eligible':True,'rights':{'status':'PERMITTED'},
                'attribution':'fixture artist','crop_policy':{'maximum_seconds':120},
                'metadata_bindings':[n.digest(metadata)]})
        n.save(root/'MUSAN_INDEX.json',{'status':'VERIFIED','members':[{'name':x['member_name']} for x in rows]})
        p=root/'selection.json';n.save(p,{'parents':rows});return p,rows

    def test_parent_freeze_precedes_quality_and_is_immutable(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(n,'STAGE',Path(tmp)):
            p,rows=self.fixture(Path(tmp));first=n.freeze_selection(p)
            self.assertFalse(first['waveform_qc_performed_before_freeze'])
            self.assertEqual(n.freeze_selection(p),first)
            rows[0]['split']='reserve';n.save(p,{'parents':rows})
            with self.assertRaisesRegex(ValueError,'overwritten'):n.freeze_selection(p)

    def test_unknown_speech_and_group_leak_cannot_be_promoted(self):
        for kind in ('speech','group','rights'):
            with tempfile.TemporaryDirectory() as tmp,patch.object(n,'STAGE',Path(tmp)):
                p,rows=self.fixture(Path(tmp))
                if kind=='speech':rows[0]['speech_content']='unknown'
                elif kind=='group':rows[1]['group_id']=rows[0]['group_id']
                else:rows[0]['rights']['status']='UNKNOWN'
                n.save(p,{'parents':rows})
                with self.assertRaises(ValueError):n.freeze_selection(p)
                self.assertFalse((Path(tmp)/'NOISE_SELECTION_FROZEN.json').exists())

    def test_declared_transfer_over_budget_is_refused_before_network(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(n,'STAGE',Path(tmp)),patch.object(n,'free_check'):
            book=n.ledger();book['new_response_body_bytes']=n.NETWORK_CAP-5
            n.save(Path(tmp)/'DOWNLOAD_LEDGER.json',book)
            with patch.object(n.urllib.request,'urlopen') as request:
                with self.assertRaisesRegex(RuntimeError,'16 GiB'):n.download('https://official.test/a',Path(tmp)/'a',expected_bytes=6)
                request.assert_not_called()

    def test_ignored_range_never_appends_duplicate_payload(self):
        class Response:
            status=200;url='https://official.test/a';headers={}
            def __enter__(self):return self
            def __exit__(self,*args):pass
        with tempfile.TemporaryDirectory() as tmp,patch.object(n,'STAGE',Path(tmp)),patch.object(n,'free_check'):
            target=Path(tmp)/'a';part=Path(tmp)/'a.part';part.write_bytes(b'abc')
            with patch.object(n.urllib.request,'urlopen',return_value=Response()):
                with self.assertRaisesRegex(RuntimeError,'exact resume'):n.download('https://official.test/a',target,expected_bytes=6,attempts=1)
            self.assertEqual(part.read_bytes(),b'abc');self.assertFalse(target.exists())

    def test_existing_archive_must_match_official_digest(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(n,'STAGE',Path(tmp)):
            target=Path(tmp)/'archive';target.write_bytes(b'changed')
            with patch.object(n.urllib.request,'urlopen') as request:
                with self.assertRaisesRegex(ValueError,'official MD5'):
                    n.download('https://official.test/a',target,expected_bytes=7,expected_md5='0'*32)
                request.assert_not_called()

    def test_transfer_deadline_and_completed_bytes_survive_phase_change(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(n,'STAGE',Path(tmp)):
            root=Path(tmp);book=n.ledger();book['active_transfer_wait_s']=100
            n.save(root/'DOWNLOAD_LEDGER.json',book)
            n.save(root/'status.json',{'updated_utc':'2026-09-09T03:00:00+00:00',
                                     'downloaded_bytes':1000,'MiB_per_s':1})
            active=n.transfer_time_status()
            self.assertEqual(active['active_transfer_wait_remaining_s'],5300)
            self.assertEqual(active['remaining_download_bytes'],n.MUSAN_BYTES-1000)
            self.assertEqual(active['conditional_active_budget_exhaustion_utc_if_continuous'],'2026-09-09T04:28:20+00:00')
            book['attempts']=[{'url':n.MUSAN_URL,'status':'COMPLETE',
                               'finished_utc':'2026-09-09T03:10:00+00:00'}]
            n.save(root/'DOWNLOAD_LEDGER.json',book);n.save(root/'MUSAN_ARCHIVE_RECEIPT.json',{})
            n.save(root/'status.json',{'phase':'noise_prepare','updated_utc':'2026-09-09T03:15:00+00:00'})
            complete=n.transfer_time_status()
            self.assertEqual(complete['transfer_status'],'COMPLETE')
            self.assertEqual(complete['downloaded_bytes'],n.MUSAN_BYTES)
            self.assertEqual(complete['remaining_download_bytes'],0)
            self.assertEqual(complete['estimated_remaining_download_s'],0)
            self.assertIsNone(complete['conditional_active_budget_exhaustion_utc_if_continuous'])

if __name__=='__main__':unittest.main(verbosity=2)
