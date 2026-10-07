"""Actual engine caption methods without model imports. See README_IDENTITY_MODES.md."""
import ast
from collections import OrderedDict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import time
import unittest


def caption_methods():
    tree = ast.parse(Path(__file__).with_name('installed_engine.py').read_bytes())
    owner = next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name == 'InstalledSession')
    methods = [deepcopy(n) for n in owner.body if isinstance(n,ast.FunctionDef) and
        n.name in ('_caption','_expire_late_captions','_projection_revision')]
    namespace = dict(deepcopy=deepcopy,hashlib=hashlib,json=json,time=time)
    exec(compile(ast.fix_missing_locations(ast.Module(body=methods,type_ignores=[])),
        '<candidate-engine-caption-methods>','exec'),namespace)
    return type('CaptionMethods',(),{name:namespace[name] for name in ('_caption','_expire_late_captions','_projection_revision')})


class Store:
    def __init__(self):
        self.partitions = {}
        self.atomic_calls, self.legacy_calls = [], []
        self.versions = {}
        self.source_anchors = {}

    def replace_caption_projection(self, session, parent, rows, *, projection_revision=None,
                                   projection_source_start_sample=None):
        if projection_revision == self.versions.get(parent) and rows != self.partitions.get(parent):
            raise ValueError('Same durable projection revision has changed payload')
        self.atomic_calls.append((parent,deepcopy(rows),projection_revision))
        self.partitions[parent] = deepcopy(rows)
        self.versions[parent] = projection_revision
        self.source_anchors[parent] = projection_source_start_sample

    def write_caption(self,*args):
        self.legacy_calls.append(args)

    def write_event(self,*args):
        pass


class EngineCaptionContracts(unittest.TestCase):
    def session(self):
        session = caption_methods()()
        session.text_preferences = session.late_labels = None
        session.gallery_people = []
        session.engine = SimpleNamespace(prototype_identity=None)
        session.binding = dict(installed_manifest_sha256='a'*64)
        session.selection = SimpleNamespace(input_source='saved',speaker_attribution='retained')
        session.application = dict(mode='anonymous_conversation')
        session.rows, session.caption_payloads = OrderedDict(), OrderedDict()
        session.projection_versions = OrderedDict()
        session.first_caption = session.first_speaker = None
        session.spool = SimpleNamespace(store=Store(),session_id='s',processed_samples=16000)
        session.notify=lambda row:None
        session.caption_projection=lambda row,*args:[dict(id='s/u/segment:'+str(index),
            raw_asr_text=word,label=row.get('label','Unknown'),identity_status='collecting',
            timing_kind='ASR_REVISION_WINDOW_NOT_PHONETIC_ALIGNMENT',track_id=row.get('track_id'))
            for index,word in enumerate(row['text'].split())]
        return session

    def row(self, text='one two',version=1):
        return dict(session_id='s',utterance_id='u',caption_key='s/u',source_start_sec=0.,source_end_sec=1.,
            text=text,display_text=text,label='Speaker 1',display_version=version,final=True)

    def test_full_parent_replacement_retires_child_and_preserves_honest_timing(self):
        session = self.session()
        projection = session.caption_projection
        session.caption_projection = lambda *args:[dict(part,source_start_sec=.8 if index==0 else None)
            for index,part in enumerate(projection(*args))]
        session._caption(self.row())
        self.assertEqual(session.spool.store.partitions['s/u'][0]['start_sample'],12800)
        self.assertEqual(session.spool.store.source_anchors['s/u'],0)
        session._caption(self.row('one',2))
        self.assertEqual(len(session.spool.store.partitions['s/u']),1)
        self.assertEqual(session.spool.store.atomic_calls[-1][2],2)
        self.assertEqual(session.spool.store.source_anchors['s/u'],0)
        self.assertEqual(session.spool.store.legacy_calls,[])
        self.assertEqual(session.spool.store.partitions['s/u'][0]['provenance']['timing_kind'],
            'ASR_REVISION_WINDOW_NOT_PHONETIC_ALIGNMENT')

    def test_initial_zero_view_counter_does_not_replace_positive_display_revision(self):
        session = self.session()
        session._caption(dict(self.row(),view_revision=0))
        self.assertEqual(session.spool.store.atomic_calls[0][2],1)

    def test_late_expiry_reprojects_canonical_partition_without_legacy_parent_write(self):
        session = self.session()
        session._caption(self.row())
        session.late_labels = SimpleNamespace(expire=lambda **kwargs:[dict(caption_key='s/u',label='Unknown',
            speaker='Unknown',provisional=False,attribution_status='expired_unknown',speaker_supported=False)])
        session._expire_late_captions(10.)
        self.assertEqual(len(session.spool.store.atomic_calls),2)
        self.assertEqual(session.spool.store.legacy_calls,[])
        self.assertEqual([r['text'] for r in session.spool.store.partitions['s/u']],['one','two'])
        self.assertEqual([r['speaker'] for r in session.spool.store.partitions['s/u']],['Unknown','Unknown'])
        self.assertEqual(session.spool.store.partitions['s/u'][0]['provenance']['attribution_status'],'expired_unknown')
        self.assertEqual(session.spool.store.versions['s/u'],2)
        session.late_labels = None
        session._caption(self.row('new words',2))
        self.assertEqual(session.spool.store.versions['s/u'],3)

    def test_older_producer_partition_is_ignored_after_policy_revision(self):
        session = self.session()
        session._caption(self.row('latest',2))
        session._caption(self.row('stale',1))
        self.assertEqual(session.spool.store.partitions['s/u'][0]['text'],'latest')
        self.assertEqual(session.caption_payloads['s/u']['text'],'latest')

    def test_supplied_recognizer_continuation_fields_are_preserved_without_word_changes(self):
        session = self.session()
        session.engine.loaded_parent_engine='pinned.RuntimeEngine'
        session.engine.asr_segment_row=lambda row:dict(row,recognition_segment_final=True,
            utterance_final=False,utterance_group_id='group1',endpoint_kind='resource',
            utterance_boundary_kind='native_pause',leading_text_joiner='')
        session._caption(self.row())
        parts = session.spool.store.partitions['s/u']
        self.assertEqual([p['text'] for p in parts],['one','two'])
        self.assertEqual([p['provenance']['ui_projection']['leading_text_joiner'] for p in parts],['',' '])
        self.assertEqual(parts[0]['provenance']['ui_projection']['utterance_group_id'],'group1')
        self.assertEqual(parts[0]['provenance']['ui_projection']['utterance_boundary_kind'],'native_pause')
        self.assertEqual(parts[0]['provenance']['engine'],'pinned.RuntimeEngine')
        self.assertFalse(parts[0]['provenance']['ui_projection']['utterance_final'])


if __name__ == '__main__':
    unittest.main()
