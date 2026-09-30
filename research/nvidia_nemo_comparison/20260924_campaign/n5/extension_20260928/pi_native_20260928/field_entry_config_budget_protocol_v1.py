"""Configuration-only publication fixtures; README_FIELD_ENTRY_CONFIG_BUDGET_V1.md."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from field_entry_config_budget_v1 import EntryConfigPublisher, ConfigurationPublicationFailure, MAP, selected_live_config, sha
from field_sidecar_budget_v1 import encoded


def run(root, admission):
    plan = json.loads(Path(admission['plan_path']).read_bytes())
    base = dict(schema='entry-config-budget.v1',scope='configuration-preparation-only',files=admission['entry_files'],
                groups={name:deepcopy(plan['sidecar_groups'][name]) for name in MAP},mapped_names=MAP,
                plan_sha256=sha(admission['plan_path']),maximum_directories=5,directory_byte_ceiling=65536,
                directory_reserve_bytes=5*65536)
    data = Path(admission['data_root']);data.mkdir()
    with (data/'live_config.json').open('xb') as f:f.write((root/'LIVE_CONFIG_BACKUP.json').read_bytes())
    fixtures = Path(admission['fixture_parent']);fixtures.mkdir()
    entry = admission['entry_files']['entry']
    method = selected_live_config(entry['path'],entry['sha256'],admission['prototype'])
    rows = []

    def descriptor(name,value):
        path = root/(name+'-DESCRIPTOR.json')
        with path.open('xb') as f:f.write(encoded(value))
        return path

    for name in ['schema','scope','source-pin','map','directory-count','directory-reserve','group-budget']:
        value = deepcopy(base)
        if name == 'schema':value['extra'] = True
        elif name == 'scope':value['scope'] = 'live'
        elif name == 'source-pin':value['files']['entry']['sha256'] = '0'*64
        elif name == 'map':value['mapped_names']['config'] = 'UNMAPPED.json'
        elif name == 'directory-count':value['maximum_directories'] = 4
        elif name == 'directory-reserve':value['directory_reserve_bytes'] -= 1
        else:value['groups']['config']['maximum_bytes'] += 1
        path = descriptor('reject-'+name,value);destination = fixtures/('reject-'+name)
        try:EntryConfigPublisher(destination,path,sha(path),admission,data,1)
        except ValueError as exc:error = str(exc)
        else:raise AssertionError('Malformed descriptor accepted')
        assert not destination.exists()
        rows.append(dict(case='reject-'+name,error=error,directory_created=False))

    for name in ['mapped-config','bad-factory','boolean-capture','config-byte-cap','boolean-epoch','layout-drift','closure-quota']:
        value = deepcopy(base)
        if name == 'config-byte-cap':value['groups']['config']['maximum_write_bytes'] = 8
        if name == 'closure-quota':value['groups']['closure_reserve']['maximum_write_bytes'] = 8
        path = descriptor(name,value);destination = fixtures/name
        class ObservedPublisher(EntryConfigPublisher):
            observed_input = None
            def publish(self,cfg):
                if name == 'bad-factory':cfg['source_factory'] = 'unbound'
                if name == 'boolean-capture':cfg['capture'] = 1
                self.observed_input = deepcopy(cfg)
                return super().publish(cfg)
            def _layout(self):
                if name == 'layout-drift' and not (self.root/'unexpected').exists():
                    (self.root/'unexpected').mkdir()
                return super()._layout()
        publisher = None;prepared = None;failure = None;error = None
        try:
            publisher = ObservedPublisher(destination,path,sha(path),admission,data,True if name=='boolean-epoch' else 1)
            prepared = method(SimpleNamespace(_entry_config=publisher,data_root=data,epoch=1))
        except ConfigurationPublicationFailure as exc:failure=exc.receipt;error=str(exc)
        except ValueError as exc:error=str(exc)
        if name == 'mapped-config':
            assert error is None and prepared['status']=='CONFIGURATION_PREPARED_NOT_LAUNCHABLE'
            assert prepared['source_factory_integrated'] is False and prepared['capture_started'] is False
            assert prepared['before']['directories']==prepared['after']['directories']==5
            cfg_path=Path(prepared['path']);cfg=json.loads(cfg_path.read_bytes())
            assert cfg==publisher.observed_input and cfg['capture'] is True
            assert cfg['case_directory']==str(destination/'source') and cfg_path.parent==destination/'config'
            assert sha(cfg_path)==prepared['sha256'] and cfg_path.stat().st_size==prepared['bytes']
            before={str(p.relative_to(destination)):sha(p) for p in destination.rglob('*') if p.is_file()}
            try:method(SimpleNamespace(_entry_config=publisher,data_root=data,epoch=1))
            except ValueError as exc:repeat_error=str(exc)
            else:raise AssertionError('Duplicate configuration publication accepted')
            assert 'already attempted' in repeat_error
            assert before=={str(p.relative_to(destination)):sha(p) for p in destination.rglob('*') if p.is_file()}
        else:assert error is not None
        if name in ['bad-factory','boolean-capture','config-byte-cap','boolean-epoch']:
            assert not destination.exists()
        if name == 'layout-drift':
            assert (destination/'unexpected').is_dir() and not (destination/'config/CONFIG.json').exists()
            assert not failure['raw_retained'] and not failure['receipt_retained'] and 'diagnostic_error' in failure
        if name == 'closure-quota':
            assert (destination/'config/CONFIG.json').is_file() and not (destination/'closure_reserve/CONFIG_CLOSURE.json').exists()
            assert failure['configuration_published'] and failure['raw_retained'] and failure['receipt_retained']
            assert (destination/'failure/CONFIG_REJECTED.bin').read_bytes()==(destination/'config/CONFIG.json').read_bytes()
        if publisher is not None and publisher.observed_input is not None:
            with (root/(name+'-INPUT_CONFIG.bin')).open('xb') as f:f.write(encoded(publisher.observed_input))
        rows.append(dict(case=name,prepared=prepared,error=error,failure=failure,
                         input_cfg=None if publisher is None else publisher.observed_input,
                         directory_created=destination.exists(),repeat_error=repeat_error if name=='mapped-config' else None))
    with (root/'ENTRY_CONFIG_CASES.json').open('xb') as f:f.write(encoded(rows))
    assert sha(data/'live_config.json')==admission['data_config_sha256']
    return dict(status='PASS_SELECTED_ENTRY_CONFIG_PUBLICATION_ONLY',cases=len(rows),descriptor_rejections=7,
                configuration_cases=7,configuration_files=2,launchable_objects_returned=0,
                controller_constructors=0,models=False,capture=False,GUI=False,source_audio_samples=0,
                whole_run_integrated=False,policy_changed=False)
