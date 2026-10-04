"""Exact owned idle GUI policy inspection; README_PRODUCTION_IDLE_V2.md."""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time


def raw_json(path, maximum=262144):
    path=Path(path)
    if path.is_symlink() or path.resolve(strict=True)!=path or path.stat().st_size>maximum:
        raise ValueError('Bounded canonical idle receipt required')
    raw=path.read_bytes()
    if len(raw)>maximum:raise ValueError('Idle receipt grew')
    return json.loads(raw)


def identity(pid):
    try:ticks=int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None
    return dict(pid=pid,start_ticks=ticks,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())


def put(path,value):
    raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    if len(raw)>262144:raise ValueError('Idle receipt cap')
    with path.open('xb') as stream:
        if stream.write(raw)!=len(raw):raise OSError('Short idle receipt')
        stream.flush();os.fsync(stream.fileno())
    if path.read_bytes()!=raw:raise OSError('Idle receipt readback differs')
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def scope_module(request):
    import importlib.util
    path=Path(request['package'])/'native_scope.py'
    if path.resolve(strict=True)!=path or hashlib.sha256(path.read_bytes()).hexdigest()!=request['scope_sha256']:
        raise ValueError('Exact unchanged native_scope required')
    spec=importlib.util.spec_from_file_location('verified_idle_scope',path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    return module


def unchanged_state(request):
    """Read only the exact fresh-baseline settings, ALSA status and display."""
    files=[]
    for pin in request['unchanged_files']:
        path=Path(pin['path']);before=path.lstat()
        if (path.resolve(strict=True)!=path or not stat.S_ISREG(before.st_mode)
                or before.st_nlink!=1 or not 0<=before.st_size<=65536):
            raise ValueError('Canonical bounded settings file required')
        raw=path.read_bytes();after=path.lstat()
        if ((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)
                !=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)):
            raise ValueError('Settings changed during readback')
        value=dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        if value!=pin:raise ValueError('Fresh-baseline settings or desktop changed: '+str(path))
        if path.name=='just-peachy.desktop' and '/autostart/' in str(path):
            lines=raw.decode('utf-8').splitlines()
            if lines.count('Hidden=true')!=1 or lines.count('X-GNOME-Autostart-enabled=false')!=1:
                raise ValueError('Autostart must remain explicitly disabled')
        files.append(value)
    capture={}
    for name,value in request['capture_status'].items():
        current=Path(name).read_text().strip()
        if value!='closed' or current!=value:raise ValueError('Baseline capture device is not closed')
        capture[name]=current
    shown=subprocess.run(['wlr-randr'],capture_output=True,text=True,timeout=8)
    if len(shown.stdout)+len(shown.stderr)>32768:raise ValueError('Display readback cap')
    display=dict(returncode=shown.returncode,stdout=shown.stdout,stderr=shown.stderr)
    digest=hashlib.sha256(shown.stdout.encode('utf-8')).hexdigest()
    if (shown.returncode or 'Enabled: yes' not in shown.stdout or 'Transform: 270' not in shown.stdout
            or digest!=request['display_stdout_sha256']):
        raise ValueError('Fresh-baseline display270 changed')
    return dict(files=files,capture_status=capture,display=display,display_stdout_sha256=digest,
        autostart_disabled=True,settings_unchanged=True,desktop_unchanged=True,display_mutated=False)


def nested_registration(request):
    """Only the sole new native_scope owner tree under the prechecked empty root."""
    base=Path(request['data_root']);owners=base/'unit-owners'
    if not owners.exists():return None
    folders=list(owners.iterdir())
    if len(folders)>1:raise ValueError('Expected one fresh production native_scope owner tree')
    if not folders:return None
    root=folders[0]
    if root.resolve(strict=True)!=root or root.is_symlink() or not root.is_dir():raise ValueError('Canonical nested owner tree')
    if not (root/'SERVICE_REQUEST.json').exists():return None
    launch=raw_json(root/'SERVICE_REQUEST.json');owner=raw_json(root/'REGISTERED_OWNER.json')
    if launch['owner']!=owner or owner['boot_id']!=request['boot_id']:
        raise ValueError('Nested outside owner differs')
    if not (root/'UNIT_OWNERSHIP.json').exists():return dict(root=root,owner=owner,launch=launch,receipt=None)
    receipt=raw_json(root/'UNIT_OWNERSHIP.json')
    if (receipt['unit']!=launch['unit'] or receipt['runtime_max_seconds']!=7200
            or receipt['owner']!=raw_json(root/'main/REGISTERED_OWNER.json')):
        raise ValueError('Actual standard production7200-second nested unit differs')
    return dict(root=root,owner=owner,launch=launch,receipt=receipt)


