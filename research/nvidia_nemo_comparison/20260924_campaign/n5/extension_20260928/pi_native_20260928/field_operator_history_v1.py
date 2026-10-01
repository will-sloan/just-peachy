"""Read-only installed SessionStore history; README_FIELD_OPERATOR_BROKER_V1.md."""
from contextlib import contextmanager
import hashlib
import importlib
import os
from pathlib import Path
import re
import stat
import sys
import threading
from field_transfer_v2 import derive, CAPS
from field_operator_session_ledger_v2 import read, file_pin

_gate=threading.local()
_installed=False

def _audit(event,args):
    if not getattr(_gate,'reading',False):return
    if event=='open':
        mode=args[1];flags=args[2]
        if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):
            raise PermissionError('History read cannot open a writer')
    if event in {'os.mkdir','os.remove','os.rmdir','os.rename','os.link','os.symlink',
                 'os.chmod','os.chown','os.truncate','os.utime','sqlite3.connect',
                 'subprocess.Popen','os.system'}:
        raise PermissionError('History read cannot mutate or launch')

@contextmanager
def reading():
    global _installed
    if not _installed:sys.addaudithook(_audit);_installed=True
    if getattr(_gate,'reading',False):raise RuntimeError('Nested history operation')
    _gate.reading=True
    try:yield
    finally:_gate.reading=False

def census(folder):
    folder=Path(folder)
    for parent in (folder,*folder.parents):
        if parent.is_symlink() or not parent.is_dir():raise ValueError('Real history parents')
    rows={};directories=0
    for base,names,files in os.walk(folder,followlinks=False):
        directories+=1
        if directories>3:raise ValueError('One complete epoch only')
        for name in names:
            p=Path(base)/name
            if p.is_symlink() or not p.is_dir():raise ValueError('History directory link')
        for name in files:
            p=Path(base)/name;relative=p.relative_to(folder).as_posix()
            if name not in CAPS or name=='TRANSFER_MANIFEST.json':raise ValueError('Unknown history member')
            s=p.lstat()
            if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_size>CAPS[name]:
                raise ValueError('History member type or independent maximum')
            rows[relative]=file_pin(p)
            if len(rows)>7:raise ValueError('History member count')
    if len(rows)!=7 or sum(r['bytes'] for r in rows.values())>31*1024**2:
        raise ValueError('Complete bounded seven-member archive required')
    return rows

class History:
    """Uses original installed methods, without a Store/Controller constructor.

    Guards Python I/O on the calling thread; this is not a kernel sandbox or
    arbitrary-native-write protection. Only strict compact archives are accepted.
    """
    def __init__(self,release,manifest_sha256):
        self.release=Path(release).absolute()
        if self.release.is_symlink() or not self.release.is_dir():raise ValueError('Installed release')
        if file_pin(self.release/'RELEASE_MANIFEST.json')['sha256']!=manifest_sha256:
            raise ValueError('Installed manifest drift')
        manifest=read(self.release/'RELEASE_MANIFEST.json',256*1024)
        self.pins={r['path']:r for r in manifest['files']}
        if len(self.pins)!=len(manifest['files']):raise ValueError('Duplicate release member')
        self._verify_release()
        sys.path[:0]=[str(self.release),str(self.release/'vendor'),str(self.release/'native')]
        with reading():
            self.sessions=importlib.import_module('app.sessions')
            if Path(self.sessions.__file__).resolve()!=self.release/'app/sessions.py':
                raise ValueError('Wrong installed SessionStore origin')
            source=self.release/'native/field_archive_v3.py'
            self.transfer=derive(source.read_bytes(),self.pins['native/field_archive_v3.py']['sha256'])
        self._verify_release()

    def _verify_release(self):
        for name,row in self.pins.items():
            p=self.release/name
            if p.is_symlink() or not p.is_relative_to(self.release):
                raise ValueError('Release member path')
            if file_pin(p)!=dict(bytes=row['bytes'],sha256=row['sha256']):
                raise ValueError('Installed source drift')

    def open(self,descriptor):
        if type(descriptor) is not dict or set(descriptor)!={'slot','root','conversation_id','metadata_pin'}:
            raise ValueError('Exact closed-ledger history descriptor')
        identifier=descriptor['conversation_id']
        if not re.fullmatch('[0-9a-f]{32}',identifier):raise ValueError('History identifier')
        data=Path(descriptor['root'])/'data';folder=data/'conversations'/identifier
        with reading():
            before=census(folder)
            if file_pin(folder/'conversation.json')!=descriptor['metadata_pin']:
                raise ValueError('History metadata changed since selection')
            metadata=read(folder/'conversation.json')
            if metadata.get('id')!=identifier or metadata.get('state')!='SAVED' or metadata.get('pinned') is not True:
                raise ValueError('Only closed saved history')
            epochs=metadata.get('epochs')
            if not isinstance(epochs,list) or len(epochs)!=1 or not re.fullmatch('[0-9a-f]{32}',epochs[0]):
                raise ValueError('One exact history epoch')
            epoch=read(folder/'epochs'/epochs[0]/'epoch.json')
            if epoch.get('event_format')!='compact-patch-v1' or not epoch.get('closed') or epoch.get('worker_alive') or epoch.get('archive_error'):
                raise ValueError('No recovery or partial archive in history reader')
            self.transfer.validate_folder(folder,identifier)
            # Original list/rows code; __init__ would invoke recovery and is never called.
            store=self.sessions.SessionStore.__new__(self.sessions.SessionStore)
            store.root=data/'conversations';store.active={};store.policy=dict(self.sessions.POLICY)
            store.lock=threading.RLock()
            listing=store.list()
            selected=[r for r in listing if r['id']==identifier]
            if len(selected)!=1:raise RuntimeError('Installed history list did not find exact recording')
            rows=store.rows(identifier,limit=512)
            if len(rows)>512:raise RuntimeError('History presentation cap')
            after=census(folder)
            if after!=before:raise RuntimeError('History changed during installed consumer read')
        self._verify_release()
        return dict(metadata=selected[0],rows=rows,member_pins=before,
                    capture_started=False,constructor_called=False,read_only=True)
