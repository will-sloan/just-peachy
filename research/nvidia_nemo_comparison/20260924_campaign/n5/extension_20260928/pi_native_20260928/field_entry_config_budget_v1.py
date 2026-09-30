"""Bound configuration preparation; README_FIELD_ENTRY_CONFIG_BUDGET_V1.md."""
import ast
from contextlib import contextmanager
from copy import deepcopy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
from field_sidecar_budget_v1 import GroupWriter, encoded, validate

GROUPS = {'config', 'source', 'failure', 'closure_reserve'}
MAP = {'config': 'CONFIG.json', 'source': 'case_directory',
       'failure': ['CONFIG_FAILURE.json', 'CONFIG_REJECTED.bin'], 'closure_reserve': 'CONFIG_CLOSURE.json'}


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ConfigurationPublicationFailure(RuntimeError):
    def __init__(self, receipt):
        self.receipt = receipt
        super().__init__('CONFIGURATION_PUBLICATION_FAILED')


def validate_descriptor(path, expected, admission):
    if sha(path) != expected: raise ValueError('Entry descriptor hash')
    v = json.loads(Path(path).read_bytes())
    if set(v) != {'schema','scope','files','groups','mapped_names','plan_sha256','maximum_directories','directory_byte_ceiling','directory_reserve_bytes'}:
        raise ValueError('Entry descriptor fields')
    if v['schema'] != 'entry-config-budget.v1' or v['scope'] != 'configuration-preparation-only': raise ValueError('Entry scope')
    if v['files'] != admission['entry_files']: raise ValueError('Entry source pins')
    for row in v['files'].values():
        if sha(row['path']) != row['sha256']: raise ValueError('Entry source changed')
    if v['mapped_names'] != MAP or set(v['groups']) != GROUPS: raise ValueError('Entry map')
    if sha(admission['plan_path']) != v['plan_sha256']: raise ValueError('Entry plan')
    plan = json.loads(Path(admission['plan_path']).read_bytes())
    for name, limits in v['groups'].items():
        validate(limits)
        if any(limits[k] > plan['sidecar_groups'][name][k] for k in limits): raise ValueError('Entry group exceeds plan')
    for k in ['maximum_directories','directory_byte_ceiling','directory_reserve_bytes']:
        if type(v[k]) is not int or v[k] <= 0: raise ValueError('Positive directory limits required')
    if not 5 <= v['maximum_directories'] <= plan['maximum_directories']: raise ValueError('Entry directory count reservation')
    if not 4096 <= v['directory_byte_ceiling'] <= 65536: raise ValueError('Entry directory byte ceiling')
    if not 5*v['directory_byte_ceiling'] <= v['directory_reserve_bytes'] <= plan['filesystem_metadata_reserve_bytes']:
        raise ValueError('Entry directory metadata reservation')
    return v