def exact_unit(scope,receipt):
    state=scope.properties(receipt['unit'])
    if (state.get('InvocationID') and state['InvocationID']!=receipt['invocation_id']
            or state.get('ControlGroup') and state['ControlGroup']!=receipt['control_group']):
        raise ValueError('Exact nested unit identity changed')
    return state


def close_owned_nested(scope,registration,deadline):
    """Signals only the authenticated unique unit; PIDs are never guessed."""
    if registration is None:return dict(unit_observed=False,closed=True)
    receipt=registration['receipt']
    if receipt is None:
        raise RuntimeError('Nested service has no acknowledged ownership receipt; closure cannot be certified')
    state=exact_unit(scope,receipt);forced=False
    if scope.alive(receipt['owner']) or not scope.cgroup_empty(receipt['control_group']):
        forced=True
        subprocess.run(['systemctl','--user','kill','--kill-whom=all','--signal=TERM',receipt['unit']],capture_output=True,timeout=5)
        until=min(deadline,time.monotonic()+5)
        while time.monotonic()<until and not scope.cgroup_empty(receipt['control_group']):time.sleep(.1)
        if not scope.cgroup_empty(receipt['control_group']):
            exact_unit(scope,receipt)
            subprocess.run(['systemctl','--user','kill','--kill-whom=all','--signal=KILL',receipt['unit']],capture_output=True,timeout=5)
    state=exact_unit(scope,receipt)
    return dict(unit_observed=True,unit=receipt['unit'],ownership=receipt,forced=forced,
        main_exact_owner_gone=not scope.alive(receipt['owner']),cgroup_empty=scope.cgroup_empty(receipt['control_group']),
        closed=not scope.alive(receipt['owner']) and scope.cgroup_empty(receipt['control_group']),properties=state)


def watchdog(out):
    import resource
    os.sched_setaffinity(0,{3})
    for kind,cap in ((resource.RLIMIT_AS,128*1024**2),(resource.RLIMIT_STACK,1024**2),(resource.RLIMIT_FSIZE,32*1024**2)):
        resource.setrlimit(kind,(cap,cap))
    directory=out/'watchdog';directory.mkdir()
    owner=identity(os.getpid());put(directory/'OWNER.json',owner)  # Before request/package reads.
    request=raw_json(out/'IDLE_REQUEST.json');request.update(raw_json(out/'DEADLINE.json'));scope=scope_module(request)
    state=scope.properties(request['watchdog_unit'])
    if state['MainPID']!=str(owner['pid']) or state['InvocationID']!=os.environ.get('INVOCATION_ID'):
        raise ValueError('Actual independent watchdog ownership differs')
    put(directory/'UNIT_OWNERSHIP.json',dict(unit=request['watchdog_unit'],invocation_id=state['InvocationID'],
        control_group=state['ControlGroup'],owner=owner,main_pid=owner['pid'],runtime_max_seconds=120))
    result=None;error=None
    try:
        while time.monotonic()<request['deadline_monotonic'] and not (out/'CONTROL_COMPLETE.json').exists():time.sleep(.1)
        registration=nested_registration(request)
        result=close_owned_nested(scope,registration,request['deadline_monotonic']+10)
        if not result['closed']:raise RuntimeError('Nested GUI did not close')
    except BaseException as exc:error=repr(exc)
    put(directory/'WATCHDOG_EXIT.json',dict(owner=owner,result=result,error=error,control_complete=(out/'CONTROL_COMPLETE.json').exists()))
    if error:raise RuntimeError(error)


