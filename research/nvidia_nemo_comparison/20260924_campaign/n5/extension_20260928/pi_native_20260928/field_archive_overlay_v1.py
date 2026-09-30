"""Retained-file installed overlay; README_FIELD_ARCHIVE_OVERLAY_V1.md."""
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

SCHEMA='just-peachy.retained-archive-overlay.v1'
BUDGET_SHA='d2cc2038e868f93dde009a9403feb259879bba4e8c0a05e760d1e14d087f86f8'
BASE_MANIFEST='274e6de279264f89642e3857c64bf164c699b600cd99e922429020b548bf55f0'

def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def load_module(name,path):
    if name in sys.modules:
        module=sys.modules[name]
        if Path(module.__file__).resolve()!=path.resolve():raise ValueError('Conflicting loaded module: '+name)
        return module
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    try:spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[name]
        raise
    return module

def verify(descriptor,expected_sha):
    descriptor=Path(descriptor).resolve()
    if sha(descriptor)!=expected_sha:raise ValueError('Overlay descriptor changed')
    doc=json.loads(descriptor.read_text())
    if set(doc)!={'schema','base','base_manifest_sha256','base_contract_sha256','entry','entry_sha256','modules','contract','contract_sha256','budget','budget_sha256','budget_canonical_sha256','interchange','capture_enabled'}:
        raise ValueError('Overlay descriptor fields')
    if doc['schema']!=SCHEMA or doc['capture_enabled'] is not False or doc['interchange']!='UNAVAILABLE_IN_OVERLAY':raise ValueError('Overlay scope')
    base=Path(doc['base']);campaign=Path(__file__).resolve().parent.parent
    if base!=campaign/'field-artifact-install-v2/deployment/releases/b01-offline-20260930-v12':raise ValueError('Base release origin')
    if doc['base_manifest_sha256']!=BASE_MANIFEST or sha(base/'RELEASE_MANIFEST.json')!=BASE_MANIFEST:raise ValueError('Base manifest')
    if sha(base/'config/field_contract.json')!=doc['base_contract_sha256']:raise ValueError('Base contract')
    entry=base/'native/field_entry_v5.py'
    if doc['entry']!=str(entry) or sha(entry)!=doc['entry_sha256']:raise ValueError('Entry origin or hash')
    paths={'app.sessions':campaign/'field-archive-finalization-v1/archive_finalization_v1/app/sessions.py',
           'field_archive_budget_v2':campaign/'field-archive-finalization-v1/field_archive_budget_v2.py'}
    if set(doc['modules'])!=set(paths):raise ValueError('Overlay module names')
    for name,path in paths.items():
        row=doc['modules'][name]
        if set(row)!={'path','sha256'} or row['path']!=str(path) or path.is_symlink() or sha(path)!=row['sha256']:
            raise ValueError('Overlay module origin/hash: '+name)
    for kind,rel in [('contract','config/field_contract.json'),('budget','config/archive_budget.json')]:
        p=descriptor.parent/rel
        if doc[kind]!=rel or p.is_symlink() or p.resolve().parent!=descriptor.parent/'config' or sha(p)!=doc[kind+'_sha256']:
            raise ValueError('Overlay '+kind+' binding')
    helper=load_module('field_archive_budget_v2',paths['field_archive_budget_v2'])
    budget=helper.validate(json.loads((descriptor.parent/doc['budget']).read_text()))
    if helper.digest(budget)!=BUDGET_SHA or doc['budget_canonical_sha256']!=BUDGET_SHA:raise ValueError('Exact reserved archive policy required')
    old=json.loads((base/'config/field_contract.json').read_text())
    contract=json.loads((descriptor.parent/doc['contract']).read_text())
    binding=dict(file=doc['budget'],sha256=doc['budget_sha256'],canonical_sha256=BUDGET_SHA)
    if 'archive_budget' in old or contract!={**old,'archive_budget':binding}:raise ValueError('Only reviewed archive-budget contract delta allowed')
    if contract['private_data_quota_bytes']!=512*1024**2 or contract['minimum_free_bytes']!=5*1024**3:raise ValueError('Storage contract')
    return dict(descriptor=doc,base=base,contract=contract,budget=budget,module_paths=paths)

