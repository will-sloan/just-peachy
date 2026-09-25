"""Prove the service override survives export configuration; README_A1_PORTABLE.md."""
from dataclasses import dataclass
from types import SimpleNamespace
import unittest
from a1_export_contract import configure_service_export


@dataclass
class Config:
    cache_drop_size:int=1
    valid_out_len:int=1
    left_context:int=70


class ContractTests(unittest.TestCase):
    def service(self,drift=False):
        class Encoder:
            streaming_cfg=Config()
            calls=[]
            def setup_streaming_params(s,chunk_size=None,shift_size=None):
                s.calls.append((chunk_size,shift_size))
                s.streaming_cfg=Config(0,2) if chunk_size is None else Config(1,1,71 if drift else 70)
        encoder=Encoder()
        model=SimpleNamespace(encoder=encoder,cfg=SimpleNamespace(encoder=SimpleNamespace(subsampling_factor=8)),
            set_export_config=lambda args:encoder.setup_streaming_params())
        return SimpleNamespace(asr_model=model,model_chunk_size=16,tokens_per_frame=1)

    def test_actual_service_override_is_reapplied_after_default_reset(self):
        s=self.service();before=configure_service_export(s)
        self.assertEqual(before,dict(cache_drop_size=1,valid_out_len=1,left_context=70))
        self.assertEqual(s.asr_model.encoder.calls,[(None,None),(2,1)])

    def test_unexpected_prior_geometry_is_rejected(self):
        s=self.service();s.asr_model.encoder.streaming_cfg=Config(0,2)
        with self.assertRaises(ValueError):configure_service_export(s)

    def test_any_other_streaming_change_is_rejected(self):
        with self.assertRaises(ValueError):configure_service_export(self.service(drift=True))


if __name__=='__main__':unittest.main(verbosity=2)
