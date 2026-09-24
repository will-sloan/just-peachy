"""Run selected model-free contracts against the installed release, not the worktree."""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import sys
import unittest

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--release',type=Path,required=True)
p.add_argument('--tests',type=Path,required=True)
p.add_argument('--harness',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();a.release=a.release.resolve();a.harness.mkdir(parents=True,exist_ok=False)
selected=['test_people.py','test_lifecycle.py','test_file_tap.py','test_enrollment_cleanup.py',
          'test_live_stop_ownership.py','test_live_pipeline_bridge.py','test_live_timing.py',
          'test_roster_policy.py','test_seats.py','test_motion.py','test_sessions.py',
          'test_text_assistance.py','test_paragraph_enrollment.py']
rows=[]
for name in selected:
    source=a.tests/name
    raw=source.read_text(encoding='utf-8')
    # Only the test's source-root expression changes. The assertions and fixtures
    # remain byte-identical; changed copies live outside the installed release.
    rebound=raw.replace('Path(__file__).resolve().parents[1]',f'Path({str(a.release)!r})')
    rebound=rebound.replace('from tests.test_people import','from test_people import').replace('from tests.test_enrollment_cleanup import','from test_enrollment_cleanup import')
    (a.harness/name).write_text(rebound,encoding='utf-8')
    rows.append(dict(name=name,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        rebound_sha256=hashlib.sha256(rebound.encode()).hexdigest(),
        path_expression_replacements=raw.count('Path(__file__).resolve().parents[1]')))
sys.path[:0]=[str(a.release),str(a.release/'vendor')]
suite=unittest.defaultTestLoader.discover(str(a.harness),pattern='test_*.py')
result=unittest.TextTestRunner(verbosity=2).run(suite)
bindings={}
for name in ['app.controller','app.people','app.pipeline','app.live_audio','app.enrollment_quality',
             'app.motion','app.seats','app.sessions','app.text_assistance','app.enrollment_progress']:
    module=importlib.import_module(name);path=Path(module.__file__).resolve()
    if a.release not in path.parents:raise RuntimeError(f'Test imported non-release source: {path}')
    bindings[name]=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
summary=dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests_run=result.testsRun,
    failures=[str(t) for t,_ in result.failures],errors=[str(t) for t,_ in result.errors],
    skipped=[str(t) for t,_ in result.skipped],source_test_bindings=rows,runtime_bindings=bindings,
    no_microphone=True,no_native_model_load=True,
    adaptation='Test source-root expressions rebound to installed release; two tests-package helper imports rebound to the external harness; assertions preserved.')
a.output.parent.mkdir(parents=True,exist_ok=True)
a.output.write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
raise SystemExit(0 if result.wasSuccessful() else 1)
