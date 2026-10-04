"""Lossless bounded discovery decoding. README_PRODUCTION_SCOPE_V3.md."""
import base64
import hashlib
import json
from pathlib import Path
import unittest
import zlib

from prepare_production_scope_v3 import decode_discovery, strict_json


def envelope(value=None,raw=None):
    if raw is None:raw=json.dumps(value,sort_keys=True,separators=(',',':')).encode()
    return dict(schema='just-peachy.production-scope-transport.v1',encoding='zlib-base64',
        uncompressed_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
        payload=base64.b64encode(zlib.compress(raw,1)).decode())


def fixture():
    return dict(schema='just-peachy.production-scope-discovery.v2',
        roots=[dict(source='/home/peachyprototype/JustPeachy/data',destination='root-00')],
        members=[dict(root_index=0,relative='people/person.json',bytes=3)],total_files=1,total_bytes=3)


class TransportTests(unittest.TestCase):
    def test_actual_scope06_lossless_and_full_copy_classification(self):
        from prepare_production_scope_v2 import build_scope
        q=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
        transport=strict_json((q/'operation-production-scope-06/dispatch/RESULT.json').read_bytes())['action_result']
        self.assertEqual(transport['uncompressed_bytes'],221634)
        self.assertEqual(transport['sha256'],'2ae3d7ad0b4c598fe31def4d71cd7427fba2b124063e5a88bfe05cf33345b17e')
        decoded=decode_discovery(transport)
        self.assertEqual(len(decoded['roots']),26);self.assertEqual(len(decoded['members']),1932)
        self.assertEqual(sum(row['bytes'] for row in decoded['members']),657980201)
        assets=strict_json((q/'selected-assets-01.json').read_bytes())
        spec,summary=build_scope(decoded,assets,640*1024**2,1800)
        self.assertEqual(summary['observed_nonmodel_bytes'],657980201)
        self.assertEqual(spec['external_assets'],[])
        self.assertEqual(len(spec['historical_roots_preserved_outside_copy']),80)
        self.assertEqual(len(spec['absent_reserved_slots']),5)
        with self.assertRaises(ValueError):decode_discovery(decoded)

    def test_bounded_expansion_trailing_stream_and_hash_refused(self):
        good=envelope(fixture())
        for changed in (dict(good,uncompressed_bytes=1),dict(good,uncompressed_bytes=2*1024**2+1),dict(good,sha256='0'*64),
                        dict(good,payload=base64.b64encode(base64.b64decode(good['payload'])+zlib.compress(b'tail')).decode())):
            with self.assertRaises(ValueError):decode_discovery(changed)
        bomb=envelope(raw=b'x'*1000000);bomb['uncompressed_bytes']=10
        with self.assertRaises(ValueError):decode_discovery(bomb)

    def test_duplicate_json_and_member_traversal_refused(self):
        raw=b'{"schema":"a","schema":"just-peachy.production-scope-discovery.v2"}'
        with self.assertRaisesRegex(ValueError,'Duplicate'):decode_discovery(envelope(raw=raw))
        for relative in ('../outside','/absolute','a//b','a/./b','a\\b'):
            value=fixture();value['members'][0]['relative']=relative
            with self.assertRaises(ValueError):decode_discovery(envelope(value))
        value=fixture();value['members'][0]['root_index']=True
        with self.assertRaises(ValueError):decode_discovery(envelope(value))
        value=fixture();value['members'].append(dict(value['members'][0]));value.update(total_files=2,total_bytes=6)
        with self.assertRaisesRegex(ValueError,'Duplicate'):decode_discovery(envelope(value))


if __name__=='__main__':unittest.main()
