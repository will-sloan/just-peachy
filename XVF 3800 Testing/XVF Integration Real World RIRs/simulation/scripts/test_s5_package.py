"""Model-free S5 package boundary/provenance fixtures. README_S5.md."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import s5_package as package


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding='utf-8')


def audit_fixture():
    return {'mode': 'FULL_REQUIRE_TERMINAL', 'errors': [], 'ended_utc': '2026-09-09T15:03:08Z',
        'resources': {'status': 'PASS', 'sampled_model_tree_peak_rss_bytes': 512 * 2**20,
            'sampled_available_ram_min_bytes': 20 * 2**30, 'model_ram_samples': 47,
            'current_ram': {'available': 25 * 2**30},
            'new_storage': {'bounded_new_logical_bytes': 4 * 2**30},
            'ssd': {'volumes': [{'drive': d, 'free_bytes': free * 2**30,
                'mapping': [{'model': model, 'health_status': 'Healthy', 'operational_status': ['OK']}]} for
                d, free, model in [('C:', 123, 'OS SSD'), ('G:', 321, 'Payload SSD')]]}},
        'native_totals': {'fresh_s5': {'model_child_wall_s': 600, 'jobs': 312},
                          'reused_s45': {'model_child_wall_s': 90, 'jobs': 48}},
        'reserve_protection': {'status': 'VERIFIED_RECORDED_APPLICATION_GUARDS',
            'development_cases': 180, 'protected_reserve_cases': 60,
            'reserve_task_model_accesses': 0, 'reserve_task_performance_accesses': 0,
            'components': [], 'missing': []}}


class PackageTests(unittest.TestCase):
    def test_readable_prose_preserves_identifiers_paths_hashes_and_times(self):
        fixed = r'O0 O1 PCM24 PCM16 ReDimNet2 S45_12_15 C:\Just_Peachy_S5\20260909T130308Z 14:33:25 2,000 468b2b306f994937a7d02db611080d38c7a4bcc7dc89ce7dc73d93762380f546'
        self.assertEqual(package.readable_prose(fixed), fixed)
        self.assertEqual(package.readable_prose('CER8.76%;O0:36 errors; all4 rooms; 34IDs; at-6 dB'),
                         'CER 8.76%; O0: 36 errors; all 4 rooms; 34 IDs; at -6 dB')

    def test_partial_panel_refused_before_audit_or_decision_reads(self):
        with patch('s5_package.read', return_value={'status': 'PARTIAL_DIAGNOSTIC'}) as reader:
            with self.assertRaisesRegex(AssertionError, 'partial diagnostic'):
                package.report_data()
            self.assertEqual(reader.call_count, 1)

    def test_resources_use_audit_values_with_historical_and_snapshot_scope(self):
        text = package.resource_table(audit_fixture())
        for value in ('7200.00 s (2.00 h)', '512.00 MiB', '47 samples', '20.00 GiB', '25.00 GiB',
                      '4.00 GiB', '123.00 GiB free', '321.00 GiB free', '90.00 s / 48 jobs',
                      'outside S5 elapsed wall time', 'not a continuous absolute peak'):
            self.assertIn(value, text)

    def test_unqualified_resources_or_missing_ssd_are_not_reported_as_zero(self):
        for mutation in ('status', 'volume'):
            audit = audit_fixture()
            if mutation == 'status':
                audit['resources']['status'] = 'UNAVAILABLE'
            else:
                audit['resources']['ssd']['volumes'].pop()
            with self.assertRaises(AssertionError):
                package.resource_table(audit)

    def test_elapsed_rejects_missing_timezone_and_prestart_boundaries(self):
        for value in ('2026-09-09T15:03:08', '2026-09-09T12:03:08Z'):
            with self.assertRaises(AssertionError):
                package.elapsed_through(value)

    def test_level_table_distinguishes_zero_rms_and_missing_support(self):
        levels = {'per_scene_rms_dbfs': {'n': 2, 'median': -24, 'p10': -30, 'p90': -18}, 'zero_rms_scenes': 1}
        region = {'scenes': 4, 'scenes_with_nonempty_support': 3, 'support_samples': 32000,
                  'raw_levels': levels, 'adapter_pcm16_levels': copy.deepcopy(levels)}
        region['adapter_pcm16_levels']['per_scene_rms_dbfs']['median'] = -21
        text = package.region_level_table({'O0': {'regions': {'speech_active': region}}, 'O1': {'regions': {}}})
        for value in ('3/4', '2.00', '-24.00 [-30.00, -18.00]; n=2; zero RMS=1', '-21.00', 'unavailable'):
            self.assertIn(value, text)


class ReserveEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.report = self.root / 'report'
        self.bank = self.root / 'bank'
        self.scenes = [{'case_id': f'C{i:03}', 'split': 'development' if i < 180 else 'reserve',
                        'task_scoring_allowed': i < 180} for i in range(240)]
        self.allowed = [s['case_id'] for s in self.scenes[:180]]
        self.audit = audit_fixture()
        component = self.report / 'access' / 'runner.json'
        write_json(component, {'fixture': 'qualified execution receipt'})
        self.audit['reserve_protection']['components'] = [{'receipt': package.bind(component), 'component': 'runner'}]
        write_json(self.report / 'FINAL_AUDIT.json', self.audit)
        write_json(self.bank / 'SCENE_MANIFEST.json', {'scenes': self.scenes})
        for name in ('aggregate', 'package', 'figures'):
            write_json(self.report / 'access' / (name + '.json'), {'component': name,
                'allowed_development_cases': self.allowed, 'metadata_rows_parsed': 240,
                'permitted_operation_calls': {'development_only_fixture': 360},
                'denied_before_open': [], 'reserve_task_accesses': 0})
        for target, value in [('REPORT', self.report), ('BANK', self.bank)]:
            p = patch.object(package, target, value); p.start(); self.addCleanup(p.stop)
        p = patch.object(package, 'manifest', return_value={'scenes': self.scenes})
        p.start(); self.addCleanup(p.stop)

    def change(self, name, key, value):
        path = self.report / 'access' / (name + '.json')
        data = json.loads(path.read_text(encoding='utf-8')); data[key] = value
        write_json(path, data)

    def test_exports_zero_task_access_separately_from_240_metadata_rows(self):
        self.change('package', 'denied_before_open', [{'case_id': 'C180', 'operation': 'blocked_fixture'}])
        result = package.export_reserve_protection(self.audit)
        self.assertEqual(result['reserve_task_performance_accesses'], 0)
        self.assertTrue(result['reserve_metadata_parsing_allowed'])
        self.assertEqual([r['metadata_rows_parsed'] for r in result['reporting_components']], [240, 240, 240])
        self.assertEqual(len(result['reporting_components'][1]['denied_before_open']), 1)
        self.assertEqual(result['final_audit'], package.bind(self.report / 'FINAL_AUDIT.json'))
        self.assertTrue((self.report / 'RESERVE_PROTECTION.json').exists())

    def test_missing_guard_is_not_assumed_zero(self):
        (self.report / 'access' / 'aggregate.json').unlink()
        with self.assertRaises(FileNotFoundError):
            package.export_reserve_protection(self.audit)
        self.assertFalse((self.report / 'RESERVE_PROTECTION.json').exists())

    def test_nonzero_reporting_or_execution_access_rejected(self):
        self.change('package', 'reserve_task_accesses', 1)
        with self.assertRaises(AssertionError):
            package.export_reserve_protection(self.audit)
        self.change('package', 'reserve_task_accesses', 0)
        self.audit['reserve_protection']['reserve_task_model_accesses'] = 1
        with self.assertRaises(AssertionError):
            package.export_reserve_protection(self.audit)

    def test_reserve_case_substituted_into_allowlist_rejected(self):
        self.change('aggregate', 'allowed_development_cases', self.allowed[:-1] + ['C180'])
        with self.assertRaises(AssertionError):
            package.export_reserve_protection(self.audit)

    def test_changed_execution_guard_or_partial_audit_rejected(self):
        write_json(self.report / 'access' / 'runner.json', {'fixture': 'changed after audit'})
        with self.assertRaisesRegex(AssertionError, 'binding changed'):
            package.export_reserve_protection(self.audit)
        self.audit['mode'] = 'PARTIAL_METADATA_ONLY'
        with self.assertRaisesRegex(AssertionError, 'full native audit'):
            package.export_reserve_protection(self.audit)


class FigureEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.report = self.root / 'report'
        self.figures = self.report / 'figures'; self.figures.mkdir(parents=True)
        self.sim = self.root / 'sim'; (self.sim / 'scripts').mkdir(parents=True)
        code = self.sim / 'scripts' / 's5_figures.py'; code.write_text('# fixture\n', encoding='utf-8')
        names = [f'{i:02}_fixture.png' for i in range(1, 5)]
        for name in names:
            (self.figures / name).write_bytes(b'fixture PNG bytes, not a rendered scientific image')
        (self.figures / 'plotdata.csv').write_text('name,value\nfixture,1\n', encoding='utf-8')
        (self.figures / 'CAPTIONS.md').write_text('\n\n'.join(f'**{name}**\n\nFixture caption {name}.' for name in names), encoding='utf-8')
        inputs = []
        for name in ('SUMMARY_METRICS.json', 'PAIRED_METRICS.json', 'SHORT_TURN_SUMMARY.csv',
                     'SCORING_PROTOCOL.json', 'JOB_MANIFEST.json', 'representation/SUMMARY_COMPACT.json'):
            path = self.report / name; write_json(path, {'fixture': name}); inputs.append(package.bind(path))
        self.receipt = {'schema': 'jp_s5_figures_v1', 'status': 'FINAL_COMPLETE_PANEL_FIGURES',
            'figure_count': 4, 'figures': [package.bind(self.figures / n) for n in names],
            'plotdata': package.bind(self.figures / 'plotdata.csv'),
            'captions': package.bind(self.figures / 'CAPTIONS.md'), 'code': package.bind(code),
            'input_bindings': inputs, 'layout_warnings': [], 'reserve_task_audio_or_native_logs_opened': 0}
        self.save()
        for target, value in [('REPORT', self.report), ('SIM', self.sim)]:
            p = patch.object(package, target, value); p.start(); self.addCleanup(p.stop)

    def save(self):
        write_json(self.figures / 'FIGURE_RECEIPT.json', self.receipt)

    def test_four_current_bound_images_have_portable_embeds_and_captions(self):
        result = package.figure_bundle()
        self.assertEqual(result.count('!['), 4)
        self.assertEqual(result.count('(figures/'), 4)
        self.assertEqual(result.count('Fixture caption'), 4)

    def test_preview_and_layout_warning_refused(self):
        self.receipt['status'] = 'SYNTHETIC_PREVIEW_ONLY'; self.save()
        with self.assertRaises(AssertionError):
            package.figure_bundle()
        self.receipt['status'] = 'FINAL_COMPLETE_PANEL_FIGURES'
        self.receipt['layout_warnings'] = ['clipped label']; self.save()
        with self.assertRaises(AssertionError):
            package.figure_bundle()

    def test_three_or_five_figures_refused(self):
        self.receipt['figures'].pop(); self.save()
        with self.assertRaises(AssertionError):
            package.figure_bundle()
        self.receipt['figures'].append(package.bind(self.figures / '04_fixture.png')); self.save()
        (self.figures / '05_unreceipted.png').write_bytes(b'extra')
        with self.assertRaises(AssertionError):
            package.figure_bundle()

    def test_missing_plotdata_refused(self):
        (self.figures / 'plotdata.csv').unlink()
        with self.assertRaises(FileNotFoundError):
            package.figure_bundle()

    def test_changed_panel_or_figure_bytes_refused(self):
        write_json(self.report / 'SUMMARY_METRICS.json', {'fixture': 'new final values'})
        with self.assertRaisesRegex(AssertionError, 'binding changed'):
            package.figure_bundle()
        self.receipt['input_bindings'][0] = package.bind(self.report / 'SUMMARY_METRICS.json'); self.save()
        (self.figures / '01_fixture.png').write_bytes(b'changed image')
        with self.assertRaisesRegex(AssertionError, 'binding changed'):
            package.figure_bundle()

    def test_missing_caption_or_substituted_input_refused(self):
        captions = self.figures / 'CAPTIONS.md'
        captions.write_text('**01_fixture.png**\n\nOnly one caption', encoding='utf-8')
        self.receipt['captions'] = package.bind(captions); self.save()
        with self.assertRaisesRegex(AssertionError, 'Caption required'):
            package.figure_bundle()
        extra = self.report / 'substitute.json'; write_json(extra, {'fixture': 'substituted panel'})
        self.receipt['input_bindings'][0] = package.bind(extra); self.save()
        with self.assertRaisesRegex(AssertionError, 'current numeric panel'):
            package.figure_bundle()


class ShallowIndexTests(unittest.TestCase):
    def test_receipts_indexed_without_environment_or_deep_tree_walk(self):
        with tempfile.TemporaryDirectory() as tmp:
            sim = Path(tmp)
            root = sim / 'staging' / 's5_fixture'
            keep = [root / 'DEPENDENCY_RECEIPT.json', root / 'TEST_OUTPUT.txt',
                    root / 'v1_resources' / 'TEST_RECEIPT.json']
            skip = [root / 'analysis_env' / 'TEST_RECEIPT.json', root / 'model.onnx',
                    root / 'v1_resources' / 'deep' / 'TEST_RECEIPT.json']
            for p in keep + skip:
                p.parent.mkdir(parents=True, exist_ok=True); p.write_text('fixture', encoding='utf-8')
            with patch.object(package, 'SIM', sim):
                result = package.component_test_bindings()
            self.assertEqual({Path(b['path']) for b in result}, {p.resolve() for p in keep})


if __name__ == '__main__':
    unittest.main()
