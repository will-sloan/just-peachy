"""No native/Tk execution. README_RUNTIME_UI and README_NATIVE_VARIANT."""
import json
from pathlib import PurePosixPath
from types import SimpleNamespace
import unittest
from unittest import mock
import native_variant as variant
import runtime_ui_channel as channel
from launcher import selection_control_states
from native_gui_driver import validate_plan


class ReviewFixTests(unittest.TestCase):
    def test_fresh_loader_refuses_search_overrides_and_existing_native_mapping(self):
        for key in ('LD_PRELOAD','LD_LIBRARY_PATH'):
            with mock.patch.dict(variant.os.environ,{key:'not-admitted'},clear=True):
                with self.assertRaises(ValueError):variant.require_fresh_variant_loader()
        with mock.patch.dict(variant.os.environ,{},clear=True),mock.patch.object(variant,'_process_maps',return_value='1-2 r-xp 0 08:01 7 /isolated/libggml.so.0\n'):
            with self.assertRaises(ValueError):variant.require_fresh_variant_loader()
        with mock.patch.dict(variant.os.environ,{},clear=True),mock.patch.object(variant,'_process_maps',return_value='1-2 r-xp 0 08:01 7 /system/libc.so.6\n'):
            variant.require_fresh_variant_loader()
        with self.assertRaises(ValueError):variant._native_mappings('1-2 r-xp 0 08:01 7 /isolated/libggml.so.0 (deleted)')

    def test_actual_mapping_requires_exact_inventory_hash_inode_and_complete_libraries(self):
        names=('libnemo_speech_asr_c.so.1','libnemo_speech_asr.so','libggml.so.0','libggml-base.so.0','libggml-cpu.so.0')
        rows=[dict(path='/isolated/'+name,sha256='a'*64) for name in names]
        mapped=[dict(path=row['path'],device='08:01',inode=7) for row in rows]
        class FakePath:
            def __init__(self,path):self.value=str(path);self.name=PurePosixPath(path).name
            def __str__(self):return self.value
            def resolve(self,strict=False):return self
            def stat(self):return SimpleNamespace(st_ino=7,st_dev=1)
        with mock.patch.object(variant,'Path',FakePath),mock.patch.object(variant,'_process_maps',return_value='synthetic'),mock.patch.object(variant,'_native_mappings',return_value=mapped),mock.patch.object(variant.os,'major',return_value=8,create=True),mock.patch.object(variant.os,'minor',return_value=1,create=True),mock.patch.object(variant,'_file') as verify:
            actual=variant.verify_loaded_variant_libraries(dict(native_runtime_files=rows))
            self.assertTrue(actual['exact_inventory']);self.assertEqual(verify.call_count,5)
            mapped[0]['inode']=8
            with self.assertRaisesRegex(ValueError,'inode/device'):variant.verify_loaded_variant_libraries(dict(native_runtime_files=rows))
            mapped[0]['inode']=7;mapped[0]['path']='/wrong/'+names[0]
            with self.assertRaisesRegex(ValueError,'outside'):variant.verify_loaded_variant_libraries(dict(native_runtime_files=rows))
            mapped[0]['path']=rows[0]['path'];mapped.pop()
            with self.assertRaisesRegex(ValueError,'incomplete'):variant.verify_loaded_variant_libraries(dict(native_runtime_files=rows))
            variant.verify_loaded_variant_libraries(dict(native_runtime_files=rows),require_cpu=False)
            verify.side_effect=ValueError('wrong bytes')
            with self.assertRaisesRegex(ValueError,'wrong bytes'):variant.verify_loaded_variant_libraries(dict(native_runtime_files=rows),require_cpu=False)

    def test_fragmented_health_and_optional_failure_are_live_bounded_not_logged(self):
        health=dict(state='RUNNING',backlog_seconds=4,rss=123,source_samples=16000,
            rolling_scope='diarizer_push_only',diarizer_rolling=dict(rolling_rtf=.7),
            transcript='must not copy',refinement=dict(state='disabled',failure='late',label_backlog_seconds=30))
        frames=[channel.status_message('health',health,now=1),channel.status_message('diagnostic',dict(kind='optional_refiner_disabled',error='late',primary_continues=True),now=2)]
        for raw in frames:self.assertLessEqual(len(raw),4096)
        received=[];logs=[];decoder=channel.StreamDecoder(lambda _:self.fail('not spatial'),logs.append,received.append)
        wire=b''.join(frames)+b'actual native diagnostic\n'
        for first in range(0,len(wire),3):decoder.feed(wire[first:first+3])
        decoder.finish()
        self.assertEqual([row['kind'] for row in received],['health','diagnostic'])
        self.assertEqual(received[0]['value']['diarizer_rolling']['rolling_rtf'],.7)
        self.assertEqual(received[0]['value']['refinement']['label_backlog_seconds'],30)
        self.assertNotIn('transcript',received[0]['value'])
        self.assertEqual(b''.join(logs),b'actual native diagnostic\n')
        huge={k:'🙂'*10000 for k in ('kind','state','error','reason','message','optional_refiner','primary_continues','child_dead','supervisor_thread_closed')}
        self.assertLessEqual(len(channel.status_message('diagnostic',huge)),4096)

    def test_health_one_hz_diagnostic_immediate_and_caption_remains_external(self):
        writes=[]
        with mock.patch.object(channel,'_last_health',float('-inf')),mock.patch.object(channel.time,'monotonic',side_effect=[1,1.2,1.3,2]),mock.patch.object(channel.os,'write',side_effect=lambda fd,raw:(writes.append(raw) or len(raw))):
            channel.emit_spatial(dict(kind='health',value={}))
            channel.emit_spatial(dict(kind='health',value={}))
            channel.emit_spatial(dict(kind='diagnostic',value=dict(error='child failed')))
            channel.emit_spatial(dict(kind='health',value={}))
            channel.emit_spatial(dict(kind='caption',row=dict(text='persist elsewhere')))
        self.assertEqual(len(writes),3)
        self.assertEqual([json.loads(raw[len(channel.PREFIX):])['kind'] for raw in writes],['health','diagnostic','health'])

    def test_controls_and_native_driver_refuse_silently_unused_configuration(self):
        self.assertEqual(selection_control_states('pyannote','retained'),dict(geometry='disabled',revision='disabled'))
        self.assertEqual(selection_control_states('nemotron','single_d1_late_labels'),dict(geometry='readonly',revision='normal'))
        self.assertEqual(selection_control_states('nemotron','retained')['revision'],'disabled')
        with self.assertRaisesRegex(ValueError,'no editable'):validate_plan(dict(revision_window_seconds=20),'inspect',5)


if __name__=='__main__':unittest.main()
