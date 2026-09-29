"""Withdrawn native Tk/archive check. See README_NATIVE_UI_ARCHIVE_V3.md."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import resource
import shutil
import sys
import threading
import time

for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[key] = '1'
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
os.environ['ORT_DISABLE_TELEMETRY'] = '1'


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    d = Path(__file__).resolve().parent
    a = json.loads((d/'ADMISSION.json').read_text())
    assert datetime.now(timezone.utc) < datetime.fromisoformat(a['expires_utc'])
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip() == a['boot_id']
    assert sorted(os.sched_getaffinity(0)) == [2, 3] and os.getuid() != 0
    assert shutil.disk_usage(d).free >= 5*1024**3
    available = next(int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))
    assert available >= 850*1024**2
    cg = next(x.split(':', 2)[2] for x in Path('/proc/self/cgroup').read_text().splitlines() if x.startswith('0::'))
    quota, period = (Path('/sys/fs/cgroup')/cg.lstrip('/')/'cpu.max').read_text().split()
    assert quota != 'max' and int(quota)/int(period) <= 2
    resource.setrlimit(resource.RLIMIT_AS, (768*1024**2,)*2)
    assert resource.getrlimit(resource.RLIMIT_STACK) == (1048576, 1048576)
    threading.stack_size(1048576)
    for item in a['files']:
        assert sha(Path(item['path'])) == item['sha256'], item['path']
    owner = dict(pid=os.getpid(), start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),
                 boot_id=a['boot_id'], admission_sha256=sha(d/'ADMISSION.json'))
    with (d/'OWNER.json').open('x') as f: json.dump(owner, f)
    result = dict(status='FAILED_PRESERVED', owner=owner, native_CM5=True, inference_run=False,
                  capture=False, playback=False, physical_layout_qualified=False, release_accepted=False, checks=[])
    controller = root = None
    try:
        import tkinter as tk
        # Tk has not processed an idle map at construction. Withdraw immediately,
        # before application construction or any event/idle processing.
        root = tk.Tk(screenName=a['display'])
        root.withdraw()
        root.tk.eval('rename wm jp_original_wm; proc wm {args} {if {[lindex $args 0] eq "deiconify" || ([lindex $args 0] eq "state" && [llength $args] > 2 && [lindex $args 2] ne "withdrawn")} {error "visible windows forbidden in withdrawn check"}; return [uplevel 1 [linsert $args 0 jp_original_wm]]}')
        callback_errors = []
        root.report_callback_exception = lambda kind, value, trace: callback_errors.append(kind.__name__+': '+str(value))
        source = Path(a['prototype']);sys.path[:0] = [str(source), str(source/'vendor')]
        from app.controller import Controller
        from app.ui import PrototypeUI
        controller = Controller(d/'data', Path.home()/'JustPeachy/install/models', saved_audio_only=True)
        ui = PrototypeUI(root, controller, allow_auto_start=False)

        def pump():
            controller.commands.join()
            ui.poll();ui._flush_rows();root.update_idletasks();root.update()
            assert root.state() == 'withdrawn' and not root.winfo_ismapped()
            assert not callback_errors and not ui._notice.startswith('Display update:')
            assert controller.engine is None and controller.playback is None and controller._enroll_live is None
            assert not controller.error, controller.error

        def click(key):
            assert key in ui.actions and ui.actions[key].winfo_exists(), key
            ui.actions[key].invoke();pump();result['checks'].append(key)

        pump()
        ui.show_backends();click('backend_nemotron_hybrid')
        assert controller.backend_id == a['backend_manifest_id']
        ui.show_advanced();click('mode_anonymous_conversation')
        assert controller.mode == 'anonymous_conversation'
        identifier = a['conversation_id'];copy_root = (d/'data/conversations'/identifier).resolve()
        assert copy_root.parent == (d/'data/conversations').resolve()
        before = controller.session_store.metadata(identifier)
        assert not before['pinned']
        ui.show_session(identifier);click('session_pin')
        assert controller.session_store.metadata(identifier)['pinned']
        ui.show_session(identifier);click('session_open')
        opened = controller.snapshot();rows = opened['rows'];assert rows
        ui.home();pump();ui._render_rows(rows, force=True);root.update_idletasks()
        widget_rows = []
        for row in rows:
            rid = str(row['id']);label, caption, selected = ui._row_cache[rid]
            actual = ui.caption_text.get(*ui._marks[rid])
            assert actual == (label+'\n' if label else '')+caption+'\n\n'
            widget_rows.append(dict(id=rid, label=label, caption=caption, actual_text=actual))
        result['widget_rows'] = widget_rows
        result['opened_rows'] = rows
        result['display_rows_count'] = len(rows)
        result['root_state'] = root.state();result['root_mapped'] = bool(root.winfo_ismapped())
        with (d/'OPENED_SNAPSHOT.json').open('x') as f: json.dump(opened, f)
        ui.show_session(identifier);click('session_delete');assert ui.page == 'consent'
        click('cancel');assert copy_root.exists()
        result['delete_cancel_preserves_archive'] = True
        ui.show_session(identifier);click('session_delete');click('confirm')
        assert not copy_root.exists() and not controller.snapshot()['rows']
        assert not controller.snapshot()['sessions']['library']
        result['copied_archive_deleted'] = True
        result['hybrid_model_loads'] = {n:getattr(controller.models,n) for n in ('asr_loads','speaker_loads','streams','enhancer_loads')}
        assert all(v == 0 for v in result['hybrid_model_loads'].values())
        assert all(getattr(controller.models,n) is None for n in ('asr','speakers','diarizer','enhancer'))
        ui.show_backends();click('backend_baseline')
        result['baseline_backend_id'] = controller.backend_id
        result['model_loads'] = {n:getattr(controller.models,n) for n in ('asr_loads','speaker_loads','streams','enhancer_loads')}
        assert all(v == 0 for v in result['model_loads'].values())
        assert controller.models.asr is None and controller.models.speakers is None and controller.models.enhancer is None
        result['punctuation_unloaded_by_asr_absence'] = True
        result['callback_errors'] = callback_errors
        result['status'] = 'WITHDRAWN_TK_ARCHIVE_COLLECTED_REQUIRES_REVIEW'
    except Exception as exc:
        result['error'] = type(exc).__name__+': '+str(exc)
    finally:
        if controller is not None:
            controller.close();controller.commands.join();controller.worker.join(10)
            result['controller_closed'] = controller.closed
            result['controller_worker_closed'] = not controller.worker.is_alive()
        if root is not None:
            try:root.destroy();result['Tk_destroyed'] = True
            except Exception as exc:result['Tk_destroy_error'] = str(exc)
        result['source_archive_unchanged'] = all(sha(Path(x['path']))==x['sha256'] for x in a['source_archive_files'])
        result['peak_rss_bytes'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        result['ended_utc'] = datetime.now(timezone.utc).isoformat()
        with (d/'RESULT.json').open('x') as f:json.dump(result, f, indent=2)
    print(json.dumps({k:v for k,v in result.items() if k not in ('widget_rows','opened_rows')}), flush=True)
    return int(result['status']=='FAILED_PRESERVED')


if __name__ == '__main__':
    raise SystemExit(main())
