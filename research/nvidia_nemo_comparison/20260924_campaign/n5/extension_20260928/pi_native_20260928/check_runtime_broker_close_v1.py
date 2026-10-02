"""Focused actual-method Close regression; README_RUNTIME_BROKER_CLOSE_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,ast,base64,json,os,sys,types
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir();me=psutil.Process()
    def save(name,value):
        raw=json.dumps(value,sort_keys=True,indent=2).encode()
        with (a.output/name).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        assert (a.output/name).read_bytes()==raw
    save('REGISTERED_OWNER.json',dict(pid=me.pid,create_time=me.create_time(),affinity=[14]))
    from field_runtime_broker_close_v1 import derive
    raw,review=derive(a.bundle.read_bytes());bundle=json.loads(raw)
    tree=ast.parse(base64.b64decode(bundle['files']['code/field_operator_chooser_v3.py']))
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Chooser')
    ns={};exec(compile(ast.Module(body=[cls],type_ignores=[]),'<actual-changed-chooser>','exec'),ns)
    C=ns['Chooser'];events=[]
    class Widget:
        def configure(self,**kw):assert not ui.closed;events.append(('configure',kw))
    class Root:
        destroyed=False;callback=None
        def deiconify(self):assert not self.destroyed
        def update(self):
            assert not self.destroyed
            if self.callback:
                cb,self.callback=self.callback,None;cb();assert not self.destroyed
        def destroy(self):assert not self.destroyed;self.destroyed=True;events.append('destroy')
    class Broker:
        proc=None;closed=False
        def poll(self):return True
        def close(self):assert not self.closed;self.closed=True;events.append('broker-close')
    def instance():
        x=C.__new__(C);x.root=Root();x.broker=Broker();x.closed=False;x.close_requested=False;x.fault=None;x.status=Widget();x.refresh=lambda:None
        return x
    module=types.ModuleType('d1_visible_controls_v2')
    def visible(root):root.update();assert not root.destroyed
    module.visible=visible
    if module.__name__ in sys.modules:raise RuntimeError('Unexpected preloaded fixture module')
    sys.modules[module.__name__]=module
    try:
        ui=instance();ui.root.callback=ui.close;ui.tick()
        assert ui.closed and ui.broker.closed and ui.root.destroyed and events[-2:]==['broker-close','destroy']
        ui=instance();ui.broker.proc=types.SimpleNamespace(poll=lambda:None);ui.close()
        assert not ui.close_requested and not ui.closed and not ui.broker.closed
        ui=instance();ui.close();assert ui.close_requested and not ui.closed
        ui.tick();assert ui.closed and ui.broker.closed
    finally:sys.modules.pop(module.__name__)
    save('RESULT.json',dict(status='PASS_ACTUAL_CHANGED_METHODS_SYNTHETIC_TK',cases=3,native_executed=False,review=review))
    print(json.dumps(dict(status='PASS',cases=3)))

if __name__=='__main__':main()
