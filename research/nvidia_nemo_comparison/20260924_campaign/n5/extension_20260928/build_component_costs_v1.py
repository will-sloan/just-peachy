"""Fresh source derivative for complete call accounting. README_COMPONENT_COSTS_V1.md."""
from pathlib import Path
import ast,shutil,sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent.parent/'n4'))
from common import bind,freeze,load,verify
from metric_process import pin,exact_process
from window_guard import window,snapshot


def once(text,old,new):
    if text.count(old)!=1:raise ValueError('Parent anchor differs: '+old[:80])
    return text.replace(old,new,1)


def main():
    pin();window();local=HERE.parent.parents[4]/'local'
    worker=load(local/'supervision/worker.json')
    owners=[dict(pid=worker['pid'],create_time=worker['create_time'])]
    if worker.get('child_pid'):owners.append(dict(pid=worker['child_pid'],create_time=worker['child_create_time']))
    if any(exact_process(o) is not None for o in owners):raise RuntimeError('Prior owner alive')
    parent=bind(local/'n5/research-extension-20260928/derivatives/ui-error-v1/DERIVATIVE.json')
    if parent['sha256']!='19b12da2b14229fd57e44e936592bac2daecae03826c1ebddc430dedd185bbf8':raise ValueError('Unreviewed source')
    d=load(parent['path']);source=Path(d['prototype'])
    target=local/'n5/research-extension-20260928/derivatives/component-costs-v1'
    if target.exists():raise FileExistsError(target)
    census=snapshot(local,16*1024**2)
    edits={}
    for name in ('app/pipeline.py','app/n2_pipeline.py','app/n3_pipeline.py','vendor/edge_speech_pipeline/runtime.py'):
        verify(dict(path=str(source/name),**d['files'][name]))
        edits[name]=(source/name).read_text(encoding='utf-8')
    p=edits['app/pipeline.py']
    p=once(p,'        self.resident=models;self.writer_delay=writer_delay;self.text_writers=[]',
        '        from edge_speech_pipeline.component_costs import CallCosts\n        self._component_costs=CallCosts()\n        self.resident=models;self.writer_delay=writer_delay;self.text_writers=[]')
    p=once(p,'    def _prepare_native_models(self,caption_only):return self.resident.acquire(self.config,caption_only)',
        "    def _prepare_native_models(self,caption_only):return self._cost_call('model_setup',self.resident.acquire,self.config,caption_only)")
    edits['app/pipeline.py']=p
    p=edits['app/n2_pipeline.py']
    for old,new in (
        ("diarizer=self.resident.acquire_diarizer(self._session_dir.name)","diarizer=self._cost_call('diarizer_setup',self.resident.acquire_diarizer,self._session_dir.name)"),
        ('update=diarizer.push(audio)',"update=self._cost_call('diarizer_push',diarizer.push,audio,samples=len(audio))"),
        ('self._accept_activity(diarizer.finish(),models)',"self._accept_activity(self._cost_call('diarizer_finish',diarizer.finish),models)"),
        ('vector=models.embed(audio)',"vector=self._cost_call('embedding',models.embed,audio,samples=len(audio))")):
        p=once(p,old,new)
    edits['app/n2_pipeline.py']=p
    p=edits['app/n3_pipeline.py']
    p=once(p,'rows = asr.feed(audio)',"rows = self._cost_call('asr_accept',asr.feed,audio,samples=int(audio.size))")
    p=once(p,'rows = asr.finish_events()',"rows = self._cost_call('asr_finish',asr.finish_events)")
    edits['app/n3_pipeline.py']=p
    p=edits['vendor/edge_speech_pipeline/runtime.py']
    p=once(p,'    def telemetry(self) -> dict[str, object]:',
        "    def _cost_call(self, key, function, *args, samples=0, **kwargs):\n        ledger = getattr(self, '_component_costs', None)\n        if ledger is None: return function(*args, **kwargs)\n        return ledger.call(key, function, *args, samples=samples, **kwargs)\n\n    def telemetry(self) -> dict[str, object]:")
    p=once(p,'        data = dict(self._telemetry)',"        data = dict(self._telemetry)\n        if hasattr(self, '_component_costs'): data['component_costs'] = self._component_costs.snapshot()")
    for old,new in (
        ('text, endpoint = asr.accept(block)',"text, endpoint = self._cost_call('asr_accept',asr.accept,block,samples=int(block.size))"),
        ('asr.accept(pending)',"self._cost_call('asr_accept',asr.accept,pending,samples=int(pending.size))"),
        ('final = asr.reset_endpoint()',"final = self._cost_call('asr_reset',asr.reset_endpoint)"),
        ('final = asr.finish()',"final = self._cost_call('asr_finish',asr.finish)")):
        p=once(p,old,new)
    edits['vendor/edge_speech_pipeline/runtime.py']=p
    for name,text in edits.items():ast.parse(text,filename=name)
    prototype=target/'prototype';prototype.mkdir(parents=True)
    for name,row in d['files'].items():
        verify(dict(path=str(source/name),**row));out=prototype/name;out.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source/name,out)
    for name,text in edits.items():
        raw=text.encode('utf-8')
        if b'\r\n' in (source/name).read_bytes():raw=raw.replace(b'\n',b'\r\n')
        (prototype/name).write_bytes(raw)
    shutil.copyfile(HERE/'component_costs_v1.py',prototype/'vendor/edge_speech_pipeline/component_costs.py')
    shutil.copyfile(HERE/'README_COMPONENT_COSTS_V1.md',prototype/'app/README_COMPONENT_COSTS_V1.md')
    files={}
    for file in sorted(prototype.rglob('*')):
        if file.is_file():b=bind(file);files[file.relative_to(prototype).as_posix()]={k:b[k] for k in ('sha256','bytes')}
    changed=sorted(n for n,r in d['files'].items() if files[n]!=r)
    assert changed==sorted(edits)
    freeze(target/'CENSUS.json',census)
    freeze(target/'DERIVATIVE.json',dict(schema='extended-component-costs-v1',status='PREPARED_NOT_RELEASE_ACCEPTED',
        parent_source_receipt=parent,e0_shutdown_parent=d['e0_shutdown_parent'],prototype=str(prototype),files=files,
        changed_code=changed,added=['vendor/edge_speech_pipeline/component_costs.py','app/README_COMPONENT_COSTS_V1.md'],
        code=[bind(HERE/f) for f in ('build_component_costs_v1.py','component_costs_v1.py','test_component_costs_v1.py','README_COMPONENT_COSTS_V1.md')],
        census=bind(target/'CENSUS.json'),closed_prior_owners=owners))
    print(dict(status='PREPARED_NOT_TESTED',files=len(files),changed=changed))


if __name__=='__main__':main()
