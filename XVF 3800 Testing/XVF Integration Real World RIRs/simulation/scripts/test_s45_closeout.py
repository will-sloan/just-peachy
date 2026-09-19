"""Model-free closeout fixtures; see README_S45_CLOSEOUT_TESTS.md.

Only named function ASTs are loaded. All child processes, clocks and resource
checks are replaced by in-memory fixtures. Files stay in TemporaryDirectory.
"""
import ast
import base64
import contextlib
import copy
import datetime
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
import uuid


RUN_ID = '20260909T031300Z'
SCRIPTS = Path(__file__).parent


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding='utf-8')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def bind(path, expected=None):
    path = Path(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if expected is not None and digest != expected:
        raise ValueError('Fixture SHA256 mismatch: ' + str(path))
    return {'path': str(path), 'sha256': digest, 'bytes': path.stat().st_size}


def named_functions(name, selected, values):
    path = SCRIPTS / name
    tree = ast.parse(path.read_text(encoding='utf-8'))
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in selected]
    if {n.name for n in functions} != set(selected):
        raise AssertionError('Expected production helpers were not found')
    scope = types.ModuleType('fixture_' + name.replace('.', '_'))
    scope.__dict__.update(values)
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), 'exec'), scope.__dict__)
    return scope


class PackageGateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.report = self.root / 'report'
        self.bank = self.root / 'bank'
        self.sim = self.root / 'sim'
        self.report.mkdir(); self.bank.mkdir()
        (self.sim / 'scripts').mkdir(parents=True)
        self.counts = {'accepted': 240, 'canonical_analyzed': 240,
                       'H2_output_statuses': {'COMPLETE': 48}, 'H2_dry_statuses': {'COMPLETE': 24}}
        self.package = named_functions('s45_package.py', {'optional', 'verified_analysis_summary'},
            {'REPORT': self.report, 'BANK': self.bank, 'SIM': self.sim, 'RUN_ID': RUN_ID,
             'Path': Path, 'read': read, 'save': save, 'bind': bind})
        paths = [self.bank / 'SCENE_MANIFEST.json', self.report / 'ACCEPTED_CAPTURES.json',
                 self.report / 'CAPTURE_ANALYSIS.json', self.report / 'COVERAGE_SUMMARY.json',
                 self.report / 'SENTINEL_PLAN.json', self.report / 'DRY_CONTROL_PLAN.json',
                 self.report / 'h2/execution_contract.json']
        for path in paths:
            save(path, {'fixture': True, 'run_id': RUN_ID})
        table = self.report / 'per_scene_metrics.csv'
        table.write_text('case_id,split\nfixture,development\n', encoding='utf-8')
        code = self.sim / 'scripts/s45_results.py'
        code.write_text('# fixture aggregation\n', encoding='utf-8')
        self.good = {'schema': 'jp_s45_summary_v1', 'run_id': RUN_ID,
                     'status': 'COMPLETE_WITH_LIMITATIONS',
                     'actual': {'canonical_accepted': 240, 'audio_analyzed': 240,
                                'development_spatial_analyzed': 180,
                                'H2': {'output_native_complete': 48, 'dry_native_complete': 24}},
                     'reserve_task_metrics_read': False,
                     'consumed_json_bindings': [bind(path) for path in paths],
                     'per_scene_metrics_binding': bind(table), 'aggregation_code': bind(code)}

    def verify(self, value=None):
        save(self.report / 'summary_metrics.json', self.good if value is None else value)
        return self.package.verified_analysis_summary(self.counts)

    def test_complete_current_summary_passes_with_bound_receipt(self):
        result = self.verify()
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['summary']['sha256'], bind(self.report / 'summary_metrics.json')['sha256'])

    def test_missing_summary_cannot_complete(self):
        self.assertEqual(self.package.verified_analysis_summary(self.counts)['status'], 'PENDING_OR_STALE')

    def test_pending_partial_and_wrong_schema_cannot_complete(self):
        for key, value in [('status', 'PENDING_DETAILED_ANALYSIS'), ('status', 'PARTIAL_EVIDENCE'),
                           ('schema', 'jp_s45_summary_unknown')]:
            with self.subTest(key=key, value=value):
                bad = copy.deepcopy(self.good); bad[key] = value
                self.assertEqual(self.verify(bad)['status'], 'PENDING_OR_STALE')

    def test_stale_denominators_and_reserve_task_read_cannot_complete(self):
        for key in ['canonical_accepted', 'audio_analyzed', 'development_spatial_analyzed']:
            with self.subTest(key=key):
                bad = copy.deepcopy(self.good); bad['actual'][key] -= 1
                self.assertEqual(self.verify(bad)['status'], 'PENDING_OR_STALE')
        bad = copy.deepcopy(self.good); bad['reserve_task_metrics_read'] = True
        self.assertEqual(self.verify(bad)['status'], 'PENDING_OR_STALE')

    def test_wrong_consumed_table_and_code_hashes_cannot_complete(self):
        for kind in ['consumed_json_bindings', 'per_scene_metrics_binding', 'aggregation_code']:
            with self.subTest(kind=kind):
                bad = copy.deepcopy(self.good)
                binding = bad[kind][0] if isinstance(bad[kind], list) else bad[kind]
                binding['sha256'] = '0' * 64
                self.assertEqual(self.verify(bad)['status'], 'PENDING_OR_STALE')

    def test_missing_bound_artifact_and_empty_provenance_cannot_complete(self):
        bad = copy.deepcopy(self.good)
        bad['consumed_json_bindings'][0]['path'] = str(self.root / 'absent.json')
        self.assertEqual(self.verify(bad)['status'], 'PENDING_OR_STALE')
        bad['consumed_json_bindings'] = []
        self.assertEqual(self.verify(bad)['status'], 'PENDING_OR_STALE')

    def test_foreign_run_with_same_denominators_cannot_complete(self):
        bad = copy.deepcopy(self.good); bad['run_id'] = 'earlier_run_same_counts'
        self.assertEqual(self.verify(bad)['status'], 'PENDING_OR_STALE')

    def test_valid_foreign_paths_cannot_replace_current_artifacts(self):
        for kind in ['consumed_json_bindings', 'per_scene_metrics_binding', 'aggregation_code']:
            with self.subTest(kind=kind):
                bad = copy.deepcopy(self.good)
                original = bad[kind][0] if isinstance(bad[kind], list) else bad[kind]
                foreign = self.root / ('foreign_' + Path(original['path']).name)
                foreign.write_bytes(Path(original['path']).read_bytes())
                replacement = bind(foreign)
                if isinstance(bad[kind], list):
                    bad[kind][0] = replacement
                else:
                    bad[kind] = replacement
                self.assertEqual(self.verify(bad)['status'], 'PENDING_OR_STALE')

    def test_omitting_any_current_critical_input_cannot_complete(self):
        for index in range(len(self.good['consumed_json_bindings'])):
            with self.subTest(index=index):
                bad = copy.deepcopy(self.good)
                del bad['consumed_json_bindings'][index]
                self.assertEqual(self.verify(bad)['status'], 'PENDING_OR_STALE')

    def test_empty_or_malformed_summary_returns_checkpoint_status(self):
        for payload in ['', '{incomplete']:
            with self.subTest(payload=payload):
                (self.report / 'summary_metrics.json').write_text(payload, encoding='utf-8')
                self.assertEqual(self.package.verified_analysis_summary(self.counts)['status'], 'PENDING_OR_STALE')


class PlotArtifactTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.report = self.root / 'report'; self.plots = self.report / 'plots'; self.plots.mkdir(parents=True)
        self.sim = self.root / 'sim'; (self.sim / 'scripts').mkdir(parents=True)
        self.package = named_functions('s45_package.py',
            {'optional', 'verified_plot_artifacts', 'verified_findings', 'final_review_ready'},
            {'REPORT': self.report, 'SIM': self.sim, 'Path': Path, 'read': read, 'save': save, 'bind': bind})
        save(self.report / 'summary_metrics.json', {'schema': 'jp_s45_summary_v1', 'fixture': True})
        (self.sim / 'scripts/s45_results.py').write_text('# fixture plotting code\n', encoding='utf-8')
        (self.plots / 'plotted_data.csv').write_text('metric,value\nfixture,1\n', encoding='utf-8')
        self.png = self.plots / 'fixture.png'
        self.png.write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Zl1sAAAAASUVORK5CYII='))
        self.good = {'schema': 'jp_s45_figures_v1', 'figure_count': 1, 'maximum_figures': 4,
                     'figures': [{'file': 'fixture.png', 'title': 'Fixture only', 'binding': bind(self.png)}],
                     'plotted_data': bind(self.plots / 'plotted_data.csv'),
                     'summary_metrics': bind(self.report / 'summary_metrics.json'),
                     'plot_code': bind(self.sim / 'scripts/s45_results.py'), 'no_reserve_task_plots': True,
                     'visual_QA': 'PENDING_HUMAN_OR_TOOL_INSPECTION'}

    def verify(self, index=None):
        save(self.plots / 'FIGURE_INDEX.json', self.good if index is None else index)
        return self.package.verified_plot_artifacts()

    def findings(self):
        for name in ['ANALYSIS_FINDINGS.md', 'WORKBOOK_FINDINGS.md']:
            (self.report / name).write_text('Reviewed fixture findings.\n', encoding='utf-8')
        return self.package.verified_findings()

    def test_valid_current_index_returns_only_bound_artifacts(self):
        result = self.verify()
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['figure_count'], 1)
        self.assertEqual({Path(b['path']).name for b in result['files']}, {'fixture.png', 'plotted_data.csv', 'FIGURE_INDEX.json'})
        for binding in result['files']:
            bind(binding['path'], binding['sha256'])

    def test_pass_tool_inspection_and_both_findings_make_review_ready(self):
        good = copy.deepcopy(self.good); good['visual_QA'] = 'PASS_TOOL_INSPECTION'
        self.assertTrue(self.package.final_review_ready(self.verify(good), self.findings()))

    def test_missing_empty_malformed_or_wrong_schema_index_is_excluded(self):
        self.assertEqual(self.package.verified_plot_artifacts()['files'], [])
        for payload in ['', '{incomplete', '[]', '{"schema":"wrong"}']:
            with self.subTest(payload=payload):
                (self.plots / 'FIGURE_INDEX.json').write_text(payload, encoding='utf-8')
                result = self.package.verified_plot_artifacts()
                self.assertEqual(result['status'], 'PENDING_OR_STALE')
                self.assertEqual(result['files'], [])

    def test_stale_summary_code_and_numeric_csv_bindings_are_excluded(self):
        for key in ['summary_metrics', 'plot_code', 'plotted_data']:
            with self.subTest(key=key):
                bad = copy.deepcopy(self.good); bad[key]['sha256'] = '0' * 64
                self.assertEqual(self.verify(bad)['files'], [])

    def test_missing_or_tampered_png_is_excluded(self):
        self.png.write_bytes(b'changed PNG bytes')
        self.assertEqual(self.verify()['status'], 'PENDING_OR_STALE')
        self.png.unlink()
        self.assertEqual(self.verify()['files'], [])

    def test_valid_hash_at_foreign_path_or_traversal_name_is_excluded(self):
        for key in ['summary_metrics', 'plot_code', 'plotted_data', 'figure']:
            with self.subTest(key=key):
                bad = copy.deepcopy(self.good)
                binding = bad['figures'][0]['binding'] if key == 'figure' else bad[key]
                foreign = self.root / ('foreign_' + Path(binding['path']).name)
                foreign.write_bytes(Path(binding['path']).read_bytes())
                replacement = bind(foreign)
                if key == 'figure':
                    bad['figures'][0]['binding'] = replacement
                else:
                    bad[key] = replacement
                self.assertEqual(self.verify(bad)['files'], [])
        bad = copy.deepcopy(self.good); bad['figures'][0]['file'] = '../fixture.png'
        self.assertEqual(self.verify(bad)['files'], [])

    def test_duplicate_count_cap_and_reserve_guard_fail_closed(self):
        variants = []
        bad = copy.deepcopy(self.good); bad['figures'] *= 2; bad['figure_count'] = 2; variants.append(bad)
        for key, value in [('figure_count', 2), ('maximum_figures', 5), ('no_reserve_task_plots', False)]:
            bad = copy.deepcopy(self.good); bad[key] = value; variants.append(bad)
        bad = copy.deepcopy(self.good); bad['figures'] = []; bad['figure_count'] = 0; variants.append(bad)
        bad = copy.deepcopy(self.good); bad['figures'] *= 5; bad['figure_count'] = 5; variants.append(bad)
        for bad in variants:
            with self.subTest(index=bad):
                self.assertEqual(self.verify(bad)['files'], [])

    def test_unindexed_png_is_never_added_by_glob(self):
        extra = self.plots / 'old_unindexed.png'; extra.write_bytes(self.png.read_bytes())
        result = self.verify()
        self.assertEqual(result['status'], 'PASS')
        self.assertNotIn(str(extra), [b['path'] for b in result['files']])

    def test_missing_or_whitespace_findings_block_final_review(self):
        good = copy.deepcopy(self.good); good['visual_QA'] = 'PASS_TOOL_INSPECTION'
        plots = self.verify(good)
        self.assertFalse(self.package.final_review_ready(plots, self.package.verified_findings()))
        (self.report / 'ANALYSIS_FINDINGS.md').write_text('Reviewed findings.\n', encoding='utf-8')
        (self.report / 'WORKBOOK_FINDINGS.md').write_text(' \n\t', encoding='utf-8')
        findings = self.package.verified_findings()
        self.assertEqual(findings['status'], 'PENDING')
        self.assertEqual(findings['pending'][0]['file'], 'WORKBOOK_FINDINGS.md')
        self.assertFalse(self.package.final_review_ready(plots, findings))

    def test_pending_or_generic_QA_never_counts_as_tool_inspection(self):
        findings = self.findings()
        for qa in [None, 'PENDING_HUMAN_OR_TOOL_INSPECTION', 'PASS']:
            with self.subTest(qa=qa):
                index = copy.deepcopy(self.good); index['visual_QA'] = qa
                plots = self.verify(index)
                self.assertEqual(plots['status'], 'PASS')
                self.assertFalse(self.package.final_review_ready(plots, findings))
        self.assertFalse(self.package.final_review_ready({'status': 'PENDING_OR_STALE', 'visual_QA': 'PASS_TOOL_INSPECTION'}, findings))


