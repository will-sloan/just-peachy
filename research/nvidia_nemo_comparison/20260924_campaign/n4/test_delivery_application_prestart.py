"""Actual invisible source-delivery cell preparation, with acquisition forbidden."""
from unittest.mock import patch
from test_journal_application_prestart import JournalApplicationTests


class DeliveryApplicationTests(JournalApplicationTests):
    def test_real_application_prepare_and_close_for_three_engine_families(self):
        from common import bind,load
        from controller_projection import forbid_inference
        from mode_galleries import backend_contract
        from paced_application_cell_v2 import ApplicationCell
        from application_delivery import POLICY
        from app.controller import Controller
        from app.pipeline import FileSource
        catalog=load(self.admission['catalog']['path']);job=self.admission['job']
        def forbidden(*args,**kwargs):raise AssertionError('Source construction/start forbidden in prestart qualification')
        entries=[row for row in catalog['backends'] if row['implemented']]
        self.assertEqual(len(entries),16)
        original_start=FileSource.start
        # Keep __init__/start code origins available for the launch adapter's
        # verification; __new__ rejects any actual FileSource construction.
        with forbid_inference(),patch.object(Controller,'start_file',side_effect=forbidden),\
                patch.object(Controller,'start_live',side_effect=forbidden),patch.object(FileSource,'__new__',side_effect=forbidden):
            for entry in entries:
                contract=backend_contract(catalog,entry['key'],'open_with_names')
                folder=self.output/'prepared'/entry['key'];cell=ApplicationCell(folder,job,contract)
                try:
                    prepared=cell.prepare(source=self.source,models_root=folder/'NO_MODEL_PAYLOAD',
                        runtimes=self.admission['runtimes'],gallery_preparation=self.admission['gallery_preparation'])
                    self.assertEqual(cell.c.backend_id,prepared['backend_id']);self.assertIsNone(cell.c.engine)
                    self.assertIsNone(cell.c.consumer);self.assertEqual(prepared['logical_client'],[480,800])
                    self.assertEqual(prepared['active_height_px'],184);self.assertEqual(prepared['delivery_policy'],POLICY)
                    self.assertFalse(cell.delivery.test_seams);self.assertFalse(cell.delivery.ever_installed)
                    self.assertFalse(cell.c.collect_references);self.assertFalse(cell.c.use_references)
                    self.assertFalse(cell.started);cell.check()
                finally:result=cell.close()
                self.assertEqual(result['status'],'PREPARED_ONLY_CLOSED',str(result))
                self.assertTrue(result['controller_worker_exited']);self.assertFalse(result['source_start_requested'])
                self.assertIsNone(result['delivery_join']);self.assertEqual(result['application_variant'],'source-delivery-v2')
                captured=load(result['delivery_capture']['path'])
                self.assertEqual(captured['status'],'PREPARED_WITHOUT_SOURCE_DELIVERY')
                self.assertFalse(captured['test_seams_used']);self.assertEqual(captured['launch_attempts'],0)
                self.assertIsNone(captured['observation']);self.assertIsNone(captured['trace'])
                self.assertIs(FileSource.start,original_start);self.assertFalse(result['complete_N4_acceptance'])
                self.prepared.append(dict(backend=entry['key'],engine=contract['engine'],
                    prepared=bind(folder/'PREPARED.json'),result=bind(folder/'RESULT.json'),delivery_capture=result['delivery_capture']))
