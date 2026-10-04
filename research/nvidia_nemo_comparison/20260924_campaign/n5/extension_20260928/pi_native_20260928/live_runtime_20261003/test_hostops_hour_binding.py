"""Exact actual closed-hour ownership derivative. README_HOST_OPERATIONS.md."""
import hashlib
import json
import unittest
from host_operations import Q,closed_unit_owner


class HourBindingTests(unittest.TestCase):
    def test_actual_six_field_hour_accepts_only_exact_completed_copy(self):
        root=Q/'chunk52-threads2-hour-01-monitor-02'
        raw=(root/'closed-output/UNIT_OWNERSHIP.json').read_bytes()
        job=json.loads((root/'RESULT.json').read_bytes())['job']
        rows=json.loads((root/'MIRROR_MANIFEST.json').read_bytes())
        entry=next(row for row in rows if row['path']=='UNIT_OWNERSHIP.json')
        closure=json.loads((root/'MIRROR_COMPLETE.json').read_bytes())['closure']
        result=closed_unit_owner(job,raw,entry,closure)
        self.assertEqual(result['owner'],job['owner'])
        self.assertEqual(result['sha256'],'3146b28d6ef3ccc9fe90fd331bded738d4c4d81c22cd882e32f605132eb59dc7')
        for changed in (dict(job,unit='jp-v29-other.service'),dict(job,output_root=job['output_root']+'-other'),
                        dict(job,package_manifest_sha256='0'*64)):
            with self.subTest(changed=changed),self.assertRaises(ValueError):closed_unit_owner(changed,raw,entry,closure)
        for key in ('closed','exact_owner_gone','cgroup_empty'):
            with self.subTest(key=key),self.assertRaises(ValueError):closed_unit_owner(job,raw,entry,dict(closure,**{key:False}))
        for key,value in (('runtime_max_seconds',4531),('main_pid',11411)):
            changed=json.loads(raw);changed[key]=value
            altered=json.dumps(changed,sort_keys=True,separators=(',',':')).encode()
            matching=dict(entry,identity=dict(entry['identity'],bytes=len(altered)),sha256=hashlib.sha256(altered).hexdigest())
            with self.subTest(key=key),self.assertRaises(ValueError):closed_unit_owner(job,altered,matching,closure)
        with self.assertRaises(ValueError):closed_unit_owner(job,raw,dict(entry,sha256='0'*64),closure)


if __name__=='__main__':unittest.main()