class FakeChild:
    def __init__(self, polls=(0,), wait_timeout=False):
        self.pid = 424242
        self.polls = list(polls)
        self.returncode = None
        self.wait_timeout = wait_timeout
        self.wait_calls = []

    def poll(self):
        result = self.polls.pop(0) if self.polls else self.returncode
        if result is not None:
            self.returncode = result
        return result

    def wait(self, timeout):
        self.wait_calls.append(timeout)
        if self.wait_timeout:
            raise subprocess.TimeoutExpired('fixture-owned-child', timeout)
        self.returncode = 0
        return self.returncode


class SupervisorStepTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.report = self.root / 'report'; self.report.mkdir()
        self.sim = self.root / 'sim'; (self.sim / 'scripts').mkdir(parents=True)
        for name in ['fixture.py', 's45_package.py']:
            (self.sim / 'scripts' / name).write_text('# Not executed\n', encoding='utf-8')
        self.children = []
        self.calls = []
        self.launch = True
        self.spawn_error = None
        self.sleep_error = None

        def popen(command, **kwargs):
            self.calls.append({'argv': command, 'kwargs': kwargs})
            if self.spawn_error:
                raise self.spawn_error
            kwargs['stdout'].write('fixture child invocation ' + str(len(self.calls)) + '\n')
            return self.children.pop(0)

        def sleep(seconds):
            if self.sleep_error:
                raise self.sleep_error

        process_api = types.SimpleNamespace(Popen=popen, STDOUT=subprocess.STDOUT,
            CREATE_NO_WINDOW=0x08000000, TimeoutExpired=subprocess.TimeoutExpired)
        self.execute = named_functions('s45_execute_v2.py', {'step'},
            {'REPORT': self.report, 'SIM': self.sim, 'BASE_PYTHON': 'fixture-python',
             'Path': Path, 'datetime': datetime, 'uuid': uuid, 'json': json,
             'read': read, 'save': save, 'bind': bind, 'now': lambda: 'FIXTURE_UTC',
             'single_thread_env': lambda: {'FIXTURE_ONLY': '1'}, 'subprocess': process_api,
             'time': types.SimpleNamespace(monotonic=lambda: 1., sleep=sleep),
             'launch_allowed': lambda: self.launch, 'elapsed_s': lambda: 0.,
             'remaining_s': lambda: 100., 'storage': lambda: {'fixture': True}})

    def step(self, name='capture', script='fixture.py'):
        with contextlib.redirect_stdout(io.StringIO()):
            return self.execute.step(name, script)

    def invocation_receipts(self):
        return list((self.report / 'supervisor').glob('capture_*.json'))

    def test_repeated_stage_preserves_distinct_logs_and_receipts(self):
        self.children = [FakeChild(), FakeChild()]
        self.assertTrue(self.step())
        first = self.invocation_receipts()[0]
        first_bytes = first.read_bytes(); first_log = Path(read(first)['log']['path']).read_bytes()
        self.assertTrue(self.step())
        receipts = self.invocation_receipts()
        self.assertEqual(len(receipts), 2)
        self.assertEqual(len(list((self.report / 'supervisor').glob('capture_*.log'))), 2)
        self.assertEqual(first.read_bytes(), first_bytes)
        self.assertEqual(Path(read(first)['log']['path']).read_bytes(), first_log)
        pointer = read(self.report / 'supervisor/capture.json')['latest_invocation']
        self.assertNotEqual(pointer['path'], str(first))
        bind(pointer['path'], pointer['sha256'])
        self.assertIsNone(read(self.report / 'supervisor_process.json')['pid'])

    def test_nonzero_child_records_failure_and_closed_owner(self):
        self.children = [FakeChild((9,))]
        self.assertFalse(self.step())
        receipt = read(self.invocation_receipts()[0])
        self.assertEqual(receipt['status'], 'FAILED')
        self.assertEqual(receipt['exit_code'], 9)
        self.assertIsNone(read(self.report / 'supervisor_process.json')['pid'])

    def test_cutoff_requests_finite_stop_without_kill(self):
        child = FakeChild((None, 0)); self.children = [child]; self.launch = False
        self.assertTrue(self.step())
        self.assertIn('cutoff', read(self.report / 'STOP_REQUEST.json')['reason'])
        self.assertEqual(child.wait_calls, [])

    def test_exception_waits_only_owned_child_and_records_confirmed_exit(self):
        child = FakeChild((None, None)); self.children = [child]
        self.sleep_error = KeyboardInterrupt('fixture supervisor interrupted')
        with self.assertRaises(KeyboardInterrupt):
            self.step()
        self.assertEqual(child.wait_calls, [300])
        self.assertTrue((self.report / 'STOP_REQUEST.json').exists())
        self.assertFalse((self.report / 'UNRESOLVED_SUPERVISOR_CHILD.json').exists())
        self.assertIsNone(read(self.report / 'supervisor_process.json')['pid'])
        receipt = read(self.invocation_receipts()[0])
        self.assertIn(receipt['status'], ['FAILED', 'FAILED_OR_INTERRUPTED', 'INTERRUPTED'])
        self.assertIn('error', receipt)
        self.assertEqual(receipt['exit_code'], 0)
        self.assertEqual(receipt['owned_process_pid'], child.pid)
        self.assertIs(receipt['exit_confirmed'], True)

    def test_exception_timeout_marks_unresolved_and_blocks_other_stages(self):
        child = FakeChild((None, None), wait_timeout=True); self.children = [child]
        self.sleep_error = KeyboardInterrupt('fixture supervisor interrupted')
        with self.assertRaises(KeyboardInterrupt):
            self.step()
        marker = read(self.report / 'UNRESOLVED_SUPERVISOR_CHILD.json')
        self.assertEqual(marker['pid'], child.pid)
        self.assertIs(marker['requires_explicit_resolution'], True)
        self.assertEqual(read(self.report / 'supervisor_process.json')['status'], 'UNVERIFIED_ACTIVE_CHILD')
        with self.assertRaisesRegex(AssertionError, 'Unresolved'):
            self.step(name='results')
        self.assertEqual(len(self.calls), 1)
        self.children = [FakeChild()]; self.sleep_error = None
        self.assertTrue(self.step(name='package', script='s45_package.py'))
        self.assertEqual(read(self.report / 'UNRESOLVED_SUPERVISOR_CHILD.json'), marker)

    def test_failed_spawn_finalizes_receipt_without_claiming_child_started(self):
        self.spawn_error = OSError('fixture create-process failure')
        with self.assertRaises(OSError):
            self.step()
        receipt = read(self.invocation_receipts()[0])
        self.assertEqual(receipt['status'], 'FAILED_NO_CHILD')
        self.assertIn('error', receipt)
        self.assertIs(receipt['child_launched'], False)
        self.assertIsNone(receipt['owned_process_pid'])
        self.assertIsNone(receipt['exit_code'])
        self.assertIsNone(read(self.report / 'supervisor_process.json')['pid'])
        self.assertFalse((self.report / 'UNRESOLVED_SUPERVISOR_CHILD.json').exists())

    def test_initial_receipt_write_failure_has_no_child_and_is_recorded(self):
        calls = []
        def save_first_error(path, value):
            calls.append(str(path))
            if len(calls) == 1:
                raise OSError('fixture initial invocation status write failed')
            save(path, value)
        self.execute.save = save_first_error
        with self.assertRaisesRegex(OSError, 'initial invocation'):
            self.step()
        self.assertEqual(self.calls, [])
        receipt = read(self.invocation_receipts()[0])
        self.assertEqual(receipt['status'], 'FAILED_NO_CHILD')
        self.assertIn('initial invocation', receipt['error'])

    def test_first_pid_status_write_failure_still_cleans_up_launched_child(self):
        child = FakeChild((None,)); self.children = [child]
        failed = []
        def save_first_pid_error(path, value):
            if Path(path).name == 'supervisor_process.json' and not failed:
                failed.append(True)
                raise OSError('fixture initial PID status write failed')
            save(path, value)
        self.execute.save = save_first_pid_error
        with self.assertRaisesRegex(OSError, 'initial PID'):
            self.step()
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(child.wait_calls, [300])
        self.assertIsNone(read(self.report / 'supervisor_process.json')['pid'])
        receipt = read(self.invocation_receipts()[0])
        self.assertEqual(receipt['status'], 'FAILED')
        self.assertEqual(receipt['exit_code'], 0)
        self.assertIn('initial PID', receipt['error'])

    def test_monitor_exception_retains_already_confirmed_nonzero_exit(self):
        child = FakeChild((None, 7)); self.children = [child]
        self.sleep_error = RuntimeError('fixture monitor failure')
        with self.assertRaisesRegex(RuntimeError, 'monitor failure'):
            self.step()
        self.assertEqual(child.wait_calls, [])
        receipt = read(self.invocation_receipts()[0])
        self.assertEqual(receipt['exit_code'], 7)
        self.assertEqual(receipt['status'], 'FAILED')
        self.assertIsNone(read(self.report / 'supervisor_process.json')['pid'])

    def test_stop_request_write_failure_does_not_prevent_owned_child_wait(self):
        child = FakeChild((None, None)); self.children = [child]
        self.sleep_error = RuntimeError('fixture original monitor failure')
        def save_stop_error(path, value):
            if Path(path).name == 'STOP_REQUEST.json':
                raise OSError('fixture stop request write failed')
            save(path, value)
        self.execute.save = save_stop_error
        with self.assertRaisesRegex(RuntimeError, 'original monitor'):
            self.step()
        self.assertEqual(child.wait_calls, [300])
        receipt = read(self.invocation_receipts()[0])
        self.assertEqual(receipt['status'], 'FAILED')
        self.assertEqual(receipt['exit_code'], 0)
        self.assertTrue(any('stop request' in e['error'] for e in receipt['cleanup_errors']))

    def test_v1_reproductions_remain_bounded_and_frozen_main_is_unchanged(self):
        original = SCRIPTS / 's45_execute.py'
        self.assertEqual(bind(original)['sha256'], '8d25493541441fec6fa929ecb60b022773928b4365d5e5e9ddfd45a9090aab2a')
        bodies = []
        for path in [original, SCRIPTS / 's45_execute_v2.py']:
            tree = ast.parse(path.read_text(encoding='utf-8'))
            bodies.append(ast.dump(next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')))
        self.assertEqual(*bodies)
        values = {k: v for k, v in self.execute.__dict__.items() if not k.startswith('__')}
        self.execute = named_functions('s45_execute.py', {'step'}, values)
        child = FakeChild((None, None)); self.children = [child]
        self.sleep_error = KeyboardInterrupt('bounded historical reproduction')
        with self.assertRaises(KeyboardInterrupt):
            self.step()
        self.assertEqual(child.wait_calls, [300])
        self.assertEqual(read(self.report / 'supervisor_process.json')['pid'], child.pid)
        self.assertEqual(read(self.invocation_receipts()[0])['status'], 'STARTED')
        self.spawn_error = OSError('bounded historical Popen failure')
        with self.assertRaises(OSError):
            self.step()
        self.assertEqual(len(self.invocation_receipts()), 2)
        self.assertTrue(all(read(p)['status'] == 'STARTED' for p in self.invocation_receipts()))


if __name__ == '__main__':
    unittest.main(verbosity=2)
