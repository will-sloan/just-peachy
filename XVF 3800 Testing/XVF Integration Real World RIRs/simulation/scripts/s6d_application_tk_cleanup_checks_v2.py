"""Related model-free cleanup probes; see README_S6D_APPLICATION_TK_NATIVE_V2.md."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    spec.loader.exec_module(module);return module


class Tests(unittest.TestCase):
    def setup_probe(self,mode):
        folder=OUT/self._testMethodName;folder.mkdir()
        handles=[];surfaces=[];original_open=Path.open
        class Surface:
            def __init__(self):self.destroyed=False;surfaces.append(self)
            def destroy(self):self.destroyed=True
            def title(self,value):pass
        class Gallery:
            def score(self,value):return []
        gallery=Gallery();original_score=gallery.score
        class Engine:
            config=None;_research_gallery=gallery
            def stop(self):
                if mode=='stop_failure':raise RuntimeError('synthetic stop failure')
        engine=Engine()
        class Window:
            count=0
            def __init__(self,*a,**kw):
                Window.count+=1;self._s6d_render_handle=None
                if mode=='partial_second_window' and Window.count==2:
                    self._s6d_render_handle=(folder/'partial_render.jsonl').open('x')
                    raise RuntimeError('synthetic second window failure')
                if mode=='stop_failure':raise RuntimeError('synthetic first window failure')
        class Thread:
            instances=[]
            def __init__(self,**kw):self.ident=None;self.alive=False;self.name=kw['name'];self.joins=0;Thread.instances.append(self)
            def start(self):
                if self.name=='s6d-owned-tk-start':raise RuntimeError('synthetic start failure')
                self.ident=1;self.alive=True
            def join(self,*a):
                if self.ident is None:raise AssertionError('Joined never-started thread')
                self.joins+=1;self.alive=False
            def is_alive(self):return self.alive
        def opened(path,*a,**kw):
            if mode=='consumer_open_failure' and path.name=='consumer_events.jsonl':raise OSError('synthetic consumer open failure')
            f=original_open(path,*a,**kw);handles.append(f);return f
        views=[dict(name='T0',settings={})]
        if mode=='partial_second_window':views.append(dict(name='T1',settings=dict(transcript_mode='T1',selected_profile_ids=['a'])))
        with patch.dict(sys.modules,{'tkinter':SimpleNamespace(Tk=Surface,Toplevel=lambda root:Surface())}),patch.object(Path,'open',opened),patch.object(H.threading,'Thread',Thread):
            with self.assertRaisesRegex((RuntimeError,OSError),'synthetic'):
                H.execute_gui(engine,dict(views=views),{}, {},folder,{},None,S,SimpleNamespace(EdgeSpeechWindow=Window),None,None,None)
        self.assertTrue(surfaces[0].destroyed)
        self.assertEqual(gallery.score,original_score)
        self.assertTrue(all(h.closed for h in handles))
        receipt=json.loads((folder/'OWNED_RESOURCE_CLOSURE.json').read_text())
        self.assertIsNotNone(receipt['setup_or_loop_error'])
        self.assertTrue(receipt['no_session_completion_claim'])
        self.assertFalse((folder/'RESULT.json').exists())
        self.assertFalse(receipt['startup_thread_alive'] or receipt['observer_thread_alive'])
        if mode=='stop_failure':
            self.assertFalse(receipt['resources_closed'])
            self.assertEqual(receipt['cleanup_errors'][0]['resource'],'engine_stop')
            self.assertTrue(receipt['consumer_closed'] and receipt['gallery_spy_restored'] and receipt['root_destroyed'])
        else:self.assertTrue(receipt['resources_closed'])
        OBS[self._testMethodName]=receipt
        return Thread.instances

    def test_consumer_open_failure_destroys_root(self):self.setup_probe('consumer_open_failure')
    def test_partial_second_window_render_handle_is_owned(self):self.setup_probe('partial_second_window')
    def test_stop_failure_does_not_skip_other_cleanup(self):self.setup_probe('stop_failure')
    def test_start_failure_joins_only_started_observer(self):
        threads=self.setup_probe('thread_start_failure')
        self.assertEqual([(t.name,t.joins) for t in threads],[('s6d-owned-tk-start',0),('s6d-owned-tk-resources',1)])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--helper',type=Path,required=True);parser.add_argument('--app-source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();OUT=args.output.resolve();OBS={}
    if OUT.drive.upper()!='G:':raise ValueError('Only fresh G fixture outputs allowed')
    OUT.mkdir(parents=True,exist_ok=False)
    H=load(args.helper,'s6d_tk_cleanup_helper');S=load(args.app_source/'research_s6d.py','s6d_tk_cleanup_policy')
    with (OUT/'TESTS.log').open('x') as log:result=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    H.write_new(OUT/'OBSERVATIONS.json',OBS)
    H.write_new(OUT/'RECEIPT.json',dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),helper=H.binding(args.helper),fixture=H.binding(__file__),observations=H.binding(OUT/'OBSERVATIONS.json'),log=H.binding(OUT/'TESTS.log'),actual_tk_created=False,model_calls=0,device_calls=0))
    print(json.dumps(dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),receipt=str(OUT/'RECEIPT.json'))))
    sys.exit(0 if result.wasSuccessful() else 1)
