"""Model-free planner/CLI integration fixtures. See README_S6D_APPLICATION_BEAM_PLAN.md."""
from dataclasses import asdict,replace
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from s6d_application_beam_plan import prepare,REPO,SIM,binding
from edge_speech_pipeline.checks_research_beams_s6d import fixture_capture,save,calibrated
from edge_speech_pipeline.research_beams_s6d import BeamSettings
from edge_speech_pipeline.research_profiles import ResearchProfile
from edge_speech_pipeline.research_s6d import S6DSettings


class PlannerChecks(unittest.TestCase):
    def fixture(self,root):
        admission,data=fixture_capture(root)
        data['calibration_partition']=save(root/'partition.json',{'fixture_only':True,'schema_version':'edge-s6d-beam-calibration-partition.v1',
            'partition':'C','Q_used':False,'disjoint_from_E_Q_verified':True,'accepted_case_results':[data['case_result']]})
        save(admission,data)
        pilot=json.loads((SIM/'reports/S6D/20260913T195357Z/application/native_pilot_v3/MANIFEST.json').read_text())
        original=next(r for r in pilot['jobs'] if r['candidate']=='C088')
        settings=BeamSettings(mode='calibration_collection')
        return {'job_id':'C_fixture','control_group':'fixture_C','role':'calibration_collection','admission':binding(admission),
            'beam_settings':save(root/'BEAM.json',asdict(settings)),'research_profile':original['profile_binding'],
            'research_gallery':original['gallery'],'s6d_settings':save(root/'S6D.json',asdict(S6DSettings()))}

    def request(self,root,jobs):
        path=root/'REQUEST.json';save(path,{'schema':'s6d-beam-native-request.v1','jobs':jobs,'declared_job_limit':len(jobs),'purpose':'MODEL_FREE_SYNTHETIC_FIXTURE_ONLY'})
        return path

    def test_C_plan_and_actual_cli_check_only_never_start_session(self):
        with tempfile.TemporaryDirectory(prefix='s6d-C-plan-fixture-',dir='G:\\') as tmp:
            root=Path(tmp);row=self.fixture(root)
            result=prepare(self.request(root,[row]),root/'plan',root/'payload')
            self.assertEqual(result['job_count'],1);self.assertEqual(result['unique_physical_capture_results'],1)
            self.assertFalse((root/'payload').exists())
            env=dict(os.environ,**result['environment'])
            run=subprocess.run(result['jobs'][0]['model_free_admission_argv'],cwd=result['source_root'],env=env,text=True,capture_output=True,timeout=30)
            self.assertEqual(run.returncode,0,run.stderr)
            status=json.loads(run.stdout);self.assertEqual(status['status'],'INPUTS_VALIDATED_NO_MODELS');self.assertFalse(status['native_tested'])
            self.assertFalse((root/'payload').exists())

    def test_uncalibrated_evaluation_cannot_be_mislabeled_family_failure(self):
        with tempfile.TemporaryDirectory(prefix='s6d-eval-plan-fixture-',dir='G:\\') as tmp:
            root=Path(tmp);row=self.fixture(root)
            row['role']='mono_asr_beam_identity';row['beam_settings']=save(root/'BEAM.json',asdict(BeamSettings()))
            with self.assertRaisesRegex(ValueError,'uncalibrated nominal selector'):prepare(self.request(root,[row]),root/'plan',root/'payload')
            self.assertFalse((root/'plan').exists())

    def test_evaluation_control_requires_same_S6D_delivery_policy(self):
        with tempfile.TemporaryDirectory(prefix='s6d-pair-plan-fixture-',dir='G:\\') as tmp:
            root=Path(tmp);row=self.fixture(root);profile=ResearchProfile.load(row['research_profile']['path'])
            proof=save(root/'C_PROOF.json',{'fixture_only':True,'partition':'C','Q_used':False,'disjoint_from_E_Q_verified':True})
            c=save(root/'CALIBRATION.json',{'fixture_only':True,'schema_version':'edge-s6d-beam-calibration.v1','status':'ACCEPTED_C_ONLY',
                'gallery':row['research_gallery'],'calibration_evidence':proof,'identity_streams':['focus0_asr','focus1_asr'],
                'selected_profile_ids':[],'profile_sha256':profile.digest(),'capture_profile':'P_MAIN6',**calibrated(BeamSettings()).calibration})
            row['role']='mono_asr_beam_identity';row['beam_settings']=save(root/'VARIANT.json',asdict(BeamSettings(calibration=c)))
            control=dict(row,job_id='auto_control',role='same_pass_auto_control',beam_settings=save(root/'CONTROL.json',asdict(BeamSettings(mode='same_pass_auto_control',identity_streams=('auto_asr',)))))
            row['s6d_settings']=save(root/'CHANGED_S6D.json',asdict(replace(S6DSettings(),boundary_repair=False)))
            with self.assertRaisesRegex(ValueError,'Unmatched s6d_settings'):prepare(self.request(root,[control,row]),root/'plan',root/'payload')
            self.assertFalse((root/'plan').exists())


if __name__=='__main__':unittest.main(verbosity=2)