def inspect_optional_policy(send, splitlist, start):
    """Inspect real controls only; never invoke Start or construct a worker."""
    checks = 0
    def checked(*args):
        nonlocal checks
        if not int(send(start, 'instate', 'disabled')):
            raise ValueError('Start must remain disabled throughout policy inspection')
        result = send(*args)
        if not int(send(start, 'instate', 'disabled')):
            raise ValueError('A policy control enabled Start unexpectedly')
        checks += 1
        return result
    def unique(values, description):
        if len(values) != 1: raise ValueError('Unique actual '+description+' control required')
        return values[0]
    todo = ['.']; widgets = []
    while todo:
        widget = todo.pop()
        if len(widgets) >= 512: raise ValueError('Bounded actual policy widget census')
        widgets.append((widget, str(checked('winfo', 'class', widget))))
        todo.extend(splitlist(checked('winfo', 'children', widget)))
    combos = [(w, tuple(splitlist(checked(w, 'cget', '-values')))) for w, kind in widgets if kind == 'TCombobox']
    def combo(values): return unique([w for w, actual in combos if actual == values], 'selection')
    diarizer = combo(('pyannote', 'nemotron'))
    embedding = combo(('redimnet', 'titanet', 'anonymous'))
    source = combo(('live', 'saved'))
    checkboxes = [(w, str(checked(w, 'cget', '-text'))) for w, kind in widgets if kind == 'TCheckbutton']
    experimental = unique([w for w, text in checkboxes if text == 'Enable experimental configurations'], 'experimental')
    optional = unique([w for w, text in checkboxes if text.startswith('Optional anonymous CurrentDelayed refiner:')], 'optional')
    labels = [(w, str(checked(w, 'cget', '-text'))) for w, kind in widgets if kind == 'TLabel']
    label = unique([w for w, text in labels if text == 'Label revision window in seconds (1-300)'], 'revision label')
    siblings = list(splitlist(checked('winfo', 'children', checked('winfo', 'parent', label))))
    index = siblings.index(label)
    if index+1 >= len(siblings): raise ValueError('Actual revision entry missing')
    revision = siblings[index+1]
    if checked('winfo', 'class', revision) != 'TEntry': raise ValueError('Actual adjacent revision entry required')
    def value(widget): return str(checked('set', checked(widget, 'cget', '-variable')))
    def summaries():
        result = []
        for widget, _ in labels:
            variable = checked(widget, 'cget', '-textvariable')
            if variable: result.append(str(checked('set', variable)))
        return result
    ordinary = 'Source 300 s; load 120 s; drain 120 s; backlog 120 s; cleanup 60 s.'
    reviewed = 'Source 300 s; load 120 s; drain 60 s; backlog 30 s; cleanup 60 s.'
    if ordinary not in summaries() or value(experimental) != '0' or value(optional) != '0':
        raise ValueError('Actual ordinary idle defaults required before inspection')
    for widget, selected in ((diarizer, 'pyannote'), (embedding, 'titanet'), (source, 'live')):
        checked(widget, 'set', selected)
        if checked(widget, 'get') != selected: raise ValueError('Actual selection did not persist')
    checked(experimental, 'invoke')
    if value(experimental) != '1' or int(checked(revision, 'instate', 'disabled')):
        raise ValueError('Experimental Pyannote must expose revision before optional selection')
    checked('set', checked(revision, 'cget', '-textvariable'), '60')
    if str(checked(revision, 'get')) != '60' or int(checked(optional, 'instate', 'disabled')):
        raise ValueError('Exact window60 optional admission is unavailable')
    checked(optional, 'invoke')
    if value(optional) != '1' or reviewed not in summaries():
        raise ValueError('Actual checked optional policy differs from reviewed300/60/30')
    checked(optional, 'invoke')
    if value(optional) != '0' or ordinary not in summaries():
        raise ValueError('Unchecked optional must restore unchanged ordinary defaults')
    return dict(schema='just-peachy.production-idle-optional-policy.v1',
        actual_controls=True, selection=dict(diarizer='pyannote', embedding='titanet', input_source='live',
            allow_experimental=True, revision_window_seconds=60),
        optional_enabled=True, checked_policy_summary=reviewed, unchecked_policy_summary=ordinary,
        optional_final_checked=False, start_disabled_checks=checks, start_invocations=0,
        worker_constructed=False, source_capture_started=False)


