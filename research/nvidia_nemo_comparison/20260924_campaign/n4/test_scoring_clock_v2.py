"""Artifact and qualification rejection tests. README_SCORING_CLOCK_V2.md."""
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from common import bind
import integrated_scoring_adapter as original
from integrated_scoring_adapter_v2 import LIMIT, convert, read_artifact, read_component_events
from scoring_bank_v2 import admit, validate_implementation


class ScoringClockTests(unittest.TestCase):
    def artifact(self, path, data):
        path.write_bytes(gzip.compress(data, mtime=0))
        return dict(compressed=bind(path), expanded_bytes=len(data),
                    expanded_sha256=hashlib.sha256(data).hexdigest())

    def test_full_64_mib_artifact_and_original_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=b'"'+b'x'*(LIMIT-2)+b'"'
            b=self.artifact(Path(tmp)/'full.gz', data)
            self.assertEqual(len(read_artifact(b)), LIMIT-2)
            with self.assertRaises(ValueError): original.read_artifact(b)

    def test_declared_bound_type_and_digest_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=self.artifact(Path(tmp)/'small.gz', b'{"valid":true}')
            self.assertEqual(read_artifact(b), {'valid':True})
            for size in (True, -1, LIMIT+1, 1.0, None, 0):
                with self.subTest(size=size), self.assertRaises(ValueError):
                    read_artifact(dict(b, expanded_bytes=size))
            with self.assertRaises(ValueError): read_artifact(dict(b, expanded_sha256='0'*64))
            wrong=deepcopy(b);wrong['compressed']['sha256']='0'*64
            with self.assertRaises(ValueError): read_artifact(wrong)

    def test_actual_expansion_over_cap_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=self.artifact(Path(tmp)/'oversize.gz', b'"'+b'x'*(LIMIT-1)+b'"')
            with self.assertRaises(ValueError): read_artifact(dict(b, expanded_bytes=LIMIT))

    def test_valid_binding_cannot_hide_bad_gzip_crc_or_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bad.gz';b=self.artifact(path,b'{}')
            payload=bytearray(path.read_bytes());payload[-8]^=1;path.write_bytes(payload)
            b['compressed']=bind(path)
            with self.assertRaises((OSError, EOFError)): read_artifact(b)
            b=self.artifact(path,b'not json')
            with self.assertRaises(ValueError): read_artifact(b)

    def fixture(self):
        code=[{'path':n,'sha256':'0'*64,'bytes':1} for n in
              ('integrated_bank_v2.py','integrated_bank_plan_v2.py','method_artifact_v2.py')]
        receipt={'path':'fixture-qualification','sha256':'1'*64,'bytes':1}
        return dict(code=code,qualification=[receipt]), dict(code=code,
            status='PASS_INTEGRATED_BANK_NATIVE_CLOCK_DERIVATIVE_ONLY',artifact_cap_bytes=LIMIT), receipt

    def test_only_exact_qualified_derivative_admitted(self):
        context, qualification, receipt=self.fixture()
        validate_implementation(context,qualification,receipt)
        for change in ('missing-code','missing-receipt','reordered','changed-code','old-status','wrong-cap','duplicates','entrypoint'):
            c,q=deepcopy(context),deepcopy(qualification)
            if change=='missing-code':c['code']=[]
            elif change=='missing-receipt':c['qualification']=[]
            elif change=='reordered':c['code'].reverse()
            elif change=='changed-code':c['code'][0]['sha256']='2'*64
            elif change=='old-status':q['status']='READY_FOR_REVIEW'
            elif change=='wrong-cap':q['artifact_cap_bytes']=32*1024**2
            elif change=='duplicates':c['code']+=c['code'][:1];q['code']=c['code']
            elif change=='entrypoint':c['code'][0]['path']='unqualified.py';q['code']=c['code']
            with self.subTest(change=change),self.assertRaises(ValueError):
                validate_implementation(c,q,receipt)

    def test_active_method_owner_rejected_before_any_scoring(self):
        with patch('scoring_bank_v2.bind',return_value={'path':'fixture'}), \
                patch('scoring_bank_v2.load',return_value={'owner':{'pid':1,'create_time':1.}}), \
                patch('scoring_bank_v2.exact_process',return_value=object()), \
                patch('scoring_bank_v2.verify') as verify:
            with self.assertRaisesRegex(ValueError,'still active'): admit(Path('fixture'))
            verify.assert_not_called()

    def test_original_conversion_and_component_reader_preserved(self):
        self.assertIs(convert, original.convert)
        self.assertIs(read_component_events, original.read_component_events)
        self.assertFalse(any(n=='torch' or n=='method_artifact_v2' or
            n.startswith(('edge_speech_pipeline','application_publication','component_d1_replay')) for n in sys.modules))


if __name__=='__main__': unittest.main()