def install_modules(binding):
    base=binding['base']
    sys.path[:0]=[str(base),str(base/'vendor'),str(base/'native')]
    import app
    if Path(app.__file__).resolve()!=base/'app/__init__.py':raise ValueError('Base app package origin')
    sessions=load_module('app.sessions',binding['module_paths']['app.sessions']);app.sessions=sessions
    from native import field_entry_v5 as entry
    from app import paths
    if entry.ROOT.resolve()!=base or paths.ROOT.resolve()!=base:raise ValueError('Installed root changed')
    if Path(entry.__file__).resolve()!=Path(binding['descriptor']['entry']):raise ValueError('Installed entry origin')
    return entry,sessions

def health(descriptor,expected_sha):
    binding=verify(descriptor,expected_sha);entry,_=install_modules(binding)
    original=entry.health()
    return dict(status='RETAINED_ARCHIVE_OVERLAY_HEALTHY',base_health=original['status'],
                base_manifest_sha256=BASE_MANIFEST,descriptor_sha256=expected_sha,
                effective_contract=binding['contract'],archive_budget=binding['budget'],
                module_origins={k:str(v) for k,v in binding['module_paths'].items()},
                capture_enabled=False,models_loaded=False,interchange='UNAVAILABLE_IN_OVERLAY')

def create_controller(descriptor,expected_sha,data):
    # All descriptor/config/module checks precede ApplicationLock or private-data publication.
    binding=verify(descriptor,expected_sha);entry,sessions=install_modules(binding)
    from field_archive_v3 import FieldArchiveStore as InstalledStore
    from field_artifact_limits_v1 import validate as validate_limits
    helper=sys.modules['field_archive_budget_v2']
    contract=binding['contract'];budget=binding['budget'];_,limits=entry.artifact_contract()
    if InstalledStore.__bases__!=(sessions.SessionStore,):raise ValueError('Store imported before overlay')
    base_controller,backend=entry.controller_type()
    class OverlayStore(InstalledStore):
        def __init__(self,data_root,before_publish):
            self.before_publish=before_publish;self.data_root=Path(data_root).resolve();self.contract=contract
            checked=helper.validate(budget);checked_limits=validate_limits(limits)
            sessions.SessionStore.__init__(self,self.data_root,policy=dict(quota_mib=512,free_floor_mib=5120,
                artifact_limits=checked_limits,record_bytes=1024**2,archive_budget=checked))
        def import_archive(self,*args,**kwargs):raise ValueError('Interchange unavailable for this archive overlay')
        def export(self,*args,**kwargs):raise ValueError('Interchange unavailable for this archive overlay')
    class OverlayController(base_controller):
        def _sessions_initialize(self):
            self.session_store=OverlayStore(self.data_root,self._validate_import_projection)
            self.conversation_id=None;self.opened_conversation=None;self.archive=None;self.playback=None
            self.output_choices=[];self.chosen_output=None;self.session_rows=[]
            self.session_listing=[];self.session_usage={};self._refresh_sessions();self.session_annotations={}
        def _artifact_limits_for_epoch(self):
            verify(descriptor,expected_sha)
            if helper.validate(self.session_store.policy.get('archive_budget'))!=budget or self.session_store.archive_budget!=budget:
                raise ValueError('Archive store policy conflicts with overlay contract')
            return super()._artifact_limits_for_epoch()
        def start_live(self,*args,**kwargs):raise RuntimeError('This overlay qualification entry does not admit capture')
        def _start_session(self,*args,**kwargs):raise RuntimeError('This overlay qualification entry does not admit pipeline start')
    controller=OverlayController(data,Path(contract['models_root']),saved_audio_only=True)
    try:
        controller.config=replace(controller.config,asr_threads=1,speaker_threads=1,punctuation_threads=1)
        controller.select_backend(backend);controller.commands.join()
        if controller.error:raise RuntimeError(controller.error)
        controller.switch(mode='open_with_names',recipe='balanced',tap='O0');controller.commands.join()
        if controller.error:raise RuntimeError(controller.error)
    except BaseException:
        if not controller.closed:controller.close()
        controller.commands.join();controller.worker.join(10)
        raise
    return controller
