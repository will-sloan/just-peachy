"""Focused non-authorizing production14 checks; README_PRODUCTION14_PLAN.md."""
import copy
import importlib.util
from pathlib import Path
import time
import unittest

import prepare_production14_plan as target

Q=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
PLAN=Q/'audit-preparation/production14-plan-d6b03cfe19924879b4b6a990711cb89a'


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec)
    exec(compile(target.read(path),str(path),'exec'),value.__dict__)
    return value


class Production14Plan(unittest.TestCase):
    def test_actual_plan_cannot_authorize_or_relocate(self):
        plan=target.strict(target.read(PLAN/'PRODUCTION_PLAN_NOT_AUTHORIZATION.json'))
        certificate=target.strict(target.read(PLAN/'RELOCATION_REQUIRES_REVIEW.json'))
        review=target.strict(target.read(PLAN/'REVIEW.json'))
        source=Path(review['source']);binding_raw=target.read(source/'BINDING.json')
        binding=target.strict(binding_raw);destination=target.strict(target.read(PLAN/'DISABLED_DESTINATION_BINDING_PREVIEW.json'))
        builder=load(PLAN/'pinned-builder/prepare_package.py','plan_builder')
        authorization=load(PLAN/'pinned-builder/release_authorization.py','plan_auth')
        with self.assertRaisesRegex(ValueError,'production acceptance'):
            authorization.validate_acceptance(plan,destination)
        with self.assertRaisesRegex(ValueError,'reviewed path-only'):
            builder.validate_relocation(certificate,binding,destination,review['source_manifest_sha256'],binding_raw)
        self.assertEqual(len(plan['allowed_selections']),246)
        self.assertEqual(len(plan['assets']),61)
        self.assertEqual(plan['optional_refiner_admissions'],[])
        self.assertIsNone(plan['full_backup'])
        self.assertFalse(destination['native_launch_enabled'])

    def test_in_memory_review_allows_only_exact13_path_fields(self):
        review=target.strict(target.read(PLAN/'REVIEW.json'));source=Path(review['source'])
        binding_raw=target.read(source/'BINDING.json');binding=target.strict(binding_raw)
        destination,certificate=target.relocation(binding,review['source_manifest_sha256'],binding_raw)
        # Pure in-memory fixture; never written or presented as actual review.
        certificate.update(reviewed=True,reviewer='synthetic host fixture',reviewed_unix=time.time())
        builder=load(PLAN/'pinned-builder/prepare_package.py','plan_builder')
        builder.validate_relocation(certificate,binding,destination,review['source_manifest_sha256'],binding_raw)
        self.assertEqual(len(certificate['relocations']),13)
        changed=copy.deepcopy(destination);changed['live_config']['block_frames']=960
        with self.assertRaisesRegex(ValueError,'runtime behavior'):
            builder.validate_relocation(certificate,binding,changed,review['source_manifest_sha256'],binding_raw)


if __name__=='__main__':unittest.main()
