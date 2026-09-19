"""Model-free accepted capture and representative level contracts; README_S45.md."""
import copy, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import soundfile as sf
import s45_campaign as c

class CampaignChecks(unittest.TestCase):
    def fixture(self):
        scene={'canonical_audio':{'sha256':'input'},'split':'development'}
        row={'status':'PASS','audio_integrity_status':'PASS','telemetry_status':'PASS','final_recipe_capture':True,'recipe':'frozen','input_scene_sha256':'input','split':'development','payload':{'status':'PASS'},'reserve_task_scored':False,'code_key':'code'}
        contract={'scene_manifest_sha256':'manifest','code_key':'code','recipe':'frozen','final_recipe_capture':True}
        return row,scene,contract,'manifest',{'hardware_recipe':'frozen'}
    def test_wrong_contract_never_accepted(self):
        args=self.fixture();self.assertEqual(c.acceptance_errors(*args),[])
        for key,value in [('final_recipe_capture',False),('recipe','other'),('audio_integrity_status','FAIL'),('telemetry_status','FAIL'),('input_scene_sha256','other'),('split','reserve'),('code_key','other'),('reserve_task_scored',True)]:
            changed=copy.deepcopy(args);changed[0][key]=value
            self.assertTrue(c.acceptance_errors(*changed),key)
        changed=copy.deepcopy(args);changed[2]['scene_manifest_sha256']='other';self.assertIn('scene_manifest',c.acceptance_errors(*changed))
    def test_representative_o1_quarantine_does_not_tune_or_block_o0(self):
        with tempfile.TemporaryDirectory(prefix='s45_campaign_') as folder:
            root=Path(folder);rows=[]
            for cid in c.REPRESENTATIVES:
                p=root/cid;p.mkdir();sf.write(p/'O0.wav',np.zeros(16000),16000,subtype='PCM_24');sf.write(p/'O1.wav',np.ones(16000),16000,subtype='PCM_24')
                c.save(p/'case_result.json',{'output_audio':{n:c.bind(p/(n+'.wav')) for n in ['O0','O1']}})
                rows.append({'case_id':cid,'folder':str(p),'case_result':c.bind(p/'case_result.json')})
            c.save(root/'SCENE_MANIFEST.json',{'fixture':True});c.save(root/'OUTPUT_LEVEL_POLICY.json',{'fixture':True})
            with patch.object(c,'REPORT',root),patch.object(c,'BANK',root):
                self.assertTrue(c.representative_levels({'accepted':rows}))
                c.verify_representative_gate({'accepted':rows})
                result=c.read(root/'REPRESENTATIVE_LEVEL_CHECK.json');self.assertTrue(result['hardware_recipe_unchanged']);self.assertFalse(result['H2_executed'])
                self.assertTrue(all(r['streams']['O1']['gross_saturation'] for r in result['cases']))
                sf.write(root/c.REPRESENTATIVES[0]/'O0.wav',np.ones(16000),16000,subtype='PCM_24')
                with self.assertRaises(ValueError):c.representative_levels({'accepted':rows})
                p=root/c.REPRESENTATIVES[0];c.save(p/'case_result.json',{'output_audio':{n:c.bind(p/(n+'.wav')) for n in ['O0','O1']}});rows[0]['case_result']=c.bind(p/'case_result.json')
                with self.assertRaises(AssertionError):c.verify_representative_gate({'accepted':rows})
                self.assertFalse(c.representative_levels({'accepted':rows}))

if __name__=='__main__':unittest.main(verbosity=2)