class EntryConfigPublisher:
    def __init__(self, root, descriptor, expected, admission, data_root, epoch):
        self.v = validate_descriptor(descriptor, expected, admission)
        self.root = Path(root)
        self.data_root = Path(data_root)
        self.epoch = epoch
        self.admission = admission
        self.attempted = False
        self.groups = {}
        self._validate_inputs()

    def _validate_inputs(self):
        if type(self.epoch) is not int or self.epoch < 0: raise ValueError('Entry epoch must be a nonnegative integer')
        if not self.root.is_absolute() or self.root.parent != Path(self.admission['fixture_parent']) or self.root.exists() or self.root.is_symlink():
            raise ValueError('Fresh admitted entry root required')
        if self.data_root != Path(self.admission['data_root']) or sha(self.data_root/'live_config.json') != self.admission['data_config_sha256']:
            raise ValueError('Entry private configuration binding')

    def source_directory(self):
        if self.attempted: raise ValueError('Entry publication already attempted')
        self._validate_inputs()
        return self.root/'source'

    @contextmanager
    def _locked(self):
        fd = os.open(self.root/'.layout.guard', os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW, 0o600)
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_size: raise ValueError('Entry layout guard')
            fcntl.flock(fd, fcntl.LOCK_EX|fcntl.LOCK_NB)
            yield
        finally: os.close(fd)

    def _layout(self):
        entries = list(self.root.iterdir())
        if {p.name for p in entries} != GROUPS|{'.layout.guard'}: raise ValueError('Entry layout membership')
        dirs = [self.root]+[self.root/name for name in sorted(GROUPS)]
        measured = []
        for path in dirs:
            st = path.lstat()
            if not stat.S_ISDIR(st.st_mode): raise ValueError('Entry layout directory type')
            size = max(st.st_size, st.st_blocks*512)
            if size > self.v['directory_byte_ceiling']: raise ValueError('Entry directory extent limit')
            measured.append(size)
        if len(dirs) > self.v['maximum_directories'] or sum(measured) > self.v['directory_reserve_bytes']:
            raise ValueError('Entry directory budget')
        for name, writer in self.groups.items():
            snap = writer.snapshot()
            if snap['bytes'] > writer.budget['maximum_bytes'] or snap['files'] > writer.budget['maximum_files']:
                raise ValueError('Existing entry group over budget')
        return dict(directories=len(dirs), measured_directory_extent_bytes=sum(measured),
                    directory_extent_ceiling_bytes=self.v['directory_byte_ceiling'],
                    reserved_directory_bytes=self.v['directory_reserve_bytes'])

    def publish(self, cfg):
        if self.attempted: raise ValueError('Entry publication already attempted')
        self.attempted = True
        self._validate_inputs()
        prototype = self.admission['prototype']
        expected = dict(source_module='source_quiet_factory_v1',source_factory='create',capture=True,quiet_only=True,
                        prototype=prototype,case_directory=str(self.root/'source'),backpressure_seconds=1,
                        authority=prototype+'/config/AUTONOMOUS_QUIET_AUTHORIZATION_V1.json',
                        alsa_config=prototype+'/config/alsa_hw_only_v1.conf',live_config=str(self.data_root/'live_config.json'))
        if type(cfg) is not dict or cfg != expected or any(type(cfg[k]) is not type(v) for k,v in expected.items()):
            raise ValueError('Entry configuration value/path/type mismatch')
        raw = encoded(cfg)
        budget = self.v['groups']['config']
        if len(raw) > min(budget['maximum_write_bytes'],budget['maximum_file_bytes'],budget['maximum_bytes']):
            raise ValueError('Entry CONFIG exceeds bound before layout')
        self.root.mkdir()
        for name in sorted(GROUPS): (self.root/name).mkdir()
        self.groups = {k:GroupWriter(self.root/k,v) for k,v in self.v['groups'].items()}
        try:
            with self._locked():
                before = self._layout()
                self.groups['config'].write('CONFIG.json',raw)
                after = self._layout()
                result = dict(status='CONFIGURATION_PREPARED_NOT_LAUNCHABLE',path=str(self.root/'config/CONFIG.json'),
                              sha256=sha(self.root/'config/CONFIG.json'),bytes=len(raw),epoch=self.epoch,
                              source_directory=str(self.root/'source'),before=before,after=after,
                              capture_started=False,source_factory_integrated=False)
                self.groups['closure_reserve'].json('CONFIG_CLOSURE.json',result)
                self._layout()
                return result
        except Exception as exc:
            failure = dict(error_type=type(exc).__name__,error=str(exc)[:256],bytes=len(raw),
                           sha256=hashlib.sha256(raw).hexdigest(),raw_retained=False,receipt_retained=False,
                           configuration_published=(self.root/'config/CONFIG.json').exists(),capture_started=False)
            try:
                with self._locked():
                    self._layout()
                    self.groups['failure'].write('CONFIG_REJECTED.bin',raw)
                    failure['raw_retained'] = True
                    self.groups['failure'].json('CONFIG_FAILURE.json',dict(failure,receipt_retained=True))
                    failure['receipt_retained'] = True
            except Exception as secondary: failure['diagnostic_error'] = type(secondary).__name__+': '+str(secondary)[:256]
            # Never retry CONFIG or a rejected closure, nor remove partial evidence.
            raise ConfigurationPublicationFailure(failure) from exc


def selected_live_config(entry_path, expected, prototype):
    if sha(entry_path) != expected: raise ValueError('Installed entry changed')
    tree = ast.parse(Path(entry_path).read_bytes())
    methods = [n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name == '_live_config']
    if len(methods) != 1: raise ValueError('Installed entry method identity')
    method = deepcopy(methods[0])
    assert len(method.body) == 6 and isinstance(method.body[3],ast.Assign) and ast.unparse(method.body[3].targets[0]) == 'cfg'
    assert isinstance(method.body[4],ast.With) and isinstance(method.body[5],ast.Return)
    # Preserve the exact installed config projection. Replace dynamic directory
    # creation/publication and return an explicit preparation receipt only.
    method.body = ast.parse('directory=self._entry_config.source_directory()').body + [method.body[3]] + ast.parse('return self._entry_config.publish(cfg)').body
    ns = {'ROOT':Path(prototype)}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),str(entry_path)+':selected-config','exec'),ns)
    return ns['_live_config']
