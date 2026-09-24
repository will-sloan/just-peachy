"""Guard and account for one frozen unittest module. See README_CHECK_SUITE.md."""
from __future__ import annotations
import faulthandler
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from .io_utils import atomic


def test_ids(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from test_ids(item)
        else:
            yield item.id()


class AccountedSuite(unittest.TestSuite):
    def __init__(self, suite, folder, census):
        super().__init__([suite]); self.folder = folder; self.census = census

    def run(self, result, debug=False):
        started = []; completed = []; outcomes = []
        original = {}
        for name in ('startTest', 'stopTest', 'addSuccess', 'addError', 'addFailure',
                     'addSkip', 'addExpectedFailure', 'addUnexpectedSuccess', 'addSubTest'):
            original[name] = getattr(result, name)

        def start(test):
            started.append(test.id()); return original['startTest'](test)

        def stop(test):
            completed.append(test.id()); return original['stopTest'](test)

        def outcome(name):
            def record(test, *args):
                item = dict(test_id=test.id(), outcome=name)
                if name == 'addSkip': item['reason'] = str(args[0])
                if name in ('addFailure', 'addError', 'addExpectedFailure'):
                    item['detail'] = result._exc_info_to_string(args[0], test)
                if name == 'addSubTest':
                    item['subtest_id'] = args[0].id()
                    item['successful'] = args[1] is None
                    if args[1] is not None:
                        item['detail'] = result._exc_info_to_string(args[1], args[0])
                outcomes.append(item)
                return original[name](test, *args)
            return record

        result.startTest = start; result.stopTest = stop
        for name in original:
            if name not in ('startTest', 'stopTest'): setattr(result, name, outcome(name))
        try:
            return super().run(result, debug)
        finally:
            receipt = dict(schema='n2-isolated-module-tests-v1', **self.census,
                started_test_ids=started, completed_test_ids=completed, outcomes=outcomes,
                tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                skipped=len(result.skipped), expected_failures=len(result.expectedFailures),
                unexpected_successes=len(result.unexpectedSuccesses), successful=result.wasSuccessful())
            atomic(self.folder/'CHILD_RESULT.json', receipt)
            for name, method in original.items(): setattr(result, name, method)


def load_tests(loader, tests, pattern):
    """The original private-desktop launcher calls this before target imports."""
    import psutil
    folder = Path(os.environ['N1_UI_RECEIPT_DIR']).resolve()
    source = Path(os.environ['N2_SUITE_SOURCE']).resolve(strict=True)
    module = os.environ['N2_SUITE_MODULE']; cpu = int(os.environ['N2_SUITE_CPU'])
    process = psutil.Process(); process.cpu_affinity([cpu])
    process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    if process.cpu_affinity() != [cpu]: raise RuntimeError('CPU ownership differs')
    if os.environ.get('N2_TEST_E1') != '1': raise RuntimeError('Actual saved E1 check was not enabled')
    if not module.startswith('prototype.tests.test') or '.' in module.removeprefix('prototype.tests.'):
        raise ValueError('Expected exactly one prototype test module')
    import prototype
    if not any(Path(p).resolve() == source for p in prototype.__path__):
        raise ValueError('The launcher imported another prototype source')
    # Legacy fixtures import sibling helpers as test_people/test_ui. Discovery
    # supplies this path; module isolation must retain the same import contract.
    sys.path.insert(0, str(source/'tests'))

    # Keep a native crash log open until process exit. No user desktop capture.
    global _native_log
    _native_log = (folder/'NATIVE_OUTPUT.log').open('ab', buffering=0)
    os.dup2(_native_log.fileno(), 1); os.dup2(_native_log.fileno(), 2)
    faulthandler.enable(_native_log, all_threads=True)

    def forbidden(*args, **kwargs):
        raise AssertionError('Physical audio access forbidden in N2 suite')
    import sounddevice
    names = ('query_devices', 'query_hostapis', 'InputStream', 'RawInputStream',
             'OutputStream', 'RawOutputStream', 'Stream', 'RawStream', 'play', 'rec',
             'playrec', 'check_input_settings', 'check_output_settings')
    for name in names: setattr(sounddevice, name, forbidden)
    for name in ('app.windows_audio', 'prototype.app.windows_audio'):
        target = importlib.import_module(name)
        target.endpoint_snapshot = lambda: dict(status='BLOCKED_BY_N2_TEST_HARNESS', default_render={}, capture_endpoints=[])
    # Actual child fixtures use this exact Python. External host/USB tools are
    # blocked; mocked subprocess calls continue to exercise their contracts.
    original_popen = subprocess.Popen
    class GuardedPopen(original_popen):
        def __init__(self, args, *positional, **kwargs):
            candidate = kwargs.get('executable') or (args[0] if isinstance(args, (list, tuple)) and args else '')
            if kwargs.get('shell') or not candidate or Path(candidate).resolve() != Path(sys.executable).resolve():
                raise AssertionError('External hardware/control process forbidden in N2 suite')
            super().__init__(args, *positional, **kwargs)
    subprocess.Popen = GuardedPopen
    atomic(folder/'hardware_guard.json', dict(schema='n2-suite-hardware-guard-v1',
        module=module, source=str(source), before_test_import=True,
        physical_audio_calls='disabled', audio_entry_points=list(names),
        endpoint_enumeration='disabled for both app import namespaces',
        external_non_python_processes='disabled', synthetic_hardware_fixtures='permitted',
        cpu_affinity=process.cpu_affinity(), priority=int(process.nice()),
        N2_TEST_E1=os.environ['N2_TEST_E1'], CUDA_VISIBLE_DEVICES=os.environ.get('CUDA_VISIBLE_DEVICES')))
    imported = importlib.import_module(module)
    expected_path = source/'tests'/(module.rsplit('.', 1)[1]+'.py')
    if Path(imported.__file__).resolve() != expected_path:
        raise ValueError('Target test module came from another source')
    suite = loader.loadTestsFromModule(imported)
    ids = list(test_ids(suite))
    census = dict(module=module, source=str(expected_path), planned_tests=len(ids),
                  planned_test_ids=ids, loader_errors=list(loader.errors))
    atomic(folder/'CENSUS.json', census)
    return AccountedSuite(suite, folder, census)
