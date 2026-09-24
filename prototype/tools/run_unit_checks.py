"""Run final focused software checks without speech inference/capture; see README."""
from collections import Counter
import argparse
from datetime import datetime, timezone
import hashlib
import gc
import io
import json
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT.parent), str(ROOT), str(ROOT / 'vendor')]


def bindings():
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ('app', 'vendor', 'config') for p in (ROOT / folder).rglob('*')
            if p.is_file() and '__pycache__' not in p.parts}


def cases(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from cases(item)
        else:
            yield item


class MainThreadCleanupResult(unittest.TextTestResult):
    def startTest(self,test):
        # Prior Tk tests leave cyclic widget/interpreter references after
        # destroy(). Collect them here before a later worker can trigger GC
        # on another thread (Tcl_AsyncDelete aborts the entire process).
        gc.collect()
        super().startTest(test)


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(errors='backslashreplace')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'tests/evidence',
                        help='Use a fresh directory to retain earlier verification receipts')
    args = parser.parse_args()
    before = bindings()
    suite = unittest.TestLoader().discover(str(ROOT / 'tests'), pattern='test_*.py')
    counts = Counter(case.__class__.__module__ for case in cases(suite))
    stream = io.StringIO()
    start = time.perf_counter()
    result = unittest.TextTestRunner(stream=stream, verbosity=2,resultclass=MainThreadCleanupResult).run(suite)
    evidence = args.output_dir
    evidence.mkdir(parents=True, exist_ok=True)
    log = evidence / 'FINAL_UNIT_CHECKS.txt'
    log.write_text(stream.getvalue(), encoding='utf-8')
    record = {'scope': 'Focused software contracts. Mock capture/control and synthetic text/vectors; no microphone or neural speech inference.',
        'utc': datetime.now(timezone.utc).isoformat(), 'tests': result.testsRun,
        'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped),
        'elapsed_sec': time.perf_counter() - start, 'modules': dict(counts),
        'source_unchanged': bindings() == before, 'source_bindings': before,
        'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'tests_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT / 'tests').glob('test_*.py'))},
        'full_log_path': str(log), 'full_log_sha256': hashlib.sha256(log.read_bytes()).hexdigest()}
    record['status'] = 'PASS' if result.wasSuccessful() and record['source_unchanged'] else 'FAIL'
    (evidence / 'FINAL_UNIT_CHECKS.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: record[key] for key in ('status', 'tests', 'failures', 'errors', 'skipped', 'elapsed_sec', 'modules')}))
    if not result.wasSuccessful():
        print(stream.getvalue())
    raise SystemExit(0 if record['status'] == 'PASS' else 1)
