"""Bounded private conversation transfer; see README_FIELD_ARCHIVE_V1.md."""
import ctypes
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import uuid
import wave
import zipfile

from app.sessions import SessionStore

MIB = 1024**2
ZIP_MAX = 8*MIB
TOTAL_MAX = 32*MIB
FILE_MAX = 8*MIB
META_MAX = MIB
RECEIPT_RESERVE = 65536
MANIFEST = 'TRANSFER_MANIFEST.json'
SCHEMA = 'just-peachy.private-conversation-transfer.v1'
ID = re.compile(r'[0-9a-f]{32}\Z')
EPOCH_FILES = {'epoch.json', 'events.jsonl', 'resources.jsonl', 'windows.jsonl',
               'model_input.f32le', 'model_input.wav', 'captions.sqlite'}


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f, 'sha256').hexdigest()


def strict_json(data):
    if len(data)>META_MAX:raise ValueError('Metadata size limit')
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('Duplicate JSON key')
            result[key]=value
        return result
    def invalid(value):raise ValueError('Nonfinite JSON number')
    return json.loads(data,object_pairs_hook=pairs,parse_constant=invalid)


def safe_name(name):
    if not isinstance(name,str) or len(name)>240 or any(ord(c)<32 for c in name):raise ValueError('Archive path')
    if '\\' in name or ':' in name or name.startswith('/') or any(x in ('','.', '..') for x in name.split('/')):
        raise ValueError('Archive path')
    parts=PurePosixPath(name).parts
    if name in ('conversation.json',MANIFEST):return
    if len(parts)!=3 or parts[0]!='epochs' or not ID.fullmatch(parts[1]) or parts[2] not in EPOCH_FILES:
        raise ValueError('Unsupported archive member')


def regular_tree(root):
    result={}
    for path in Path(root).rglob('*'):
        mode=path.lstat().st_mode
        if stat.S_ISLNK(mode):raise ValueError('Linked private path')
        if stat.S_ISDIR(mode):continue
        if not stat.S_ISREG(mode):raise ValueError('Nonregular private file')
        result[path.relative_to(root).as_posix()]=path.stat().st_size
    return result


def validate_folder(folder, identifier):
    """Admit only completed compact archives; paths in descriptive metadata are never opened."""
    import numpy as np
    from app.app_bounded_artifacts_v1 import compact_rows, compact_records
    files=regular_tree(folder)
    for name in files:safe_name(name)
    if len(files)>128 or sum(files.values())>TOTAL_MAX or max(files.values(),default=0)>FILE_MAX:
        raise ValueError('Archive file/total/count limit')
    m=strict_json((folder/'conversation.json').read_bytes())
    if m.get('schema')!='just-peachy.conversation.v1' or m.get('id')!=identifier or not ID.fullmatch(identifier):raise ValueError('Conversation schema/id')
    if m.get('state')!='SAVED' or m.get('pinned') is not True:raise ValueError('Import requires saved completed conversation')
    if not isinstance(m.get('title'),str) or not 1<=len(m['title'])<=160:raise ValueError('Conversation title')
    for key in ('notes','corrections'):
        if not isinstance(m.get(key),list) or len(m[key])>200:raise ValueError('Annotation schema')
    epochs=m.get('epochs')
    if not isinstance(epochs,list) or not 1<=len(epochs)<=8 or len(set(epochs))!=len(epochs) or any(not isinstance(e,str) or not ID.fullmatch(e) for e in epochs):raise ValueError('Epoch membership')
    expected={'conversation.json'}|{f'epochs/{e}/{f}' for e in epochs for f in EPOCH_FILES}
    if set(files)!=expected:raise ValueError('Exact epoch file membership required')
    counts={};rows=0
    for ep in epochs:
        p=folder/'epochs'/ep;em=strict_json((p/'epoch.json').read_bytes())
        if any(em.get(k)!=v for k,v in dict(schema='just-peachy.epoch.v1',archive_epoch_id=ep,state='CLOSED',closed=True,
                event_format='compact-patch-v1',sample_rate=16000,channels=1,audio_enabled=True,
                master='model_input.f32le',listening_copy='model_input.wav').items()):raise ValueError('Unsupported epoch/source schema')
        if em.get('archive_error') or em.get('pipeline_terminal_state')!='COMPLETED':raise ValueError('Incomplete epoch')
        master=p/'model_input.f32le';n=master.stat().st_size//4
        if not n or master.stat().st_size%4 or sha(master)!=em.get('audio_sha256'):raise ValueError('Float source size/hash')
        with master.open('rb') as f:
            while block:=f.read(65536):
                if not np.isfinite(np.frombuffer(block,dtype='<f4')).all():raise ValueError('Nonfinite source')
        with wave.open(str(p/'model_input.wav'),'rb') as wav:
            if (wav.getnchannels(),wav.getsampwidth(),wav.getframerate(),wav.getnframes(),wav.getcomptype())!=(1,2,16000,n,'NONE'):raise ValueError('PCM source schema')
            if len(wav.readframes(n))!=n*2:raise ValueError('Truncated PCM')
        # Consume the full bounded compact stream, including its final footer.
        for unused in compact_records(p/'events.jsonl'):pass
        for row in compact_rows(p,identifier,ep,None):
            a,b=row.get('source_start_sample'),row.get('source_end_sample')
            if type(a) is not int or type(b) is not int or not 0<=a<=b<=n:raise ValueError('Caption/source bounds')
            rows+=1
        counts[ep]=n
    return dict(identifier=identifier,epochs=counts,raw_rows=rows,bytes=sum(files.values()))


