"""S4.5 structural/level regression fixtures; README_S45_BANK.md."""
import copy, tempfile, unittest
from pathlib import Path
import numpy as np
import soundfile as sf
from s45_bank import *

def noise_fixture():
    return {'prepared_segments':[{'noise_id':f'{split}_{i}','parent_id':f'{split}_{i}','split':split,'category':'stationary_appliance_noise' if i%2 else 'instrumental_music','samples':640000,'speech_content':'absent_documented' if i%2==0 else 'unknown','strict_nonspeech_eligible':i%2==0} for split,n in [('development',24),('reserve',8)] for i in range(n)]}

class BankChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest=read(SOURCE_PATH);cls.rirs=load_rirs();cls.plan,cls.src,_,cls.sentinels=build_plan(cls.manifest,noise_fixture(),cls.rirs)
    def test_counts_and_protected_sentinels(self):
        self.assertEqual(len(self.plan),240);self.assertEqual(sum(s['split']=='development' for s in self.plan),180)
        self.assertEqual(len(self.sentinels),24)
        for s in self.plan:
            self.assertEqual(s['task_scoring_allowed'],s['split']=='development')
            labels=[x['utterance_label'] for x in s['segments'] if x['kind']=='utterance']
            self.assertEqual(len(labels),len(set(labels)))
            if s['case_id'] in self.sentinels:self.assertEqual(s['split'],'development')
    def test_source_roles_and_no_L2(self):
        people=set()
        for s in self.plan:
            for seg in s['segments']:
                if seg['kind']!='utterance':continue
                source=self.src[seg['source_id']]
                self.assertIn(source['dataset'],['CMU ARCTIC','Common Voice','HiFiTTS'])
                self.assertEqual(source['usage'],'probe');self.assertEqual(source['split'],s['source_partition'])
                self.assertEqual(seg['source_crop_samples'],[0,source['samples']]);self.assertTrue(seg['whole_clip'])
                if s['split']=='development':people.add(source['identity'])
        self.assertEqual(len(people),34)
    def test_receiver_pairs(self):
        grouped=collections.defaultdict(list)
        for s in self.plan:
            if s['matched_pair_id']:grouped[s['matched_pair_id']].append(s)
            for seg in s['segments']:self.assertEqual(group(self.rirs[seg['rir_id']]),tuple(s['receiver_configuration'][k] for k in GROUP_KEYS))
        for pair in grouped.values():
            self.assertEqual(len(pair),2);self.assertEqual(pair[0]['split'],pair[1]['split'])
            if pair[0]['family_id'] in ['F05','F07','F08']:
                for a,b in zip(pair[0]['segments'],pair[1]['segments']):
                    for key in ['source_id','source_start_sample','source_stop_sample','preparation_gain_scalar','relative_source_scalar']:self.assertEqual(a[key],b[key])
    def test_matched_level_triples(self):
        scenes=[s for s in self.plan if s['family_id']=='F01' and s['split']=='development']
        for at in range(0,15,3):
            trip=scenes[at:at+3]
            self.assertEqual([s['segments'][0]['relative_source_db'] for s in trip],[-6,0,6])
            for a,b,c in zip(*(s['segments'] for s in trip)):
                for k in ['source_id','source_start_sample','source_stop_sample','rir_id']:self.assertEqual(a[k],b[k]);self.assertEqual(b[k],c[k])
        scenes=[s for s in self.plan if s['family_id']=='F10' and s['split']=='development']
        for at in range(0,15,3):
            trip=scenes[at:at+3];self.assertEqual([s['noise_policy']['snr_db'] for s in trip],[20,10,0])
            self.assertEqual(trip[0]['segments'],trip[1]['segments']);self.assertEqual(trip[1]['segments'],trip[2]['segments'])
            self.assertTrue(all(x['category']=='stationary_appliance_noise' for x in trip[0]['segments'] if x['kind']=='real_noise'))
    def test_strict_controls_and_geometry_bounds(self):
        for s in self.plan:
            if s['family_id']=='F12':self.assertTrue(all(x.get('strict_nonspeech_eligible',True) for x in s['segments']))
            if s['family_id']=='F09':
                target=s['segments'][0];background=s['segments'][1]
                overlap=sum(max(0,min(b,d)-max(a,c)) for a,b in target['activity_ranges_samples_estimated'] for c,d in background['activity_ranges_samples_estimated'])
                self.assertGreater(overlap,0,'SIR requires scheduled active overlap before any hardware')
            for seg in s['segments']:
                rir=self.rirs[seg['rir_id']];self.assertNotEqual(rir['run_id'],EXCLUDED);self.assertLessEqual(coordinates(rir)[1],5)
                self.assertEqual(rir['geometry']['active_angle_label']['source_angle_manual_uncertainty_deg'],5)
    def test_noise_mic_domain_scalar_and_pair(self):
        with tempfile.TemporaryDirectory(prefix='s45_level_',dir=PAYLOAD) as folder:
            path=Path(folder);rng=np.random.default_rng(45)
            x=rng.normal(0,.05,32000);z=rng.normal(0,.05,64000)
            h=np.zeros((801,4));h[800]=[.5,.25,-.1,.4]
            sf.write(path/'speech.wav',x,FS,subtype='FLOAT');sf.write(path/'noise.wav',z,FS,subtype='FLOAT');sf.write(path/'rir.wav',h,FS,subtype='FLOAT')
            src={'s':{'decoded_16k_binding':bind(path/'speech.wav')}};noise={'n':{'prepared_path':str(path/'noise.wav'),'prepared_sha256':bind(path/'noise.wav')['sha256']}}
            rirs={'r':{'file':bind(path/'rir.wav')}}
            seg={'kind':'utterance','source_id':'s','source_crop_samples':[0,32000],'preparation_gain_scalar':1.,'relative_source_scalar':1.,'rir_id':'r','source_start_sample':16000,'activity_ranges_samples_estimated':[[16800,48800]],'role':'target_or_conversation'}
            ns={'kind':'real_noise','source_id':'n','source_crop_samples':[0,64000],'rir_id':'r','source_start_sample':0}
            scene={'duration_s':6,'segments':[seg,ns],'snr_reference_segments':[seg],'noise_policy':{'snr_db':10,'reference':'fixture'},'speech_interference_policy':None}
            mixed,detail,_=render_raw(scene,src,noise,rirs);self.assertAlmostEqual(detail['achieved_snr_db'],10,places=8)
            control=copy.deepcopy(scene);control['segments']=[ns]
            only,cdetail,_=render_raw(control,src,noise,rirs);self.assertEqual(detail['interferer_float64_sha256'],cdetail['interferer_float64_sha256'])
            self.assertTrue(np.allclose(only[:,1],only[:,0]*.5,atol=1e-8))
            self.assertTrue(np.allclose(only[:,2],only[:,0]*-.2,atol=1e-8))
            again,_,_=render_raw(scene,src,noise,rirs);self.assertTrue(np.array_equal(mixed,again))
            transient=copy.deepcopy(ns);transient['source_crop_samples']=[0,800]
            transient.update(source_start_sample=0,source_stop_sample=800,convolution_stop_sample=1600)
            short=copy.deepcopy(scene);short['segments']=[seg,transient]
            shortcontrol=copy.deepcopy(short);shortcontrol['segments']=[copy.deepcopy(transient)]
            place_short_transients([short,shortcontrol],src,noise,rirs)
            _,shortdetail,_=render_raw(short,src,noise,rirs)
            _,shortcdetail,_=render_raw(shortcontrol,src,noise,rirs)
            self.assertGreater(shortdetail['unscaled_noise_power_same_window'],0)
            self.assertAlmostEqual(shortdetail['achieved_snr_db'],10,places=8)
            self.assertEqual(shortdetail['interferer_float64_sha256'],shortcdetail['interferer_float64_sha256'])
            self.assertFalse(short['segments'][1]['transient_placement']['uses_device_or_model_output'])
            longtransient=copy.deepcopy(scene);longtransient['duration_s']=10;longtransient['segments'][1]['category']='transient_event_noise'
            place_short_transients([longtransient],src,noise,rirs)
            excerpt=longtransient['segments'][1];self.assertLessEqual(excerpt['source_crop_samples'][1]-excerpt['source_crop_samples'][0],2*FS)
            self.assertIn('noise_excerpt_selection',excerpt)
            _,ldetail,_=render_raw(longtransient,src,noise,rirs);self.assertAlmostEqual(ldetail['achieved_snr_db'],10,places=8)
            src['b']={'decoded_16k_binding':bind(path/'noise.wav')}
            bg=copy.deepcopy(seg);bg.update(source_id='b',role='background_talker')
            voice_scene={'duration_s':6,'segments':[seg,bg],'snr_reference_segments':[],'noise_policy':None,'speech_interference_policy':{'requested_sir_db':6,'reference':'fixture'}}
            _,no_noise,sir=render_raw(voice_scene,src,noise,rirs)
            self.assertIsNone(no_noise);self.assertAlmostEqual(sir['achieved_sir_db'],6,places=8)
    def test_reserved_source_not_used_in_development(self):
        for s in self.plan:
            if s['split']=='development':self.assertEqual(s['source_partition'],'development')
            if s['reserve_stratum'] in ['new_source_reserve','joint_reserve']:self.assertEqual(s['source_partition'],'downstream_reserve')
            if s['reserve_stratum'] in ['upper_loeb_acoustic_reserve','joint_reserve']:self.assertEqual(s['receiver_configuration']['room_table'],'Upper Loeb')

if __name__=='__main__':unittest.main(verbosity=2)
