"""Model-free streaming frontend and RNNT state checks; README_A1_PORTABLE.md."""
import unittest
import numpy as np
from a1_onnx_v2 import FeatureBuffer,OnnxService


class FrontendTests(unittest.TestCase):
    def buffer(self):
        config=dict(sample_rate=16000,features=128,n_fft=512,hop_length=160,win_length=400,
            normalize='NA',pad_to=0,frame_splicing=1,log=True,log_zero_guard_type='add',
            log_zero_guard_value=2**-24,preemph=.97,mag_power=2.,exact_pad=False,use_grads=False)
        return FeatureBuffer(config,np.ones(400,np.float32),np.ones((128,257),np.float32))

    def test_zero_frontend_has_expected_initial_history_and_new_log_guard(self):
        f=self.buffer();actual=f.update(np.zeros(1280,np.float32))
        np.testing.assert_array_equal(actual[:,:17],np.full((128,17),-16.635,np.float32))
        np.testing.assert_allclose(actual[:,17:],np.log(np.float32(2**-24)),rtol=0,atol=1e-6)

    def test_reset_is_exact_and_returned_features_do_not_alias(self):
        f=self.buffer();audio=np.linspace(-.1,.1,1280,dtype=np.float32)
        first=f.update(audio);first[:]=0
        self.assertTrue(np.any(f.features!=0))
        f.reset();second=f.update(audio);f.reset()
        np.testing.assert_array_equal(second,f.update(audio))

    def test_wrong_length_and_nonfinite_audio_are_rejected(self):
        for value in (np.zeros(1279),np.full(1280,np.nan)):
            with self.assertRaises(ValueError):self.buffer().update(value)


class DecoderStateTests(unittest.TestCase):
    def service(self,tokens,frames=1):
        service=OnnxService.__new__(OnnxService)
        service.frontend=type('Frontend',(),dict(reset=lambda s:None,update=lambda s,a:np.zeros((128,25),np.float32)))()
        service.vocabulary=['']*1026;service.vocabulary[1]='\u2581one';service.vocabulary[2]='\u2581two'
        service.vocabulary[-2:]=['<EOU>','<EOB>'];service.blank=1026;service.audit=True;service.reset_state()
        class Encoder:
            def run(s,_,feed):
                return [np.zeros((1,512,frames),np.float32),np.array([frames],np.int64),
                    feed['cache_last_channel']+1,feed['cache_last_time']+1,feed['cache_last_channel_len']+1]
        class Decoder:
            def __init__(s):s.inputs=[];s.tokens=iter(tokens)
            def run(s,_,feed):
                s.inputs.append((int(feed['targets'][0,0]),float(feed['input_states_1'][0,0,0])))
                logits=np.full((1,1,1,1027),-50.,np.float32);logits[0,0,0,next(s.tokens)]=0
                return [logits,np.ones(1,np.int64),feed['input_states_1']+1,feed['input_states_2']+1]
        service.encoder=Encoder();service.decoder=Decoder();return service

    def test_blank_does_not_commit_prediction_state_or_last_token(self):
        s=self.service([1,1026,2,1026],frames=2);result=s.transcribe(bytes(2560))
        self.assertEqual(result.text,' one two')
        self.assertEqual(s.decoder.inputs,[(1026,0.),(1,1.),(1,1.),(2,2.)])
        self.assertEqual(float(s.hidden[0,0,0]),2.)

    def test_predicted_eou_resets_all_recurrent_state_after_recording(self):
        s=self.service([1024,1026]);result=s.transcribe(bytes(2560))
        self.assertTrue(result.is_final);self.assertEqual(result.text,'<EOU>')
        self.assertEqual(s.last_token,1026);self.assertFalse(np.any(s.hidden));self.assertFalse(np.any(s.channel))
        self.assertEqual(s.last_step['tokens'],[1024])

    def test_maximum_symbols_per_frame_matches_reference(self):
        s=self.service([1]*10);result=s.transcribe(bytes(2560))
        self.assertEqual(result.text.count('one'),10);self.assertEqual(float(s.hidden[0,0,0]),10.)


if __name__=='__main__':unittest.main(verbosity=2)
