"""Copied archive Save/Open plus explicit no-capture UI states. See README_FIELD_POSTRUN_V1.md."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def inventory(root):
    return {p.relative_to(root).as_posix(): sha(p) for p in root.rglob('*') if p.is_file()}


def write(path, value):
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, indent=2, allow_nan=False)


def run(root, a):
    sys.dont_write_bytecode = True
    prior = Path(a['installed_release']); original_archive = Path(a['archive_source'])
    assert inventory(prior) == a['installed_files'] and inventory(original_archive) == a['archive_files']
    source = root / 'source'
    shutil.copytree(prior, source, ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copyfile(root / 'field_caption_state_v1.py', source / 'app/field_caption_state_v1.py')
    shutil.copyfile(root / 'README_FIELD_POSTRUN_V1.md', source / 'docs/README_FIELD_POSTRUN_V1.md')
    code = source / 'app/ui.py'; raw = code.read_text(encoding='utf-8')
    before = '"No selected speech. Use Show all." if strict and rows else "Choose Start when you are ready.")'
    assert raw.count(before) == 1
    signature = '    def _render_rows(self, rows: list[dict[str, Any]], force: bool = False) -> None:\n'
    assert raw.count(signature) == 1
    raw = raw.replace(signature, signature + '        from .field_caption_state_v1 import empty_caption\n')
    raw = raw.replace(before, 'empty_caption(self.snapshot, rows))')
    code.write_text(raw, encoding='utf-8', newline='\n')
    sys.path.insert(0, str(source))
    from release_tools import release
    built = release.build(source, root / 'archives', 'b01-offline-20260930-v6')
    staged = release.stage(built['archive'], root / 'deployment', built['sha256'])
    installed = Path(staged['path'])
    write(root / 'CANDIDATE_BUILD.json', dict(built=built, staged=staged, manifest_sha256=sha(installed / 'RELEASE_MANIFEST.json')))
    sys.path.remove(str(source))
    for name in list(sys.modules):
        if name == 'release_tools' or name.startswith('release_tools.'):
            del sys.modules[name]
    sys.path[:0] = [str(installed), str(installed / 'vendor'), str(installed / 'native')]
    from native import field_entry_v5 as entry
    from app import ui as ui_module
    from field_run_reporting_v1 import model_counters, completed_session
    data = root / 'data'; data.mkdir()
    for name in ('live_config.json', 'n2_runtime.json'):
        shutil.copyfile(Path(a['prior_data']) / name, data / name)
    copied = data / 'conversations' / original_archive.name
    shutil.copytree(original_archive, copied)
    assert inventory(copied) == a['archive_files']
    write(root / 'COPY_BACKUP.json', dict(original=str(original_archive), original_files=a['archive_files'], copied=str(copied), verified=True))
    (data / 'private-preservation-canary').write_bytes(b'PRIVATE_SYNTHETIC_CANARY\n')
    epochs = list((copied / 'epochs').glob('*/epoch.json')); assert len(epochs) == 1
    epoch = json.loads(epochs[0].read_text())
    durable = completed_session(epoch, a['original_session_parent'], 448320)
    rejected = []
    for name, changed in [('early_none', dict(epoch, native_session_path=None)), ('literal_none', dict(epoch, native_session_path='None')),
                          ('wrong_parent', dict(epoch, native_session_path=str(root))), ('incomplete_epoch', dict(epoch, closed=False)),
                          ('wrong_samples', dict(epoch, source_samples=448319))]:
        try:
            completed_session(changed, a['original_session_parent'], 448320)
        except ValueError as exc:
            rejected.append(dict(case=name, error=str(exc)))
        else:
            raise AssertionError('Diagnostic accepted ' + name)
    write(root / 'REPORTING_REJECTIONS.json', rejected)
    write(root / 'GUI_LAUNCH.json', dict(release_manifest_sha256=sha(installed / 'RELEASE_MANIFEST.json'),
          autonomous_quiet_authorized=True, expires_unix=time.time()+120, data_root=str(data.resolve()),
          scope='NO CAPTURE: copied archive and explicitly simulated UI snapshots only'))
    original_ui = ui_module.PrototypeUI; holder = {}; errors = []; steps = []; actions = []; observations = []
    started = time.monotonic(); identifier = original_archive.name

    def ui(): return holder['ui']

    def sync():
        c = ui().controller; c.commands.join()
        assert not c.error, c.error
        assert c.engine is None and c.archive is None and c.playback is None
        counts = model_counters(c.models)
        assert counts['asr_loads']['value'] == counts['speaker_loads']['value'] == 0
        assert counts['punctuation_loads'] == dict(available=False, value=None)
        assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip() == 'closed'
        assert not (data / 'source_receipts').exists()
        assert not any(Path(data / 'sessions').glob('*'))
        ui().snapshot = c.snapshot()
        return counts

    def invoke(key):
        b = ui().actions[key]; assert b.winfo_exists() and str(b.cget('state')) == 'normal'; b.invoke()

    def open_archive():
        sync(); ui().show_session(identifier); invoke('session_open'); sync()
        assert ui().snapshot['state'] == 'STOPPED' and ui().snapshot['sessions']['opened_id'] == identifier
        assert ui().snapshot['rows'] == []  # This retained quiet recording has no caption rows.
        write(root / 'FIRST_OPEN_SNAPSHOT.json', ui().snapshot)

    def save_archive():
        sync(); ui().show_session(identifier); invoke('session_pin'); sync()
        assert ui().controller.session_store.metadata(identifier)['pinned']

    def reopen_archive():
        sync(); ui().show_session(identifier); invoke('session_open'); sync()
        first = json.loads((root / 'FIRST_OPEN_SNAPSHOT.json').read_text())
        assert ui().snapshot['rows'] == first['rows'] == []
        assert ui().snapshot['sessions']['caption_links'] == first['sessions']['caption_links'] == []
        write(root / 'OPENED_SNAPSHOT.json', ui().snapshot)
        ui().home(); ui()._render_rows([], force=True)

    def photograph(name, expected, fixture=False):
        u = ui(); u.root.update_idletasks()
        assert u.root.winfo_viewable() and (u.root.winfo_width(), u.root.winfo_height()) == (480, 800)
        text = u.active_text.get('1.0', 'end-1c'); assert expected in text, (name, text)
        path = root / (name+'.png'); subprocess.run(['grim', str(path)], check=True, timeout=10)
        observations.append(dict(name=name, sha256=sha(path), width=480, height=800, text=text, no_capture_fixture=fixture))

    def fixture(state, expected):
        sync(); u = ui()
        # Only the UI view is simulated. Controller, models and hardware stay idle.
        if u._poll_handle:
            u.root.after_cancel(u._poll_handle); u._poll_handle = None
        if u._display_handle:
            u.root.after_cancel(u._display_handle); u._display_handle = None
        u.snapshot = copy.deepcopy(u.controller.snapshot())
        u.snapshot.update(state=state, status='No-capture UI state fixture: '+state)
        u.snapshot['sessions']['opened_id'] = None
        u.home(); u._show_status(); u._render_rows([], force=True)
        assert expected in u.active_text.get('1.0', 'end-1c')

    def stopped_again():
        sync(); ui().home(); ui()._render_rows([], force=True); ui().poll()

    def failed(exc):
        import traceback
        errors.append(type(exc).__name__+': '+str(exc))
        (root / 'CALLBACK_FAILURE.txt').write_text(traceback.format_exc())
        ui().close()

    def advance():
        try:
            if time.monotonic()-started > 60: raise TimeoutError('Post-run UI wall bound')
            if not steps:
                sync(); ui().close(); return
            name, fn = steps.pop(0); fn(); actions.append(dict(action=name, complete=True))
            write(root / ('ACTION_%02d.json' % len(actions)), actions[-1])
            ui().root.after(600, advance)
        except Exception as exc:
            failed(exc)

    class ScheduledUI(original_ui):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs); holder['ui'] = self
            self.root.report_callback_exception = lambda kind, value, tb: failed(value)
            self.root.after(650, advance)

    steps.extend([('actual_GUI_open_private_copy', open_archive), ('actual_GUI_Save_pin', save_archive),
                  ('actual_GUI_reopen', reopen_archive),
                  ('visible_saved_stopped', lambda: photograph('stopped-saved', 'No captions in this saved conversation.'))])
    for state, expected in [('STARTING', 'Starting microphone…'), ('RUNNING', 'Listening for speech…'),
                            ('STOPPING', 'Finishing this recording…')]:
        steps.append(('no_capture_'+state, lambda s=state, e=expected: fixture(s,e)))
        steps.append(('visible_fixture_'+state, lambda s=state, e=expected: photograph('fixture-'+s.lower(),e,True)))
    steps.append(('restore_actual_stopped_view', stopped_again))
    steps.append(('visible_actual_stopped_again', lambda: photograph('stopped-final', 'No captions in this saved conversation.')))
    ui_module.PrototypeUI = ScheduledUI; argv = sys.argv[:]
    try:
        sys.argv = [str(installed/'main.py'), 'gui', '--data-root', str(data), '--launch-admission', str(root/'GUI_LAUNCH.json')]
        code = entry.main()
    finally:
        sys.argv = argv; ui_module.PrototypeUI = original_ui
    if errors: raise RuntimeError('; '.join(errors))
    assert code == 0 and not steps and ui().controller.closed and not ui().controller.worker.is_alive()
    assert inventory(prior) == a['installed_files'] and inventory(original_archive) == a['archive_files']
    after = inventory(copied)
    assert [name for name in after if after[name] != a['archive_files'][name]] == ['conversation.json']
    assert set(after) == set(a['archive_files'])
    before_meta = json.loads((original_archive/'conversation.json').read_text()); after_meta = json.loads((copied/'conversation.json').read_text())
    assert after_meta['pinned'] is True
    assert {k:v for k,v in before_meta.items() if k not in ('pinned','updated_utc','state')} == {k:v for k,v in after_meta.items() if k not in ('pinned','updated_utc','state')}
    counts = model_counters(ui().controller.models)
    write(root / 'MODEL_COUNTERS.json', counts)
    result = dict(status='PASS_INSTALLED_COPIED_QUIET_ARCHIVE_SAVE_OPEN_AND_UI_STATES_ONLY', installed_release=str(installed),
                  observations=observations, actions=actions, source_unchanged=True, prior_release_unchanged=True,
                  controller_closed=True, model_loads=0, capture_opened=False, physical_touch=False, field_release_accepted=False,
                  optional_counters=counts, diagnostic_rejections=rejected, durable_original_session=durable,
                  samples=448320, reopened_rows=0, copied_files=after, installed_hashes=inventory(installed))
    write(root/'POSTRUN_RESULT.json', result)
    return result
