"""Authoritative accepted S4 capture selection; offline JSON/hash checks only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
import unittest

from s4_common import BANK, REPORT, bind, read

EXPECTED_IDS = [f'S4_{i:02}' for i in range(1, 25)]
SELECTION_PATH = REPORT / 'ACCEPTED_FINAL_CAPTURES.json'


def validate_ids(entries):
    ids = [row['case_id'] for row in entries]
    if len(ids) != 24 or len(set(ids)) != 24 or set(ids) != set(EXPECTED_IDS):
        raise ValueError('Accepted selection must contain exactly S4_01 through S4_24 once each')


def validate_entry(entry, scenes, recipe, hardware_root):
    cid, batch = entry['case_id'], entry['batch']
    path = Path(entry['case_result']['path']).resolve()
    expected = (Path(hardware_root) / batch / cid / 'case_result.json').resolve()
    if path != expected or not path.is_relative_to(Path(hardware_root).resolve()):
        raise ValueError('Accepted receipt path does not match its local batch/case identity')
    observed = bind(path, entry['case_result']['sha256'])
    receipt = read(path)
    if receipt.get('case_id') != cid or receipt.get('batch') != batch:
        raise ValueError('Accepted receipt case/batch identity mismatch')
    if not (receipt.get('status') == 'PASS' and receipt.get('audio_integrity_status') == 'PASS'
            and receipt.get('telemetry_status') == 'PASS' and receipt.get('final_recipe_capture') is True
            and receipt.get('recipe') == recipe and receipt.get('payload', {}).get('status') == 'PASS'
            and receipt.get('framing', {}).get('marker_error_count') == 0
            and not receipt.get('callback_errors')
            and receipt.get('input_scene_sha256') == scenes[cid]['canonical_audio']['sha256']):
        raise ValueError('Accepted capture does not satisfy final recipe, scene, audio and telemetry gates: ' + cid)
    return {'case_id': cid, 'batch': batch, 'folder': path.parent,
            'case_result': receipt, 'case_result_binding': observed}


def accepted_cases(partial=False):
    """Ordered dict cid -> {batch, folder:Path, case_result:dict, case_result_binding}."""
    manifest = read(BANK / 'SCENE_MANIFEST.json')
    scenes = {row['case_id']: row for row in manifest['scenes']}
    policy = read(REPORT / 'OUTPUT_LEVEL_POLICY.json')
    if not policy.get('frozen'):
        raise ValueError('Output policy is not frozen')
    if SELECTION_PATH.exists():
        selection = read(SELECTION_PATH)
        if selection.get('status') != 'PASS':
            raise ValueError('Authoritative accepted selection is not PASS')
        validate_ids(selection['cases'])
        entries = {row['case_id']: row for row in selection['cases']}
        return {cid: validate_entry(entries[cid], scenes, policy['hardware_recipe'], REPORT / 'hardware') for cid in EXPECTED_IDS}
    if not partial:
        raise FileNotFoundError('Authoritative ACCEPTED_FINAL_CAPTURES.json required; only explicit partial review permits original-final fallback')
    result = {}
    for cid in EXPECTED_IDS:
        path = REPORT / 'hardware/final' / cid / 'case_result.json'
        if not path.exists(): continue
        try:
            result[cid] = validate_entry({'case_id': cid, 'batch': 'final', 'case_result': bind(path)}, scenes, policy['hardware_recipe'], REPORT / 'hardware')
        except (ValueError, KeyError):
            # Partial review leaves a failed attempt unaccepted; consumers may
            # display its failure separately. Never promote it to a final pass.
            continue
    return result


def case_folder(case_id, partial=False):
    if case_id not in EXPECTED_IDS: raise ValueError('Unknown canonical S4 case: ' + case_id)
    selected = accepted_cases(partial=partial)
    if case_id in selected: return selected[case_id]['folder']
    if partial and not SELECTION_PATH.exists(): return REPORT / 'hardware/final' / case_id
    raise KeyError('No accepted final capture for ' + case_id)


class SelectionTests(unittest.TestCase):
    def test_exact_24_unique_identities(self):
        validate_ids([{'case_id': cid} for cid in EXPECTED_IDS])
        with self.assertRaises(ValueError): validate_ids([{'case_id': 'S4_01'}] * 24)
        with self.assertRaises(ValueError): validate_ids([{'case_id': cid} for cid in EXPECTED_IDS[:-1]])

    def test_bound_replacement_and_failed_telemetry(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); path = root / 'final_completion/S4_19/case_result.json'; path.parent.mkdir(parents=True)
            receipt = {'case_id': 'S4_19', 'batch': 'final_completion', 'status': 'PASS', 'audio_integrity_status': 'PASS',
                       'telemetry_status': 'PASS', 'final_recipe_capture': True, 'recipe': 'frozen', 'payload': {'status': 'PASS'},
                       'framing': {'marker_error_count': 0}, 'callback_errors': [], 'input_scene_sha256': 'scene'}
            path.write_text(json.dumps(receipt)); scenes = {'S4_19': {'canonical_audio': {'sha256': 'scene'}}}
            entry = {'case_id': 'S4_19', 'batch': 'final_completion', 'case_result': bind(path)}
            self.assertEqual(validate_entry(entry, scenes, 'frozen', root)['folder'], path.parent)
            receipt['telemetry_status'] = 'FAIL'; path.write_text(json.dumps(receipt))
            with self.assertRaises(ValueError): validate_entry(entry, scenes, 'frozen', root)
            entry['case_result'] = bind(path)
            with self.assertRaises(ValueError): validate_entry(entry, scenes, 'frozen', root)

    def test_different_folder_cannot_masquerade_as_original_batch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            entry = {'case_id': 'S4_01', 'batch': 'final', 'case_result': {'path': str(root / 'other.json'), 'sha256': 'x'}}
            with self.assertRaises(ValueError): validate_entry(entry, {}, 'frozen', root)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--partial', action='store_true'); parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SelectionTests))
        raise SystemExit(0 if result.wasSuccessful() else 1)
    selected = accepted_cases(partial=args.partial)
    print(json.dumps({'status': 'PARTIAL_REVIEW' if args.partial else 'VALIDATED_ACCEPTED_SELECTION', 'count': len(selected),
                      'cases': [{'case_id': cid, 'batch': row['batch'], 'folder': str(row['folder'])} for cid, row in selected.items()]}, indent=2))
