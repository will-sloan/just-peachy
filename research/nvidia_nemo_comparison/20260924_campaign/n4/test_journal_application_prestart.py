"""Actual common UI/Controller prestart on the complete-journal derivative."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_paced_application_cell as original


class JournalApplicationTests(original.PacedApplicationTests):
    def test_real_application_prepare_and_close_for_three_engine_families(self):
        # Override the original three-family fixture with all 16 catalog rows.
        from common import bind,load
        from controller_projection import forbid_inference
        from mode_galleries import backend_contract
        from paced_application_cell import ApplicationCell
        from app.controller import Controller
        from app.pipeline import FileSource
        catalog=load(self.admission['catalog']['path']);job=self.admission['job']
        def forbidden(*args,**kwargs):raise AssertionError('No source or device start in prestart qualification')
        entries=[row for row in catalog['backends'] if row['implemented']]
        self.assertEqual(len(entries),16)
        with forbid_inference(),patch.object(Controller,'start_file',side_effect=forbidden),\
                patch.object(Controller,'start_live',side_effect=forbidden),patch.object(FileSource,'__init__',side_effect=forbidden):
            for entry in entries:
                contract=backend_contract(catalog,entry['key'],'open_with_names')
                folder=self.output/'prepared'/entry['key'];cell=ApplicationCell(folder,job,contract)
                try:
                    prepared=cell.prepare(source=self.source,models_root=folder/'NO_MODEL_PAYLOAD',
                        runtimes=self.admission['runtimes'],gallery_preparation=self.admission['gallery_preparation'])
                    self.assertEqual(cell.c.backend_id,prepared['backend_id']);self.assertIsNone(cell.c.engine)
                    self.assertIsNone(cell.c.consumer);self.assertEqual(prepared['logical_client'],[480,800])
                    self.assertEqual(prepared['active_height_px'],184)
                    self.assertFalse(cell.c.collect_references);self.assertFalse(cell.c.use_references)
                    self.assertFalse(cell.started);cell.check()
                finally:result=cell.close()
                self.assertEqual(result['status'],'PREPARED_ONLY_CLOSED',str(result))
                self.assertTrue(result['controller_worker_exited']);self.assertFalse(result['source_start_requested'])
                self.assertFalse(result['complete_N4_acceptance'])
                self.prepared.append(dict(backend=entry['key'],engine=contract['engine'],
                    prepared=bind(folder/'PREPARED.json'),result=bind(folder/'RESULT.json')))

    def test_imported_engine_families_share_actual_complete_journal_factory(self):
        from app.pipeline import PrototypeEngine
        from app.n2_pipeline import N2Engine
        from app.n3_pipeline import N3IdentityEngine
        from app.native_complete_text import CompleteText
        from app.buffers import RotatingText
        from common import bind,freeze
        import app.pipeline as pipeline
        self.assertEqual(Path(pipeline.__file__).resolve(),self.source/'app/pipeline.py')
        records=[]
        for cls in (PrototypeEngine,N2Engine,N3IdentityEngine):
            self.assertIs(cls._open_journal_text,PrototypeEngine._open_journal_text)
            owner=SimpleNamespace(writer_delay=0,text_writers=[])
            path=self.output/'factory'/cls.__name__/'events.jsonl'
            writer=cls._open_journal_text(owner,path)
            other=cls._open_journal_text(owner,path.with_name('labelled_transcript.jsonl'))
            try:
                self.assertIsInstance(writer.sink,CompleteText);self.assertIsInstance(other.sink,RotatingText)
                writer.write('synthetic factory check\n');other.write('synthetic transcript check\n')
            finally:writer.close();other.close()
            self.assertEqual(writer.accepted,writer.completed);self.assertEqual(writer.completed,1)
            self.assertTrue(writer.closed and writer.sink.closed);self.assertFalse(writer.thread.is_alive())
            records.append(dict(engine=cls.__name__,event_file=bind(path),synthetic_only=True))
        freeze(self.output/'FACTORY_CHECKS.json',dict(rows=records,real_engine_instances_started=False))
