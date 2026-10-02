"""Focused changed saved-source checks; README_RUNTIME_SAVED_CHECK_V1.md."""
import os
import psutil
psutil.Process().cpu_affinity([14])
import argparse
import ast
import base64
import hashlib
import json
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace
import wave


def main():
    ap=argparse.ArgumentParser()
    for key in ('common','installed','scope','output'):ap.add_argument('--'+key,type=Path,required=True)
    a=ap.parse_args();a.output.mkdir();me=psutil.Process()
    (a.output/'REGISTERED_OWNER.json').write_text(json.dumps(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])))
    from datetime import datetime,timezone
    scope=json.loads(a.scope.read_bytes())
    def guard():
        if datetime.now(timezone.utc)>=datetime.fromisoformat(scope['expires_utc']):raise TimeoutError('Host scope')
        if sum(p.stat().st_size for p in a.scope.parent.rglob('*') if p.is_file())>scope['maximum_bytes']:raise RuntimeError('Cumulative host scope')
    guard()
    from field_runtime_recording_controls_v2 import derive as recording
    from field_runtime_saved_modes_v2 import derive,ENDPOINT_PINS,SAVED_HELPERS
    directory=Path(__file__).parent
    sources={m:(directory/('d1_endpoint_contract_v'+str(v[0])+'.py')).read_bytes() for m,v in ENDPOINT_PINS.items()}
    contracts={m:(directory/('D1_ENDPOINT_CONTRACT_V'+str(v[0])+'.json')).read_bytes() for m,v in ENDPOINT_PINS.items()}
    optional,_=recording(a.common.read_bytes())
    packed,review=derive(optional,sources,contracts)
    members={n:base64.b64decode(b) for n,b in json.loads(packed)['files'].items()}
    assert len([n for n in members if n.startswith('code/')])==64
    container=json.loads(members['code/D1_ENDPOINT_CONTRACT_V3.json'])
    assert all(base64.b64decode(container[m])==contracts[m] for m in contracts)
    assert b"actual_source_started" in members['code/field_operator_entry_v11.py']
    assert b"source/SOURCE_STOP.json" in members['code/field_operator_session_ledger_v4.py']

    rejected=[]
    def reject(name,call):
        try:call()
        except (ValueError,RuntimeError):rejected.append(name)
        else:raise AssertionError('Expected rejection: '+name)
    reject('capsule-pin',lambda:derive(optional+b' ',sources,contracts))
    changed=dict(sources);changed['streaming']+=b'\n'
    reject('endpoint-source-pin',lambda:derive(optional,changed,contracts))
    changed=dict(contracts);changed['chunk52']+=b' '
    reject('endpoint-contract-pin',lambda:derive(optional,sources,changed))

    # Actual installed class body, without loading the installed model graph.
    pipeline_raw=(a.installed/'app/pipeline.py').read_bytes()
    assert hashlib.sha256(pipeline_raw).hexdigest()=='0ff46fc53138f74dcc7da4c2841beaf185fad1b068633ef4fbfe6eca7e000ac7'
    tree=ast.parse(pipeline_raw);node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='FileSource')
    import soundfile as sf
    class FixturePacer:
        def __init__(self,origin,rate,stop):self.stop=stop
        def wait_for_end(self,n):return None if self.stop.is_set() else time.perf_counter()
    namespace=dict(Path=Path,threading=threading,time=time,sf=sf,AbsolutePacer=FixturePacer)
    exec(compile(ast.Module(body=[node],type_ignores=[]),'<actual-installed-FileSource>','exec'),namespace)
    fixture_home=a.output/'fixture-home';audio=fixture_home/'JustPeachy/input.wav'
    audio.parent.mkdir(parents=True)
    class FixturePath(type(Path())):
        @classmethod
        def home(cls):return fixture_home
    helpers=dict(Path=FixturePath,hashlib=hashlib,threading=threading)
    exec(compile(SAVED_HELPERS,'<prepared-saved-source-wrapper>','exec'),helpers)
    def wav(path,rate=16000,frames=320,channels=1):
        with wave.open(str(path),'wb') as h:
            h.setparams((channels,2,rate,0,'NONE','not compressed'));h.writeframes(bytes(frames*channels*2))
    wav(audio)
    pin=helpers['saved_input_pin'](audio,'streaming',guard)
    assert pin['samples']==320 and pin['sample_rate']==16000
    records=[];faults=[];events=[]
    class Journal:
        def __init__(self):self.samples=0;self.finished=[]
        def append(self,block):self.samples+=len(block)
        def finish(self,error=None):self.finished.append(error)
    cls=helpers['saved_source_type'](SimpleNamespace(FileSource=namespace['FileSource']),
        lambda:pin,'streaming',guard,SimpleNamespace(source=lambda n,v:records.append((n,v))),faults.append)
    journal=Journal();source=cls(journal,audio,lambda k,v:events.append((k,v)))
    source.start();source.thread.join(3);receipt=source.stop()
    assert not source.thread.is_alive() and receipt['file_context_closed'] and receipt['integrity']['ok']
    assert receipt['integrity']['complete_input'] and source.sent==journal.samples==320 and not faults
    assert receipt['physical_microphone'] is False and receipt['child_process_created'] is False
    assert source.stop() is receipt and len(records)==1
    assert any(k=='source_started' and v['input_sha256']==pin['sha256'] for k,v in events)
    reject('wrong-mode',lambda:helpers['saved_input_pin'](audio,'delayed',guard))
    reject('input-offset',lambda:cls(Journal(),audio,lambda *x:None,start_sample=1))
    wav(audio,rate=8000)
    reject('nonprepared-rate',lambda:helpers['saved_input_pin'](audio,'streaming',guard))
    wav(audio,frames=480001)
    reject('streaming-duration',lambda:helpers['saved_input_pin'](audio,'streaming',guard))
    wav(audio,frames=321)
    reject('changed-start-input',lambda:cls(Journal(),audio,lambda *x:None))
    # Changed input after construction is detected at terminal verification.
    wav(audio);pin=helpers['saved_input_pin'](audio,'streaming',guard)
    source=cls(Journal(),audio,lambda *x:None);wav(audio,frames=321)
    source.start();source.thread.join(3)
    reject('changed-during-input',source.stop)
    assert not source.thread.is_alive() and faults and source.integrity['ok'] is False
    guard()
    result=dict(status='PASS_CHANGED_SAVED_SOURCE_HOST',positive_groups=2,rejects=rejected,
        composition=review,source_samples=320,actual_installed_class=True,
        synthetic_input=True,pacing_fixture=True,model_graph_executed=False,native_executed=False,
        native_gui_or_accuracy_proven=False)
    with (a.output/'RESULT.json').open('x') as h:json.dump(result,h,indent=2)
    print(json.dumps(dict(status=result['status'],positive_groups=2,rejects=len(rejected),bundle_sha256=review['bundle_sha256'])))


if __name__=='__main__':main()