def rename_noreplace(source,target):
    """Linux atomic publication; no replacing destination and no unsafe fallback."""
    libc=ctypes.CDLL(None,use_errno=True)
    fn=libc.renameat2;fn.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint];fn.restype=ctypes.c_int
    if fn(-100,os.fsencode(source),-100,os.fsencode(target),1):
        error=ctypes.get_errno();raise OSError(error,os.strerror(error),str(target))


class FieldArchiveStore(SessionStore):
    def __init__(self,data_root,contract):
        self.data_root=Path(data_root).resolve();self.contract=contract
        if contract['private_data_quota_bytes']!=512*MIB or contract['minimum_free_bytes']!=5*1024**3:raise ValueError('Field storage policy mismatch')
        super().__init__(self.data_root,policy=dict(quota_mib=512,free_floor_mib=5120))

    def usage(self):
        value=super().usage()
        value.update(path=str(self.data_root),bytes=sum(regular_tree(self.data_root).values()),scope='all private data including rejected imports',automatic_cleanup=False)
        return value

    def require_space(self,additional):
        u=self.usage()
        if u['bytes']+additional>self.contract['private_data_quota_bytes']:raise OSError('Private storage limit reached (512 MiB)')
        if u['free_bytes']<self.contract['minimum_free_bytes']+additional:raise OSError('Device free-space reserve (5 GiB)')

    def enforce(self,exclude=None):
        self.require_space(RECEIPT_RESERVE)
        if len([r for r in self.list() if not r['pinned'] and r['id']!=exclude])>=self.policy['draft_limit']:
            raise OSError('Draft limit reached; manage history explicitly. Nothing was deleted.')

    def export(self,identifier,destination,*,include_audio=False,consent=False):
        if not include_audio:return super().export(identifier,destination,include_audio=False,consent=consent)
        if consent is not True:raise ValueError('Explicit private export consent required')
        self._quiet(identifier);folder=self.folder(identifier)
        summary=validate_folder(folder,identifier);target=Path(destination).absolute()
        if folder==target or folder in target.parents:raise ValueError('Export must be outside source')
        target.parent.mkdir(parents=True,exist_ok=True)
        files={name:dict(bytes=size,sha256=sha(folder/name)) for name,size in regular_tree(folder).items()}
        manifest=dict(schema=SCHEMA,identifier=identifier,files=files,scope='Private exact audio and model events; unencrypted; imported provenance is not independently trusted')
        if self.data_root in target.resolve().parents:self.require_space(ZIP_MAX)
        if shutil.disk_usage(target.parent).free<5*1024**3+ZIP_MAX:raise OSError('Export free-space reserve')
        with target.open('xb') as output:
            with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
                z.writestr(MANIFEST,json.dumps(manifest,sort_keys=True))
                for name,binding in files.items():
                    with (folder/name).open('rb') as f,z.open(name,'w') as dst:
                        h=hashlib.sha256();count=0
                        while block:=f.read(65536):
                            dst.write(block);h.update(block);count+=len(block)
                            if output.tell()>ZIP_MAX-65536:raise OSError('Export ZIP limit; incomplete file retained')
                    if count!=binding['bytes'] or h.hexdigest()!=binding['sha256']:raise ValueError('Source changed during export')
            if output.tell()>ZIP_MAX:raise OSError('Export ZIP limit')
        return str(target)

    def import_archive(self,source,*,consent=False):
        if consent is not True:raise ValueError('Explicit private import consent required')
        if self.active:raise RuntimeError('Archive owner active; Stop and drain before import')
        source=Path(source).absolute()
        for parent in (source,*source.parents):
            if parent.is_symlink():raise ValueError('Linked import source')
        fd=os.open(source,os.O_RDONLY|os.O_NOFOLLOW)
        with os.fdopen(fd,'rb') as stream:
            st=os.fstat(stream.fileno())
            if not stat.S_ISREG(st.st_mode) or not 0<st.st_size<=ZIP_MAX:raise ValueError('Import ZIP size/type limit')
            with zipfile.ZipFile(stream) as z:
                infos=z.infolist();names=[x.filename for x in infos]
                if len(infos)>129 or len(set(names))!=len(names) or MANIFEST not in names:raise ValueError('Transfer manifest/member count/duplicate')
                total=0
                for info in infos:
                    safe_name(info.filename);kind=stat.S_IFMT(info.external_attr>>16)
                    if kind not in (0,stat.S_IFREG) or info.flag_bits&1 or info.compress_type not in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED):raise ValueError('Unsupported ZIP member type')
                    if info.file_size>FILE_MAX or info.file_size<0:raise ValueError('Member size limit')
                    total+=info.file_size
                if total>TOTAL_MAX+META_MAX or z.getinfo(MANIFEST).file_size>META_MAX:raise ValueError('Total import limit')
                m=strict_json(z.read(MANIFEST));identifier=m.get('identifier')
                if m.get('schema')!=SCHEMA or not isinstance(identifier,str) or not ID.fullmatch(identifier):raise ValueError('Transfer schema/id')
                bindings=m.get('files')
                if not isinstance(bindings,dict) or set(bindings)!=set(names)-{MANIFEST}:raise ValueError('Manifest membership')
                if self.folder(identifier).exists():raise FileExistsError('Conversation ID already exists; import never overwrites')
                for name,binding in bindings.items():
                    if type(binding.get('bytes')) is not int or binding['bytes']!=z.getinfo(name).file_size or not re.fullmatch('[0-9a-f]{64}',str(binding.get('sha256'))):raise ValueError('Manifest size/hash schema')
                self.require_space(total+RECEIPT_RESERVE)
                staging=self.data_root/'.archive-imports'/uuid.uuid4().hex;staging.mkdir(parents=True,exist_ok=False)
                content=staging/'content';content.mkdir()
                receipt=dict(status='VALIDATING',source=str(source),identifier=identifier,source_bytes=st.st_size)
                (staging/MANIFEST).write_text(json.dumps(m,indent=2),encoding='utf-8')
                try:
                    written=0
                    for name,binding in bindings.items():
                        target=content/name;target.parent.mkdir(parents=True,exist_ok=True);h=hashlib.sha256();count=0
                        with z.open(name) as src,target.open('xb') as dst:
                            while block:=src.read(65536):
                                count+=len(block);written+=len(block)
                                if count>binding['bytes'] or written>TOTAL_MAX:raise ValueError('Inflated size limit')
                                self.require_space(len(block)+RECEIPT_RESERVE);dst.write(block);h.update(block)
                        if count!=binding['bytes'] or h.hexdigest()!=binding['sha256']:raise ValueError('Member hash mismatch')
                    now=os.fstat(stream.fileno())
                    if (now.st_dev,now.st_ino,now.st_size,now.st_mtime_ns,now.st_ctime_ns)!=(st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns):raise ValueError('Import source changed')
                    receipt['validation']=validate_folder(content,identifier)
                    self.require_space(RECEIPT_RESERVE)
                    rename_noreplace(content,self.folder(identifier))
                    receipt['status']='PUBLISHED';receipt['files']=bindings
                except BaseException as exc:
                    receipt.update(status='REJECTED_PRESERVED',error=type(exc).__name__+': '+str(exc));raise
                finally:
                    (staging/'RECEIPT.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
        return identifier
