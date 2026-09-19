"""Bounded independent review; see README_TEST_S6C_ENDPOINT_AUDIT_REVIEW.md."""
from pathlib import Path
import ast
import hashlib
import importlib.util
import json

SIM = Path(__file__).resolve().parents[1]
REPORT = SIM / 'reports/S6C/20260910T123540Z'

def binding(path):
    raw = path.read_bytes()
    return dict(path=str(path.resolve()), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())

def run():
    receipt_path = REPORT / 'endpoint_factorial_v1/AUDIT_HELPER_CHECKS_V3.json'
    assert binding(receipt_path)['sha256'] == 'c1976c58417e1623956c27d915978aa30606ef1cf43d10bae87da8815ec5cfb0'
    receipt = json.loads(receipt_path.read_bytes())
    for key in ('source', 'readme', 'epoch'):
        assert binding(Path(receipt[key]['path'])) == receipt[key]
    source = Path(receipt['source']['path'])
    spec = importlib.util.spec_from_file_location('endpoint_audit_reviewed', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    pure = module.tests()
    epoch = json.loads(Path(receipt['epoch']['path']).read_bytes())
    cue = module.cue_source_tests(epoch)
    assert pure['checks'] == 19 and cue['checks'] == 6
    tree = ast.parse(source.read_bytes())
    functions = {n.name:n for n in tree.body if isinstance(n, ast.FunctionDef)}
    for name in ('prepare', 'run'):
        calls = [n for n in ast.walk(functions[name]) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'source_check']
        assert len(calls) == 1 and len(calls[0].args) == 7
    result = dict(status='PASS_BOUNDED_SOURCE_AND_MODEL_FREE_REVIEW',
        reviewed_source=receipt['source'], reviewed_readme=receipt['readme'], owner_checks=binding(receipt_path),
        reviewer_source=binding(Path(__file__)), reviewer_readme=binding(Path(__file__).with_name('README_TEST_S6C_ENDPOINT_AUDIT_REVIEW.md')),
        reproduced_pure_checks=25, canonical_input_callsite_checks=2,
        findings_resolved=['Tail counts reject bool, noninteger, negative and source-span inconsistency.', 'Both prepare and run validate the declared cue condition and exact canonical case/tap telemetry before use.'],
        scope='Independent source review and reproduction of 25 tiny fixtures plus two call-site assertions. No real audit plan, prediction, event log, audio or model was read. This admits the report helper, not any future empirical endpoint result.',
        limitations=['Native journal/model provenance remains transitive through bound completed receipts.', 'Reset-empty text, continuous backlog and phonetic loss causes remain explicitly unavailable.', 'Serialized overlap token alignment is diagnostic and does not replace inherited MIMO/cp scores.'])
    out = REPORT / 'independent_review/ENDPOINT_AUDIT_HELPER_REVIEW_V1.json'
    with out.open('xb') as f:
        f.write((json.dumps(result, indent=2)+'\n').encode())
    print(json.dumps(binding(out)))

if __name__ == '__main__':
    run()
