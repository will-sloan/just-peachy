"""Deterministic fresh app derivative; README_APP_BOUNDED_ARTIFACTS_V1.md."""
import hashlib
import json
import shutil
from pathlib import Path


def prepare(source, target, helper_dir):
    source, target, helper_dir = map(Path, (source,target,helper_dir))
    if target.exists(): raise FileExistsError(target)
    bound = {'app/pipeline.py':'80c49b5e3dfb32a3de38e93726051efd9f950bdd9055659a265003af0dfa4e72',
             'app/sessions.py':'33dc0f6d5764a4f1c469c9ad66c047163cdb44dbd779fed399276d96e21094db'}
    for name, expected in bound.items():
        if hashlib.sha256((source/name).read_bytes()).hexdigest() != expected: raise ValueError('Parent changed: '+name)
    shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    def change(name, edits):
        path=target/name; text=path.read_text()
        for old,new in edits:
            if text.count(old)!=1: raise ValueError('Patch boundary mismatch: '+old[:60])
            text=text.replace(old,new)
        path.write_text(text,encoding='utf-8',newline='\n')
    change('app/pipeline.py',[
        ('from .native_complete_text import CompleteText','from .native_complete_text import CompleteText\nfrom .app_bounded_artifacts_v1 import ArtifactAsyncText'),
        ('writer=AsyncText(path,delay_once=',"writer=(ArtifactAsyncText if Path(path).name=='events.jsonl' else AsyncText)(path,delay_once=")])
    change('app/sessions.py',[
        ('RATE=16000\nMIB=1024**2','from .app_bounded_artifacts_v1 import CompactBinary, AudioWithPCM, compact_rows\n\nRATE=16000\nMIB=1024**2'),
        ("self.policy['record_bytes']=record_limit", "self.policy['record_bytes']=record_limit\n        self.metadata.update(event_format='compact-patch-v1',listening_copy='model_input.wav' if audio else None,pcm_max_frames=960000)"),
        ("for name in ('events','windows','resources'):handles[name]=(self.path/(name+'.jsonl')).open('ab',buffering=0)","handles['events']=CompactBinary(self.path/'events.jsonl')\n            for name in ('windows','resources'):handles[name]=(self.path/(name+'.jsonl')).open('ab',buffering=0)"),
        ("if self.audio:handles['audio']=(self.path/'model_input.f32le').open('ab',buffering=0)","if self.audio:handles['audio']=AudioWithPCM(self.path/'model_input.f32le',self.metadata['pcm_max_frames'])"),
        ("if kind=='events':index_event(db,json.loads(data),offset,len(data))","# Compact events reopen through the bounded decoder, not raw byte offsets."),
        ("self._check_space(len(data),kind)","self._check_space(len(data)+(len(data)//2 if kind=='audio' else 0)+(44 if kind=='audio' and not self.written_samples else 0),kind)"),
        ("self.audio_bytes+=len(data);self.written_samples", "self.audio_bytes+=len(data)+len(data)//2+(44 if not self.written_samples else 0);self.written_samples"),
        ("finally:f.close()", "finally:\n                        if hasattr(f,'failed'):f.failed=bool(self.error)\n                        f.close()"),
        ("self.closed=True\n            try:self._checkpoint", "self.metadata['artifact_metrics']={k:f.metrics() for k,f in handles.items() if hasattr(f,'metrics')}\n            self.closed=True\n            try:self._checkpoint"),
        ("if (p.parent/'events.jsonl').exists():recover_index(p.parent)","if (p.parent/'events.jsonl').exists() and m.get('event_format')!='compact-patch-v1':recover_index(p.parent)"),
        ("folder=self.epoch(identifier,epoch)\n            if not", "folder=self.epoch(identifier,epoch)\n            if read_json(folder/'epoch.json').get('event_format')=='compact-patch-v1':\n                yield from compact_rows(folder,identifier,epoch,limit)\n                continue\n            if not")])
    for name in ('app_bounded_artifacts_v1.py','bounded_live_artifacts_v1.py'):
        shutil.copyfile(helper_dir/name,target/'app'/name)
    manifest={p.relative_to(target).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(target.rglob('*')) if p.is_file()}
    (target/'ARTIFACT_DERIVATIVE.json').write_text(json.dumps(dict(parent=str(source),changed=['app/pipeline.py','app/sessions.py'],added=['app/app_bounded_artifacts_v1.py','app/bounded_live_artifacts_v1.py'],files=manifest),indent=2))
    return manifest
