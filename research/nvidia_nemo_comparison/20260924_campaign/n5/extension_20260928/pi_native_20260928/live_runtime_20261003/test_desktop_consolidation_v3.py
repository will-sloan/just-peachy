"""Closed bounded archive readback only; README_DESKTOP_CONSOLIDATION_V3.md."""
import ast
import base64
import copy
from pathlib import Path
import unittest
import zlib

import desktop_consolidation_action_v2 as previous
import desktop_consolidation_action_v3 as action
import test_desktop_consolidation as fixture_module


def pack(value):
    raw=action.encoded(value)
    return dict(schema='just-peachy.desktop-archive-transport.v1',encoding='zlib-base64',
        uncompressed_bytes=len(raw),sha256=action.sha(raw),payload=base64.b64encode(zlib.compress(raw,1)).decode())


class ArchiveReadback(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture_module.DesktopConsolidationTests();self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.consolidate()
        self.archive=self.fixture.archive
        self.transport=action.archive_transport(self.archive)

    def test_exact_transaction_ast_and_complete46_file_roundtrip(self):
        def node(module,name):
            return ast.dump(next(n for n in ast.parse(Path(module.__file__).read_text()).body
                                 if getattr(n,'name',None)==name),include_attributes=False)
        for name in ('archive_shortcuts','restore_shortcuts'):
            self.assertEqual(node(action,name),node(previous,name))
        self.assertEqual(action.OWNED,previous.OWNED);self.assertEqual(action.STARTUP,previous.STARTUP)
        metadata,files=action.decode_archive(self.transport,str(self.archive))
        self.assertEqual(len(files),46)
        self.assertEqual(set(files),{p.relative_to(self.archive).as_posix() for p in self.archive.rglob('*') if p.is_file()})
        for name,raw in files.items():self.assertEqual(raw,(self.archive/name).read_bytes())
        self.assertEqual(metadata['bytes'],sum(map(len,files.values())))

    def test_missing_changed_traversal_and_trailing_transport_refused(self):
        value=action.strict(zlib.decompress(base64.b64decode(self.transport['payload'])))
        missing=copy.deepcopy(value);missing['files'].pop();missing['bytes']=sum(r['bytes'] for r in missing['files'])
        with self.assertRaises((ValueError,KeyError)):action.decode_archive(pack(missing),str(self.archive))
        changed=copy.deepcopy(value);row=next(r for r in changed['files'] if r['path'].startswith('before/'))
        row['base64']=base64.b64encode(b'changed').decode();row['bytes']=7;row['sha256']=action.sha(b'changed')
        changed['bytes']=sum(r['bytes'] for r in changed['files'])
        with self.assertRaisesRegex(ValueError,'Original shortcut'):action.decode_archive(pack(changed),str(self.archive))
        traversal=copy.deepcopy(value);traversal['files'][0]['path']='before\\..\\outside'
        with self.assertRaisesRegex(ValueError,'relative'):action.decode_archive(pack(traversal),str(self.archive))
        trailing=dict(self.transport,payload=base64.b64encode(base64.b64decode(self.transport['payload'])+b'extra').decode())
        with self.assertRaisesRegex(ValueError,'eof'):action.decode_archive(trailing,str(self.archive))

    def test_closed_outer_receipt_binds_exact_owner_and_transaction(self):
        value=action.strict(zlib.decompress(base64.b64decode(self.transport['payload'])))
        native='/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-desktop-consolidation-'+'a'*32
        value['archive']=native
        for row in value['files']:
            if row['path'] in ('PLAN.json','CONSOLIDATED.json'):
                body=action.strict(base64.b64decode(row['base64']));body['archive']=native
                raw=action.encoded(body);row.update(bytes=len(raw),sha256=action.sha(raw),base64=base64.b64encode(raw).decode())
        value['bytes']=sum(r['bytes'] for r in value['files'])
        owner=dict(pid=1,start_ticks=2,boot_id='synthetic')
        outer=dict(utility_owner=owner,action_result=dict(status='ONE_UNIFIED_SHORTCUT_NOT_STARTED',archive=native,
            autostart_changed=False,process_started=False,archive_readback=pack(value)))
        closure=dict(owner=owner,exact_pid_absent=True,natural_returncode=0)
        self.assertEqual(len(action.readback_payload(outer,closure,owner)[1]),46)
        with self.assertRaisesRegex(ValueError,'closure'):
            action.readback_payload(outer,dict(closure,natural_returncode=1),owner)


if __name__=='__main__':unittest.main()
