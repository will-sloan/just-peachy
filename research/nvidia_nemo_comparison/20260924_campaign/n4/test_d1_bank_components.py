"""D1 admission/cache/guard tests; no models. README_D1_COMPONENTS.md."""
from copy import deepcopy
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from d1_bank_components import component_key, resource_guard, verify_admission, ALLOCATION


class TestD1BankContract(unittest.TestCase):
    def setUp(self):
        self.job = dict(job_id='test_O0', audio_path='not-opened.wav', audio_sha256='a'*64,
            frames=16000, sample_rate_hz=16000, gain=1, reset_between_scenes=True, tap='O0')
        self.contract = dict(component_contract=dict(source='frozen', model='native', runtime='bound'))

    def test_key_invalidates_audio_model_state_and_profile(self):
        key = component_key(self.contract, self.job, 'E0', {'profile': 'nominal'})
        self.assertNotEqual(key, component_key(self.contract, self.job, 'E1', {'profile': 'nominal'}))
        for field, value in [('audio_sha256', 'b'*64), ('frames', 16001), ('tap', 'O1')]:
            job = dict(self.job, **{field:value})
            self.assertNotEqual(key, component_key(self.contract, job, 'E0', {'profile': 'nominal'}))
        other = deepcopy(self.contract)
        other['component_contract']['runtime'] = 'other'
        self.assertNotEqual(key, component_key(other, self.job, 'E0', {'profile': 'nominal'}))
        self.assertNotEqual(key, component_key(self.contract, self.job, 'E0', {'profile': 'sensitivity'}))

    def test_predictor_firewall_and_unknown_encoder(self):
        with self.assertRaises(ValueError): component_key(self.contract, dict(self.job, identity='oracle'), 'E0', {})
        with self.assertRaises(ValueError): component_key(self.contract, self.job, 'E2', {})

    def test_full_bank_is_not_admitted_by_smoke_checker(self):
        with patch('d1_bank_components.load', return_value=dict(component_contract={}, schema='n4-d1-components-v1', scope='FULL')):
            with self.assertRaisesRegex(ValueError, 'separate reviewed admission'): verify_admission(Path('not-opened'))

    def test_packaging_cutoff_and_disk_floor(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            with patch('d1_bank_components.load', return_value={'target_utc': '2000-01-01T00:00:00+00:00'}):
                with self.assertRaises(TimeoutError): resource_guard(root, root)
            with patch('d1_bank_components.load', return_value={'target_utc': '2100-01-01T00:00:00+00:00'}), patch(
                    'd1_bank_components.supervisor.disk_reserves', return_value=({}, ['G:'])):
                with self.assertRaisesRegex(RuntimeError, 'Disk reserve'): resource_guard(root, root)

    def test_allocation_reserves_one_whole_cell(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            with patch('d1_bank_components.load', return_value={'target_utc': '2100-01-01T00:00:00+00:00'}), patch(
                    'd1_bank_components.supervisor.disk_reserves', return_value=({}, [])), patch(
                    'd1_bank_components.ALLOCATION', 32*1024**2-1):
                with self.assertRaisesRegex(RuntimeError, 'allocation'): resource_guard(root, root)
            self.assertEqual(ALLOCATION, 2*1024**3)


if __name__ == '__main__': unittest.main()
