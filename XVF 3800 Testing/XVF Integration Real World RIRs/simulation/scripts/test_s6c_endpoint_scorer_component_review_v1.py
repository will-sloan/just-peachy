"""Independent endpoint scorer admission; README_TEST_S6C_ENDPOINT_SCORER_COMPONENT_REVIEW.md."""
import hashlib,json
from pathlib import Path
from unittest.mock import patch
import test_s6c_endpoint_scorer_admission as admission


def binding(p):
    p=Path(p).resolve();raw=p.read_bytes();return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def main():
    target=admission.core.REPORT/'independent_review/ENDPOINT_SCORER_ADMISSION_V1.json'
    original=target.read_bytes();b=binding(target)
    assert b['sha256']=='41572e2de03053022cd24f6ce90d01285462ed94e36af6e03f6b2d51bbfa35f6'
    value=json.loads(original)
    for source in value['sources']:assert binding(source['path'])==source
    captures=[]
    def capture(path,payload):
        assert Path(path).resolve()==target.resolve();captures.append(payload)
    with patch.object(admission.core,'save',capture):admission.run()
    assert len(captures)==1
    actual=captures[0]
    fields=('checks','core_fixtures','registered_labels','added_labels','registered_routes','registry','registry_sources','command_registry_arguments','sources')
    for field in fields:assert actual[field]==value[field]
    assert target.read_bytes()==original
    for source in value['sources']:assert binding(source['path'])==source
    result=dict(status='PASS_INDEPENDENT_MODEL_FREE_240_SCORER_ADMISSION',original_admission=b,
        reproduced_fields=list(fields),reproduced_guard_count=len(actual['checks']),original_core_fixtures=actual['core_fixtures'],
        registered_labels=240,registered_routes=388,source_bindings=actual['sources'],
        review_sources=[binding(__file__),binding(Path(__file__).with_name('README_TEST_S6C_ENDPOINT_SCORER_COMPONENT_REVIEW.md'))],
        findings=['Existing V3 append-only authority contract preserves all238 prior labels and admits only C195/C196.',
            'All four actual endpoint routes preserve exact parent numeric settings and no-gallery scope.',
            'Wrong counts/duplicate label/unknown parent/original-design mismatch/undigested setting mutation reject.',
            'Future scores use four explicit amendment bindings and expected240; previous scores retain their original identities.'],
        scope='Actual metadata/guard routine executed with only its final publication intercepted. No prediction scoring, model construction, hardware, or overwrite of held receipts/dependencies.')
    output=admission.core.REPORT/'independent_review/ENDPOINT_SCORER_COMPONENT_REVIEW_V1.json'
    with output.open('xb') as f:f.write((json.dumps(result,indent=2,allow_nan=False)+'\n').encode())
    print(json.dumps(binding(output)))


if __name__=='__main__':main()
