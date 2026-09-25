"""Exercise actual copied AsyncText and actual journal factory without inference."""
import ast
import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

OUTPUT = None
SOURCE = None


def module(name, path):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class NativeRetentionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.buffers=module('n4_test_copied_buffers',SOURCE/'app/buffers.py')
        cls.complete=module('n4_test_complete_sink',SOURCE/'app/native_complete_text.py')
        tree=ast.parse((SOURCE/'app/pipeline.py').read_text(encoding='utf-8-sig'))
        engine=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='PrototypeEngine')
        method=next(node for node in engine.body if isinstance(node,ast.FunctionDef) and node.name=='_open_journal_text')
        isolated=ast.Module(body=[method],type_ignores=[])
        namespace=dict(AsyncText=cls.buffers.AsyncText,CompleteText=cls.complete.CompleteText,Path=Path)
        exec(compile(ast.fix_missing_locations(isolated),str(SOURCE/'app/pipeline.py'),'exec'),namespace)
        cls.factory=staticmethod(namespace['_open_journal_text'])

    def setUp(self):
        self.folder=OUTPUT/self._testMethodName;self.folder.mkdir()

    def test_actual_factory_selects_complete_events_and_unchanged_other_writers(self):
        owner=SimpleNamespace(writer_delay=0,text_writers=[])
        events=self.factory(owner,self.folder/'events.jsonl')
        transcript=self.factory(owner,self.folder/'labelled_transcript.jsonl')
        try:
            self.assertIsInstance(events.sink,self.complete.CompleteText)
            self.assertIsInstance(transcript.sink,self.buffers.RotatingText)
            self.assertEqual(events.queue.maxsize,4096);self.assertEqual(len(owner.text_writers),2)
            self.assertEqual(events.sink.max_bytes,256*1024**2)
        finally:events.close();transcript.close()

    def test_actual_async_writer_keeps_prefix_beyond_old_three_megabyte_window(self):
        owner=SimpleNamespace(writer_delay=0,text_writers=[]);path=self.folder/'events.jsonl'
        writer=self.factory(owner,path);expected=hashlib.sha256();count=4096
        try:
            for index in range(count):
                line=f'{index:06d} '+('x'*1024)+'\n';expected.update(line.encode());writer.write(line)
                if index%64==63:writer.queue.join()
        finally:writer.close()
        self.assertGreater(path.stat().st_size,3*1024**2)
        with path.open('rb') as stream:self.assertEqual(hashlib.file_digest(stream,'sha256').hexdigest(),expected.hexdigest())
        self.assertEqual(writer.accepted,writer.completed);self.assertEqual(writer.completed,count)
        self.assertFalse(writer.thread.is_alive());self.assertTrue(writer.closed);self.assertTrue(writer.sink.closed)
        self.assertIsNone(writer.error);self.assertEqual(writer.sink.rotations,0)
        self.assertEqual(list(self.folder.iterdir()),[path])

    def test_exact_byte_bound_and_unicode_preserve_prefix_on_failure(self):
        path=self.folder/'events.jsonl';sink=self.complete.CompleteText(path,max_bytes=5)
        try:
            self.assertEqual(sink.write('é\n'),2);self.assertEqual(sink.write('a\n'),2)
            with self.assertRaises(RuntimeError):sink.write('b\n')
            sink.flush();self.assertEqual(path.read_bytes(),'é\na\n'.encode())
            self.assertEqual(sink._bytes,5)
        finally:sink.close()

    def test_existing_file_is_never_appended_or_overwritten(self):
        path=self.folder/'events.jsonl';path.write_bytes(b'preserved\n')
        with self.assertRaises(FileExistsError):self.complete.CompleteText(path)
        self.assertEqual(path.read_bytes(),b'preserved\n')

    def test_sink_failure_propagates_through_actual_async_close(self):
        path=self.folder/'events.jsonl'
        writer=self.buffers.AsyncText(path,sink_factory=lambda p:self.complete.CompleteText(p,max_bytes=3))
        writer.write('ok\n');writer.queue.join();writer.write('overflow\n');writer.queue.join()
        self.assertIsNotNone(writer.error)
        with self.assertRaises(RuntimeError):writer.write('later\n')
        with self.assertRaises(RuntimeError):writer.close()
        self.assertFalse(writer.thread.is_alive());self.assertTrue(writer.sink.closed)
        self.assertEqual(writer.accepted,2);self.assertEqual(writer.completed,1)
        self.assertEqual(path.read_bytes(),b'ok\n')

    def test_existing_per_record_guard_still_rejects_without_enqueue(self):
        path=self.folder/'events.jsonl';writer=self.buffers.AsyncText(path,sink_factory=self.complete.CompleteText)
        try:
            with self.assertRaises(RuntimeError):writer.write('x'*(1024**2+1))
            self.assertEqual(writer.accepted,0)
        finally:writer.close()
        self.assertEqual(path.stat().st_size,0)

    def test_default_async_writer_still_rotates_with_existing_behavior(self):
        path=self.folder/'transcript.txt';writer=self.buffers.AsyncText(path);writer.sink.max_bytes=4
        try:
            for _ in range(4):writer.write('abc\n');writer.queue.join()
        finally:writer.close()
        self.assertEqual(writer.sink.rotations,3)
        self.assertEqual(len(list(self.folder.iterdir())),3)
        self.assertEqual(writer.completed,4)

    def test_invalid_budget_and_closed_write_are_rejected(self):
        for value in (True,0,-1,1.5,256*1024**2+1):
            with self.subTest(value=value),self.assertRaises(ValueError):self.complete.CompleteText(self.folder/'bad',max_bytes=value)
        sink=self.complete.CompleteText(self.folder/'events.jsonl');sink.close();sink.close();sink.flush()
        with self.assertRaises(ValueError):sink.write('late\n')