def _main(out):
    import shlex
    import signal
    request=raw_json(out/'IDLE_REQUEST.json');scope=scope_module(request)
    request['deadline_monotonic']=time.monotonic()+90
    # Both processes consume exactly this immutable fresh deadline.
    put(out/'DEADLINE.json',dict(deadline_monotonic=request['deadline_monotonic']))
    # IDLE_REQUEST lacks a runtime clock before this main is registered. The
    # watchdog reads the separate DEADLINE and cannot extend the deadline.
    unit=request['watchdog_unit']
    command=['systemd-run','--user','--unit='+unit,'--description=JustPeachyIndependentIdleWatchdog',
        '--property=AllowedCPUs=3','--property=CPUQuota=100%','--property=TasksMax=16',
        '--property=RuntimeMaxSec=120','--property=TimeoutStopSec=10','--property=KillMode=control-group',
        '--setenv=PYTHONDONTWRITEBYTECODE=1',request['command'][0],'-B',str(out/'idle_control.py'),'--watchdog',str(out)]
    started=subprocess.run(command,capture_output=True,text=True,timeout=10)
    put(out/'WATCHDOG_START.json',dict(returncode=started.returncode,stdout=started.stdout[:4096],stderr=started.stderr[:4096]))
    if started.returncode:raise RuntimeError('Independent90-second watchdog did not start')
    wait_until=time.monotonic()+10
    while not (out/'watchdog/UNIT_OWNERSHIP.json').exists():
        if time.monotonic()>wait_until:raise TimeoutError('Independent watchdog owner registration')
        time.sleep(.05)
    watcher=raw_json(out/'watchdog/UNIT_OWNERSHIP.json');exact_unit(scope,watcher)
    if identity(watcher['owner']['pid'])!=watcher['owner']:raise ValueError('Watchdog exact owner changed')
    desktop=Path(request['desktop'])
    if hashlib.sha256(desktop.read_bytes()).hexdigest()!=request['desktop_sha256']:raise ValueError('Desktop changed before actual Exec')
    state_before=unchanged_state(request);put(out/'STATE_BEFORE.json',state_before)
    import tkinter as tk
    control=tk.Tk();control.withdraw();control.tk.call('tk','appname','jp_v29_idle_'+str(os.getpid()))
    stdout=(out/'NATIVE_SCOPE.stdout').open('xb');stderr=(out/'NATIVE_SCOPE.stderr').open('xb')
    process=None;registration=None;failure=None;geometry=[];exit_invoked=0;exit_attempts=0
    exit_reply_error=None;normal_exit_observed=False;start_disabled=False;state_after=None;policy_check=None
    try:
        base=Path(request['data_root'])
        if base.exists() and (not base.is_dir() or next(base.iterdir(),None) is not None):
            raise ValueError('Default production data appeared before exact desktop Exec; preserve it')
        process=subprocess.Popen(request['command'],stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr)
        outside=identity(process.pid)
        if outside is None:raise RuntimeError('Native_scope exited before ownership could be observed')
        put(out/'NATIVE_SCOPE_CHILD_REFERENCE.json',dict(schema='just-peachy.owned-exec-reference.v1',
            child=outside,command=request['command'],desktop_sha256=request['desktop_sha256'],new_identity=False))
        while time.monotonic()<request['deadline_monotonic']-15:
            registration=nested_registration(request)
            if registration and registration['receipt']:break
            if process.poll() is not None:raise RuntimeError('Actual native_scope exited before GUI registration')
            time.sleep(.1)
        if not registration or not registration['receipt']:raise TimeoutError('Nested production ownership did not arrive')
        if registration['owner']!=outside:raise ValueError('Actual desktop Exec outside owner differs')
        receipt=registration['receipt'];state=exact_unit(scope,receipt)
        if (state['MainPID']!=str(receipt['owner']['pid']) or identity(receipt['owner']['pid'])!=receipt['owner']
                or scope.duration_seconds(state['RuntimeMaxUSec'])!=7200):raise ValueError('Actual production GUI owner/envelope differs')
        if not any(line.endswith(':'+receipt['control_group']) for line in Path('/proc',str(receipt['owner']['pid']),'cgroup').read_text().splitlines()):
            raise ValueError('Actual GUI process cgroup differs from registered ownership')
        app=None
        while time.monotonic()<request['deadline_monotonic']-15 and app is None:
            interps=control.tk.splitlist(control.tk.call('winfo','interps'))
            if len(interps)>64:raise ValueError('Finite Tk interpreter census')
            matches=[]
            for candidate in interps:
                try:pid=int(control.tk.call('send',candidate,'pid'))
                except tk.TclError:continue
                if pid==receipt['owner']['pid']:matches.append(candidate)
            if len(matches)>1:raise ValueError('Unique actual GUI Tcl interpreter required')
            if matches:app=matches[0]
            else:time.sleep(.1)
        if app is None:raise TimeoutError('Tcl-send did not find the exact actual GUI PID')
        def send(*args):
            if identity(receipt['owner']['pid'])!=receipt['owner']:raise ValueError('GUI identity changed before Tk command')
            if int(control.tk.call('send',app,'pid'))!=receipt['owner']['pid']:raise ValueError('Tk interpreter PID changed')
            return control.tk.call('send',app,control.tk.call('list',*args))
        todo=['.'];buttons=[];visited=0
        while todo:
            widget=todo.pop();visited+=1
            if visited>512:raise ValueError('Bounded actual widget census')
            if send('winfo','class',widget) in ('Button','TButton'):
                text=str(send(widget,'cget','-text'))
                if text in ('Start','Exit to desktop'):buttons.append((widget,text))
            todo.extend(control.tk.splitlist(send('winfo','children',widget)))
        start=[w for w,text in buttons if text=='Start'];exit_buttons=[w for w,text in buttons if text=='Exit to desktop']
        if len(start)!=1 or len(exit_buttons)!=1:raise ValueError('Exact real Start/Exit controls required')
        send(start[0],'state','disabled');start_disabled=True
        while len(geometry)<10 and time.monotonic()<request['deadline_monotonic']-15:
            extent=tuple(int(send('winfo',name,'.')) for name in ('width','height','rootx','rooty'))
            fullscreen=int(send('wm','attributes','.','-fullscreen'))
            if extent==(480,800,0,0) and fullscreen:geometry.append(dict(extent=extent,fullscreen=True))
            else:geometry=[]
            time.sleep(.1)
        if len(geometry)!=10:raise ValueError('Ten stable production fullscreen geometries required')
        policy_check=inspect_optional_policy(send,control.tk.splitlist,start[0])
        put(out/'OPTIONAL_POLICY_GUI_CHECK.json',policy_check)
        time.sleep(5)
        if list((Path(request['data_root'])/'launches').iterdir()):raise RuntimeError('Idle launcher unexpectedly created worker records')
        if not int(send(start[0],'instate','disabled')):raise ValueError('Start must remain disabled before Exit')
        exit_attempts=1
        try:
            send(exit_buttons[0],'invoke');exit_invoked=1
        except tk.TclError as exc:
            # A genuine root.destroy can remove the remote interpreter before
            # Tcl delivers a reply. An attempted request is never closure proof.
            exit_reply_error=str(exc)[:2048]
        process.wait(timeout=max(1,min(15,request['deadline_monotonic']-time.monotonic())))
        if process.returncode:raise RuntimeError('Actual production native_scope did not exit successfully')
        closure=raw_json(registration['root']/'UNIT_CLOSURE.json')
        if (not closure['unit_stopped'] or not closure['main_exact_owner_gone'] or not closure['all_registered_source_owners_gone']
                or closure['sources'] or closure['service_exit']['exit_code']!=0 or closure['service_exit']['error']):
            raise ValueError('Actual nested production closure failed')
        nested=close_owned_nested(scope,registration,request['deadline_monotonic'])
        if not nested['closed'] or nested['forced']:raise RuntimeError('Normal Exit did not close exact nested service')
        normal_exit_observed=True
        state_after=unchanged_state(request);put(out/'STATE_AFTER.json',state_after)
        put(out/'CONTROL_COMPLETE.json',dict(nested=nested,native_scope_outside_gone=identity(outside['pid'])!=outside))
    except BaseException as exc:
        failure=repr(exc)
        try:
            registration=nested_registration(request)
            nested=close_owned_nested(scope,registration,request['deadline_monotonic']+10)
            put(out/'CONTROL_FAILURE_CLEANUP.json',dict(nested=nested,error=failure))
        except BaseException as cleanup:put(out/'CONTROL_FAILURE_CLEANUP.json',dict(error=failure,cleanup_error=repr(cleanup)))
    finally:
        control.destroy()
        if process is not None and process.poll() is None:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
        stdout.close();stderr.close()
    until=request['deadline_monotonic']+15
    while time.monotonic()<until and (scope.alive(watcher['owner']) or not scope.cgroup_empty(watcher['control_group'])):time.sleep(.1)
    watcher_closed=not scope.alive(watcher['owner']) and scope.cgroup_empty(watcher['control_group'])
    watcher_final=exact_unit(scope,watcher)
    put(out/'WATCHDOG_CLOSURE.json',dict(ownership=watcher,exact_owner_gone=not scope.alive(watcher['owner']),
        cgroup_empty=scope.cgroup_empty(watcher['control_group']),properties=watcher_final))
    watchdog_exit=raw_json(out/'watchdog/WATCHDOG_EXIT.json') if (out/'watchdog/WATCHDOG_EXIT.json').exists() else None
    if not watcher_closed or not watchdog_exit or watchdog_exit['error']:failure=failure or 'Independent watchdog closure failed'
    copied=[];total=0;walked=0;base=Path(request['data_root']);mirror=out/'production-data-readback';mirror.mkdir()
    nested_closed=bool(registration and registration['receipt'] and not scope.alive(registration['receipt']['owner'])
        and scope.cgroup_empty(registration['receipt']['control_group']))
    worker_records=len(list((base/'launches').iterdir())) if (base/'launches').is_dir() else None
    if worker_records:failure=failure or 'Unexpected worker records exist'
    if base.exists() and nested_closed:
        for directory,children,files in os.walk(base,followlinks=False):
            walked+=1+len(children)+len(files)
            if walked>128:raise ValueError('Idle metadata membership cap')
            for name in children:
                if (Path(directory)/name).is_symlink():raise ValueError('Idle metadata symlink')
            for name in files:
                path=Path(directory)/name;before=path.lstat();total+=before.st_size
                if path.is_symlink() or before.st_nlink!=1 or before.st_size>1024**2 or total>4*1024**2:
                    raise ValueError('Only bounded single-link idle metadata may be copied')
                raw=path.read_bytes();target=mirror/path.relative_to(base);target.parent.mkdir(parents=True,exist_ok=True)
                with target.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
                if target.read_bytes()!=raw:raise OSError('Independent production metadata readback')
                copied.append(dict(path=path.relative_to(base).as_posix(),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    passed=not failure and nested_closed and worker_records==0 and exit_attempts==1 and normal_exit_observed and len(geometry)==10 and state_after==state_before and policy_check is not None
    put(out/'PRODUCTION_IDLE_RESULT.json',dict(schema='just-peachy.production-idle-ui.v3',functional_success=passed,
        optional_policy_gui_check=policy_check,
        actual_desktop_exec=True,actual_native_scope_outer_executed=True,actual_native_scope_inside_executed=True,
        production_scope_runtime_seconds=7200,independent_watchdog_seconds=90,geometry_samples=geometry,
        exact_gui_interpreter_pid=registration['receipt']['owner']['pid'] if registration and registration['receipt'] else None,
        exit_invocation_attempts=exit_attempts,exit_successful_replies=exit_invoked,exit_reply_error=exit_reply_error,
        normal_exit_observed=normal_exit_observed,start_disabled_by_driver=start_disabled,worker_records_created=worker_records,
        source_capture_started=False if worker_records==0 else None,models_constructed=False if worker_records==0 else None,default_production_data_root=True,
        desktop_double_click_tested=False,physical_touch_qualified=False,watchdog_closed=watcher_closed,
        fresh_baseline_sha256=request['baseline_sha256'],unchanged_state_before=state_before,
        unchanged_state_after=state_after,current_desktop_after_normal_exit=next((pin for pin in (state_after or {}).get('files',[]) if pin['path']==request['desktop']),None),
        copied_metadata=copied,copied_bytes=total,failure=failure))
    if not passed:raise RuntimeError('Production desktop Exec idle/Exit check failed: '+str(failure))


def main(out):
    try:return _main(out)
    except BaseException as exc:
        # A Tcl initialization/registration failure must not end the outer job
        # while the separately armed watchdog still owns nested cleanup.
        closed=False;cleanup_error=None
        try:
            request=raw_json(out/'IDLE_REQUEST.json');request.update(raw_json(out/'DEADLINE.json'))
            scope=scope_module(request);path=out/'watchdog/UNIT_OWNERSHIP.json'
            while time.monotonic()<request['deadline_monotonic']+15:
                if path.exists():
                    receipt=raw_json(path);exact_unit(scope,receipt)
                    if not scope.alive(receipt['owner']) and scope.cgroup_empty(receipt['control_group']):
                        closed=True;break
                elif not (out/'WATCHDOG_START.json').exists() or raw_json(out/'WATCHDOG_START.json')['returncode']:
                    closed=True;break
                time.sleep(.1)
        except BaseException as cleanup:cleanup_error=repr(cleanup)
        put(out/'IDLE_FAILURE_FINAL.json',dict(error=repr(exc),watchdog_closed=closed,cleanup_error=cleanup_error))
        raise


if __name__=='__main__':
    if sys.argv[1]=='--watchdog':
        # This process publishes its actual owner before reading these inputs.
        watchdog(Path(sys.argv[2]))
    else:main(Path(sys.argv[1]))
