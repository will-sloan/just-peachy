"""Lineage corruption fixtures; no source or model execution."""
from copy import deepcopy
import unittest
from common import fingerprint
from application_source_context import gallery_for_catalog,validate_lineage

CONTEXT={}


class SourceContextTests(unittest.TestCase):
    def setUp(self):
        self.parent_binding=deepcopy(CONTEXT['parent_binding']);self.parent=deepcopy(CONTEXT['parent'])
        self.child=deepcopy(CONTEXT['child'])

    def test_exact_lineage_and_catalog_relocation_only(self):
        validate_lineage(self.parent_binding,self.parent,self.child)
        old=CONTEXT['parent_catalog'];new=CONTEXT['catalog'];original=deepcopy(CONTEXT['gallery'])
        rebound=gallery_for_catalog(original,old,new)
        self.assertEqual(rebound['catalog'],new);self.assertEqual(original,CONTEXT['gallery'])
        rebound['catalog']=old;self.assertEqual(rebound,original)

    def test_changed_prediction_frontend_or_file_population_refused(self):
        for rel in ('app/controller.py','app/ui.py','vendor/edge_speech_pipeline/runtime.py'):
            child=deepcopy(self.child);child['files'][rel]['sha256']='0'*64;child['files_sha256']=fingerprint(child['files'])
            with self.subTest(rel=rel),self.assertRaises(ValueError):validate_lineage(self.parent_binding,self.parent,child)
        for action in ('extra','missing'):
            child=deepcopy(self.child)
            if action=='extra':child['files']['extra.py']=dict(sha256='0'*64,bytes=0)
            else:del child['files']['app/native_complete_text.py']
            child['files_sha256']=fingerprint(child['files'])
            with self.subTest(action=action),self.assertRaises(ValueError):validate_lineage(self.parent_binding,self.parent,child)

    def test_parent_policy_inventory_and_acceptance_forgery_refused(self):
        for change in ('parent','budget','fingerprint','acceptance','unchanged_sink'):
            child=deepcopy(self.child)
            if change=='parent':child['parent']['sha256']='0'*64
            elif change=='budget':child['policy']['max_events_bytes']*=2
            elif change=='fingerprint':child['files_sha256']='0'*64
            elif change=='acceptance':child['N4_accepted']=True
            else:child['files']['app/buffers.py']=deepcopy(self.parent['files']['app/buffers.py']);child['files_sha256']=fingerprint(child['files'])
            with self.subTest(change=change),self.assertRaises(ValueError):validate_lineage(self.parent_binding,self.parent,child)

    def test_catalog_byte_or_parent_gallery_mismatch_refused(self):
        old=CONTEXT['parent_catalog'];new=deepcopy(CONTEXT['catalog']);new['sha256']='0'*64
        with self.assertRaises(ValueError):gallery_for_catalog(CONTEXT['gallery'],old,new)
        original=deepcopy(CONTEXT['gallery']);original['catalog']['path']='C:/foreign.json'
        with self.assertRaises(ValueError):gallery_for_catalog(original,old,CONTEXT['catalog'])
