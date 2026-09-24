"""Model-free versioned-plan compatibility and traversal tests. See README.md."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('n2_make_plan_under_test',Path(__file__).with_name('make_plan.py'))
plan_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(plan_module)


class PlanVersionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='N2 plan version fixture ')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'frozen/prototype';self.source.mkdir(parents=True)
        self.local=self.root/'local/n2';(self.local/'evaluation').mkdir(parents=True)
        for name,count in [('AUDIO_ONLY.json',96),('REGRESSION_AUDIO_ONLY.json',8)]:
            (self.local/'evaluation'/name).write_text(json.dumps(dict(jobs=[dict(job_id=str(i)) for i in range(count)])))

    def create(self,name,version=None):
        out=self.root/name
        argv=['--source',str(self.source),'--local',str(self.local),'--output',str(out)]
        if version is not None:argv+=['--run-version',version]
        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):plan_module.main(argv)
        return out,json.loads(out.read_text())

    def test_default_remains_byte_identical_to_explicit_v1_and_old_paths(self):
        default,one=self.create('default.json');explicit,two=self.create('explicit.json','v1')
        self.assertEqual(default.read_bytes(),explicit.read_bytes());self.assertEqual(one,two)
        for lane in one['lanes']:
            for job in lane['jobs']:
                parent=Path(job['result']).parent
                if job['id']=='gui-panel':self.assertEqual(parent,self.local/'gui-panel-isolated-v1')
                else:self.assertEqual(parent.parent,self.local/('factorial-v1' if job['id'].startswith('screen-') else 'regressions-v1'))
        self.assertEqual(sum(j['cells'] for lane in one['lanes'] for j in lane['jobs']),422)

    def test_v2_changes_only_result_progress_and_output_roots_without_copying_assets(self):
        _,one=self.create('v1.json');_,two=self.create('v2.json','v2')
        for lane1,lane2 in zip(one['lanes'],two['lanes']):
            for old,new in zip(lane1['jobs'],lane2['jobs']):
                expected=deepcopy(old)
                root='gui-panel-isolated-' if old['id']=='gui-panel' else 'factorial-' if old['id'].startswith('screen-') else 'regressions-'
                for field in ('result','progress'):expected[field]=expected[field].replace(root+'v1',root+'v2')
                i=expected['argv'].index('--output')+1
                expected['argv'][i]=expected['argv'][i].replace(root+'v1',root+'v2')
                self.assertEqual(new,expected)
                self.assertFalse(Path(new['result']).parent.exists())
        self.assertEqual(sorted(p.name for p in self.local.iterdir()),['evaluation'])

    def test_invalid_versions_cannot_create_plan_or_escape_output_roots(self):
        invalid=['','v0','v01','V2','v2/extra','../v2',r'v2\extra','v2:stream','v2 ','2','v-2','v2\n']
        for i,value in enumerate(invalid):
            with self.subTest(value=value),self.assertRaises(SystemExit):self.create(f'invalid{i}.json',value)
            self.assertFalse((self.root/f'invalid{i}.json').exists())
        self.assertEqual(plan_module.run_version('v12'),'v12')

    def test_existing_plan_is_never_overwritten(self):
        out,_=self.create('preserved.json');before=out.read_bytes()
        with self.assertRaises(ValueError):self.create('preserved.json','v2')
        self.assertEqual(out.read_bytes(),before)


if __name__=='__main__':unittest.main()
