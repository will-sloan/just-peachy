"""One exact copied delete/import capability; README_FIELD_OPERATOR_PARENT_V1.md."""
import ast
import hashlib
import inspect
import os
from pathlib import Path
import threading
from contextlib import contextmanager
from field_live_files_v2 import PhysicalFiles as Base,PathBudgetError,TOKENS
from field_operator_paths_v1 import project
from field_transfer_v2 import sha


def make_class(import_token):
    # Derive only Base's project selection; retain every original guard method.
    source=inspect.getsource(Base.__init__)
    source=__import__('textwrap').dedent(source)
    old='from field_live_paths_v1 import project'
    if source.count(old)!=1:raise ValueError('Physical constructor shape changed')
    source=source.replace(old,'project=transfer_project')
    env=dict(Base.__init__.__globals__)
    env['transfer_project']=lambda **kw:project(**kw,import_token=import_token)
    exec(compile(ast.parse(source),'<transfer-physical-init>','exec'),env)
    init=env['__init__']
    class TransferFiles(Base):
        def __init__(self,*args,**kwargs):
            init(self,*args,**kwargs)
            self.original['rmdir']=os.rmdir
            self.delete_scope=None
            self.delete_attempted=False
            self.import_attempted=False
            self.import_token=import_token
            self.transfer_receipts=[]
        def install(self):
            super().install()
            os.rmdir=self.rmdir
            return self
        @contextmanager
        def allow_copied_delete(self,folder,binding,zip_path):
            folder=self.path(folder)
            expected=self.root/'data/conversations'/self.ids['conversation']
            if folder!=expected or self.delete_attempted or self.failures:
                raise PathBudgetError('One exact healthy copied delete only')
            if not binding.get('readback') or sha(zip_path)!=binding['zip_sha256']:
                raise PathBudgetError('Verified export required before copied delete')
            members={p.relative_to(folder).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p))
                     for p in folder.rglob('*') if p.is_file()}
            if members!=binding['files'] or any(p==folder or folder in p.parents for p in self.fds.values()):
                raise PathBudgetError('Copied delete membership or open file changed')
            directories={p for p in folder.rglob('*') if p.is_dir()}|{folder}
            if any(p.is_symlink() for p in folder.rglob('*')):raise PathBudgetError('Linked copied delete')
            self.delete_attempted=True
            self.delete_scope=dict(thread=threading.get_ident(),files={folder/name for name in members},directories=directories)
            try:
                yield
                if folder.exists() or self.delete_scope['files'] or self.delete_scope['directories']:
                    raise PathBudgetError('Copied delete incomplete')
                self.transfer_receipts.append(dict(action='delete',files=len(members),exact_copy=True,complete=True))
            except BaseException as exc:self.fail(folder,exc);raise
            finally:self.delete_scope=None
        def unlink(self,path,*,dir_fd=None):
            absolute=self.path(path,dir_fd)
            scope=self.delete_scope
            if scope and scope['thread']==threading.get_ident() and absolute in scope['files']:
                self.match(absolute)
                try:
                    with self.internal():self.original['unlink'](absolute)
                    scope['files'].remove(absolute)
                    return
                except BaseException as exc:self.fail(absolute,exc);raise
            return super().unlink(path,dir_fd=dir_fd)
        def rmdir(self,path,*,dir_fd=None):
            absolute=self.path(path,dir_fd);scope=self.delete_scope
            if not scope or scope['thread']!=threading.get_ident() or absolute not in scope['directories']:
                exc=PathBudgetError('Unadmitted directory removal');self.fail(absolute,exc);raise exc
            self.directory(absolute)
            try:
                with self.internal():self.original['rmdir'](absolute)
                scope['directories'].remove(absolute)
            except BaseException as exc:self.fail(absolute,exc);raise
        def publish_import(self,source,target):
            source=self.path(source);target=self.path(target)
            identifier=self.ids['conversation']
            expected=self.root/'data/.archive-imports'/self.import_token/'conversations'/identifier
            destination=self.root/'data/conversations'/identifier
            if self.import_attempted or self.failures or not self.delete_attempted:
                raise PathBudgetError('One import publication after copied deletion only')
            if source!=expected or target!=destination or target.exists():
                raise PathBudgetError('Exact non-replacing import publication required')
            if any(source==p or source in p.parents for p in self.fds.values()):
                raise PathBudgetError('Import writable descriptor still open')
            self.census()
            before={}
            for path in source.rglob('*'):
                if path.is_symlink():raise PathBudgetError('Linked import publication')
                if path.is_file():
                    rel=path.relative_to(source)
                    _,row=self.match(target/rel)
                    if path.stat().st_size>row['maximum_bytes']:raise PathBudgetError('Imported destination cap')
                    before[rel.as_posix()]=dict(bytes=path.stat().st_size,sha256=sha(path))
            if len(before) not in (5,7):raise PathBudgetError('Exact compact import files required')
            self.import_attempted=True
            # Deliberate, narrowly guarded C rename; NOT arbitrary native interception.
            import ctypes
            libc=ctypes.CDLL(None,use_errno=True)
            fn=libc.renameat2
            fn.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint]
            fn.restype=ctypes.c_int
            try:
                if fn(-100,os.fsencode(source),-100,os.fsencode(target),1):
                    error=ctypes.get_errno();raise OSError(error,os.strerror(error),str(target))
                if source.exists():raise PathBudgetError('Import source remains after publication')
                after={p.relative_to(target).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p))
                       for p in target.rglob('*') if p.is_file()}
                if after!=before:raise PathBudgetError('Import publication readback mismatch')
                self.census()
                self.transfer_receipts.append(dict(action='publish_import',files=len(after),exact=True))
            except BaseException as exc:self.fail(target,exc);raise
    return TransferFiles
