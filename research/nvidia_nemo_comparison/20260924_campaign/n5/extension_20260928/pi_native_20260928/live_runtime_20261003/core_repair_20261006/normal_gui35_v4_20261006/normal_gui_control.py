"""External production Tk workflow; see README_NORMAL_GUI_WORKFLOW.md.

No application imports, policy replacement, model construction, or service-room
override. Only the real desktop Exec starts the application.
"""
import ast
import base64
import hashlib
import json
import os
from pathlib import Path
import resource
import stat
import subprocess
import sys
import time

IDLE_REFERENCE_SHA = 'b123694a1c530090ff860f1a544227ada4e8a5d413dfc5078f6a14cf7d79d40e'


def read(path, maximum=262144):
    path=Path(path); before=path.lstat()
    if (path.resolve(strict=True)!=path or not stat.S_ISREG(before.st_mode)
            or before.st_nlink!=1 or not 0<=before.st_size<=maximum):
        raise ValueError('Canonical bounded ordinary workflow input required')
    with path.open('rb') as stream: raw=stream.read(maximum+1)
    after=path.lstat()
    if len(raw)>maximum or (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns):
        raise ValueError('Workflow input changed during read')
    return raw


def reference(out):
    raw=read(out/'IDLE_REFERENCE.py')
    if hashlib.sha256(raw).hexdigest()!=IDLE_REFERENCE_SHA:
        raise ValueError('Exact preserved idle Tcl/ownership reference required')
    assignments=[n for n in ast.parse(raw).body if isinstance(n,ast.Assign)
        and any(isinstance(t,ast.Name) and t.id=='CONTROL_SOURCE' for t in n.targets)]
    if len(assignments)!=1: raise ValueError('One pinned control assignment required')
    text=ast.literal_eval(assignments[0].value)
    space={'__name__':'normal_gui_ownership_reference','__file__':str(out/'IDLE_REFERENCE.py')}
    exec(compile(text,str(out/'IDLE_CONTROL_REFERENCE.py'),'exec'),space)
    return space


def failure_receipt(path,value):
    raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    if len(raw)>262144:raise ValueError('Bounded failure receipt required')
    with path.open('xb') as stream:
        if stream.write(raw)!=len(raw):raise OSError('Short failure receipt')
        stream.flush();os.fsync(stream.fileno())
    if read(path)!=raw:raise OSError('Failure receipt independent readback differs')


def unit_metadata(scope, receipt):
    state=scope.properties(receipt['unit'])
    if (state.get('InvocationID')!=receipt['invocation_id']
            or state.get('ControlGroup')!=receipt['control_group']):
        raise ValueError('Exact newly-owned production unit identity changed')
    return state


def watchdog(out):
    """Independent deadline: authenticated new unit only, never a PID census kill."""
    os.sched_setaffinity(0,{3})
    for kind,cap in ((resource.RLIMIT_AS,128*1024**2),(resource.RLIMIT_STACK,1024**2),(resource.RLIMIT_FSIZE,32*1024**2)):
        resource.setrlimit(kind,(cap,cap))
    directory=out/'watchdog';directory.mkdir()
    # Register before reading request/reference/package bytes.
    fields=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()
    owner=dict(pid=os.getpid(),start_ticks=int(fields[19]),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    raw=json.dumps(owner,separators=(',',':')).encode()
    with (directory/'OWNER.json').open('xb') as stream: stream.write(raw);stream.flush();os.fsync(stream.fileno())
    base=reference(out); request=base['raw_json'](out/'IDLE_REQUEST.json')
    request.update(base['raw_json'](out/'DEADLINE.json'));scope=base['scope_module'](request)
    state=scope.properties(request['watchdog_unit'])
    if state['MainPID']!=str(owner['pid']) or state['InvocationID']!=os.environ.get('INVOCATION_ID'):
        raise ValueError('Independent watchdog identity differs')
    base['put'](directory/'UNIT_OWNERSHIP.json',dict(unit=request['watchdog_unit'],invocation_id=state['InvocationID'],control_group=state['ControlGroup'],owner=owner,main_pid=owner['pid'],runtime_max_seconds=270))
    failure=None;closure=None
    try:
        while time.monotonic()<request['deadline_monotonic'] and not (out/'CONTROL_COMPLETE.json').exists(): time.sleep(.1)
        registration=base['nested_registration'](request)
        closure=base['close_owned_nested'](scope,registration,request['deadline_monotonic']+15)
        if not closure['closed']: raise RuntimeError('Exact nested production unit remains open')
    except BaseException as exc: failure=repr(exc)
    base['put'](directory/'WATCHDOG_EXIT.json',dict(owner=owner,closure=closure,failure=failure))
    if failure: raise RuntimeError(failure)


def selected_database(root, identifier):
    """Consistent selected-UUID numeric read only; no recovery/delete/contents."""
    import sqlite3
    path=root/'recordings/history.sqlite3'
    before=path.lstat()
    if path.resolve(strict=True)!=path or not stat.S_ISREG(before.st_mode) or before.st_nlink!=1:
        raise ValueError('Canonical ordinary existing SQLite database required')
    db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=.2)
    deadline=time.monotonic()+3
    try:
        db.execute('PRAGMA query_only=ON');db.execute('PRAGMA cache_size=-256')
        db.set_progress_handler(lambda:int(time.monotonic()>deadline),1000);db.execute('BEGIN')
        counts={}
        for name in ('sessions','segments','captions','caption_projections','events','artifacts','metadata_usage','terminal_events','terminal_metadata_usage'):
            column='id' if name=='sessions' else 'session_id'
            counts[name]=db.execute('SELECT COUNT(*) FROM '+name+' WHERE '+column+'=?',(identifier,)).fetchone()[0]
        row=db.execute('SELECT status,processed_samples,raw_samples FROM sessions WHERE id=?',(identifier,)).fetchone()
        return dict(selected_table_counts=counts,session=None if row is None else dict(status=row[0],processed_samples=row[1],raw_samples=row[2]),session_directory_absent=not os.path.lexists(root/'recordings/sessions'/identifier))
    finally:
        db.rollback();db.close()


def copy_metadata(out, source, relative):
    """Named metadata only, with independent fsync/readback; never audio/text logs."""
    raw=read(source);target=out/'production-metadata'/relative
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():
        if read(target)!=raw:raise ValueError('Immutable copied production metadata changed')
        return
    with target.open('xb') as stream:
        if stream.write(raw)!=len(raw):raise OSError('Short copied production metadata')
        stream.flush();os.fsync(stream.fileno())
    if read(target)!=raw:raise OSError('Copied production metadata readback differs')


def _main(out):
    base=reference(out);request=base['raw_json'](out/'IDLE_REQUEST.json');scope=base['scope_module'](request)
    put=base['put'];identity=base['identity'];raw_json=base['raw_json']
    deadline=time.monotonic()+210
    put(out/'DEADLINE.json',dict(deadline_monotonic=deadline));request['deadline_monotonic']=deadline
    watch_cmd=['systemd-run','--user','--unit='+request['watchdog_unit'],'--property=AllowedCPUs=3','--property=CPUQuota=100%','--property=TasksMax=16','--property=RuntimeMaxSec=270','--property=TimeoutStopSec=15','--property=KillMode=control-group','--setenv=PYTHONDONTWRITEBYTECODE=1',request['command'][0],'-B',str(out/'normal_control.py'),'--watchdog',str(out)]
    started=subprocess.run(watch_cmd,capture_output=True,text=True,timeout=10)
    put(out/'WATCHDOG_START.json',dict(returncode=started.returncode,stdout=started.stdout[:4096],stderr=started.stderr[:4096]))
    if started.returncode: raise RuntimeError('Independent production-unit watchdog did not arm')
    def wait(check,label,until=None):
        stop=min(deadline-15,until if until is not None else deadline-15)
        while time.monotonic()<stop:
            value=check()
            if value is not None and value is not False:return value
            time.sleep(.1)
        raise TimeoutError(label)
    watcher=wait(lambda:raw_json(out/'watchdog/UNIT_OWNERSHIP.json') if (out/'watchdog/UNIT_OWNERSHIP.json').exists() else None,'Watchdog owner registration',time.monotonic()+10)
    base['exact_unit'](scope,watcher)
    if identity(watcher['owner']['pid'])!=watcher['owner']: raise ValueError('Watchdog exact owner changed')
    before=base['unchanged_state'](request);put(out/'STATE_BEFORE.json',before)
    import tkinter as tk
    tkroot=tk.Tk();tkroot.withdraw();tkroot.tk.call('tk','appname','jp_normal_control_'+str(os.getpid()))
    std_out=(out/'NATIVE_SCOPE.stdout').open('xb');std_err=(out/'NATIVE_SCOPE.stderr').open('xb')
    process=None;registration=None;failure=None;normal_exit=False;workflow={};closure=None;watch_closed=False
    try:
        if hashlib.sha256(read(Path(request['desktop']),65536)).hexdigest()!=request['desktop_sha256']:
            raise ValueError('Activated Desktop changed before actual Exec')
        process=subprocess.Popen(request['command'],stdin=subprocess.DEVNULL,stdout=std_out,stderr=std_err)
        outside=identity(process.pid)
        if outside is None: raise RuntimeError('Desktop native_scope exited before registration')
        put(out/'NATIVE_SCOPE_CHILD_REFERENCE.json',dict(child=outside,command=request['command'],new_identity=False))
        def find_registration():
            value=base['nested_registration'](request)
            if value and value['receipt']:return value
            if process.poll() is not None:raise RuntimeError('Native_scope ended before production ownership')
        registration=wait(find_registration,'New production unit ownership')
        if registration['owner']!=outside:raise ValueError('Desktop outside owner differs from actual child')
        receipt=registration['receipt'];app_owner=receipt['owner'];state=unit_metadata(scope,receipt)
        if (state['RuntimeMaxUSec']!='infinity' or state['MainPID']!=str(app_owner['pid'])
                or identity(app_owner['pid'])!=app_owner):raise ValueError('Actual production manual unit identity/lifetime differs')
        envelope=raw_json(registration['root']/'main/ENVELOPE.json')
        if envelope['owner']!=app_owner or envelope['address_space']!=[256*1024**2,1024**3]:raise ValueError('Actual production GUI soft/hard address-space policy differs')
        argv=Path('/proc',str(app_owner['pid']),'cmdline').read_bytes().split(b'\0')
        if os.fsencode(Path(request['package'])/'native_scope.py') not in argv or os.fsencode(Path(request['package'])/'BINDING.json') not in argv:
            raise ValueError('Actual production app command differs from bound Desktop package')
        if not any(line.endswith(':'+receipt['control_group']) for line in Path('/proc',str(app_owner['pid']),'cgroup').read_text().splitlines()):
            raise ValueError('Production app is outside its acknowledged unit')
        def find_app():
            candidates=tkroot.tk.splitlist(tkroot.tk.call('winfo','interps'))
            if len(candidates)>64:raise ValueError('Finite interpreter census')
            matches=[]
            for name in candidates:
                try:pid=int(tkroot.tk.call('send',name,'pid'))
                except tk.TclError:continue
                if pid==app_owner['pid']:matches.append(name)
            if len(matches)>1:raise ValueError('Unique actual production Tcl interpreter required')
            return matches[0] if matches else None
        app=wait(find_app,'Production GUI interpreter')
        def send(*args):
            if identity(app_owner['pid'])!=app_owner or int(tkroot.tk.call('send',app,'pid'))!=app_owner['pid']:
                raise ValueError('Production GUI identity changed before widget command')
            return tkroot.tk.call('send',app,tkroot.tk.call('list',*args))
        def widgets():
            pending=['.'];result=[]
            while pending:
                widget=pending.pop();kind=str(send('winfo','class',widget));result.append((widget,kind))
                if len(result)>512:raise ValueError('Bounded actual widget census')
                pending.extend(tkroot.tk.splitlist(send('winfo','children',widget)))
            return result
        def named(text,classes=('Button','TButton')):
            found=[w for w,k in widgets() if k in classes and int(send('winfo','ismapped',w)) and str(send(w,'cget','-text'))==text]
            if len(found)!=1:raise ValueError('Exactly one actual visible control required: '+text)
            return found[0]
        def has(text):return any(k in ('Button','TButton','Label','TLabel') and int(send('winfo','ismapped',w)) and str(send(w,'cget','-text'))==text for w,k in widgets())
        actions=[]
        def invoke(text,classes=('Button','TButton'),destroys_root=False):
            widget=named(text,classes)
            if str(send(widget,'cget','-state'))=='disabled':raise RuntimeError('Actual control disabled: '+text)
            actions.append(dict(label=text,widget=widget,monotonic_sec=time.monotonic(),programmatic=True,physical_touch=False))
            if len(actions)>32:raise ValueError('Bounded actual actions')
            put(out/('ACTION_%02d.json'%len(actions)),actions[-1])
            try:send(widget,'invoke')
            except tk.TclError:
                if not destroys_root:raise
        def portrait():
            extent=[int(send('winfo',name,'.')) for name in ('width','height','rootx','rooty')]
            return extent==[480,800,0,0] and int(send('wm','attributes','.','-fullscreen'))==1
        wait(portrait,'Familiar portrait chooser')
        radios=[w for w,k in widgets() if k=='Radiobutton']
        backends={str(send(w,'cget','-value')):str(send(w,'cget','-text')) for w in radios if str(send(w,'cget','-value')) not in ('live','saved')}
        expected=request['chooser_rows']
        if len(backends)!=6 or backends!=expected:raise ValueError('Actual six backend chooser rows differ')
        invoke('Pyannote + ReDimNet',('Radiobutton',));invoke('Live microphone',('Radiobutton',))
        selected=named('Pyannote + ReDimNet',('Radiobutton',));source=named('Live microphone',('Radiobutton',))
        if str(send('set',send(selected,'cget','-variable')))!='pyannote_redimnet' or str(send('set',send(source,'cget','-variable')))!='live':raise ValueError('Actual selected chooser variables differ')
        invoke('Open Application',destroys_root=True)
        app=wait(find_app,'Exact application interpreter after chooser')
        wait(lambda:has('Start'),'Idle application Start');wait(portrait,'Familiar portrait application')
        root=Path(request['data_root'])
        if (root/'CURRENT_LAUNCH.json').exists():prior_current=read(root/'CURRENT_LAUNCH.json')
        else:prior_current=None
        invoke('Start')
        def actual_launch():
            path=root/'CURRENT_LAUNCH.json'
            if not path.exists():return None
            raw=read(path)
            if raw==prior_current:return None
            current=json.loads(raw);folder=root/'launches'/current['launch_id']
            if current['launch_id'] in request['prior_launch_names']:raise ValueError('Start reused a historical launch')
            if not (folder/'worker/SESSION.json').exists():return None
            return current['launch_id'],folder
        launch_id,launch=wait(actual_launch,'Actual new worker launch/session')
        native_request=raw_json(launch/'REQUEST.json');policy=native_request['policy'];chosen=native_request['selection']
        seconds=policy['maximum_session_seconds']
        if (native_request['unit']!=receipt['unit'] or native_request['binding']!=str(Path(request['package'])/'BINDING.json')
                or chosen['diarizer']!='pyannote' or chosen['embedding']!='redimnet' or chosen['input_source']!='live'
                or chosen.get('optional_d1_refiner') or policy['manual_stop'] is not True
                or policy['max_backlog_seconds'] is not None or type(seconds) is not int or seconds<1
                or policy['max_drain_seconds']!=seconds):raise ValueError('Real Start did not create genuine normal capacity policy')
        session=raw_json(launch/'worker/SESSION.json');identifier=session['session_id'];worker=raw_json(launch/'worker/REGISTERED_OWNER.json')
        import re
        if re.fullmatch('[0-9a-f]{32}',identifier) is None or session['worker']!=worker or worker['boot_id']!=request['boot_id']:
            raise ValueError('Actual session/worker identity differs')
        child=raw_json(launch/'CHILD_LAUNCH.json')
        if child['manager']!=app_owner or child['child_owner']!=worker or child['request_sha256']!=hashlib.sha256(read(launch/'REQUEST.json')).hexdigest():raise ValueError('Actual Start ownership chain differs')
        worker_envelope=raw_json(launch/'worker/ENVELOPE.json')
        if worker_envelope['owner']!=worker or worker_envelope['address_space']!=[1024**3,1024**3]:raise ValueError('Actual model worker address-space policy differs')
        if not any(line.endswith(':'+receipt['control_group']) for line in Path('/proc',str(worker['pid']),'cgroup').read_text().splitlines()):
            raise ValueError('Normal model worker is outside the production unit')
        for name in ('REGISTERED_OWNER.json','SESSION.json','ENVELOPE.json'):
            copy_metadata(out,launch/'worker'/name,Path('launches')/launch_id/'worker'/name)
        def capturing():
            import sqlite3
            if identity(worker['pid'])!=worker:raise RuntimeError('Worker ended before actual Stop')
            if has('Continue') or has('Allow microphone'):raise RuntimeError('Redundant Start consent control appeared')
            try:
                result=selected_database(root,identifier)
            except sqlite3.OperationalError as error:
                error_code=getattr(error,'sqlite_errorcode',None)
                if type(error_code) is int and (error_code & 255) in (5,6):
                    return None
                raise
            listening=any(k in ('Label','TLabel') and int(send('winfo','ismapped',w))
                and str(send(w,'cget','-text')).startswith(('balanced / O0 · Listening locally · ', '● SAVING EXACT AUDIO · Listening locally · ')) for w,k in widgets())
            if result['session'] and result['session']['processed_samples']>=192000 and has('Stop') and listening:return result
        running=wait(capturing,'RUNNING actual source reaches twelve seconds')
        source_owner_path=root/'recordings/sessions'/identifier/'work/source/REGISTERED_OWNER.json'
        source_registration=raw_json(source_owner_path);source_owner=source_registration['owner']
        if identity(source_owner['pid'])!=source_owner:raise ValueError('Actual source owner is not live before Stop')
        copy_metadata(out,source_owner_path,Path('sources')/identifier/'REGISTERED_OWNER.json')
        workflow.update(app_owner=app_owner,worker_owner=worker,source_owner=source_owner,launch_id=launch_id,session_id=identifier,unit=receipt['unit'],unit_ownership=receipt,actual_unit_properties=state,gui_address_space=envelope['address_space'],worker_address_space=worker_envelope['address_space'],policy=policy,running=running,actual_portrait_ui=True,six_backend_rows=backends,start_no_consent=True,request_sha256=hashlib.sha256(read(launch/'REQUEST.json')).hexdigest())
        put(out/'NORMAL_RUNNING_PROOF.json',workflow)
        invoke('Stop')
        def closed_worker():
            path=launch/'HOST_CLOSURE.json'
            if not path.exists():return None
            value=raw_json(path);result=value.get('result') or {}
            if (value.get('returncode')!=0 or value.get('direct_child_reaped') is not True
                    or value.get('stdout_reader_joined') is not True or value.get('output_error')
                    or value.get('receipt_errors') or value.get('registered_owner')!=worker
                    or value.get('nested_source',{}).get('closed') is not True
                    or result.get('session_id')!=identifier or result.get('failure') or result.get('cleanup_error')):
                raise RuntimeError('Normal worker/source closure is not successful')
            if identity(worker['pid'])==worker or identity(source_owner['pid'])==source_owner:raise RuntimeError('Exact worker/source remains alive')
            return value
        worker_closure=wait(closed_worker,'Actual Stop worker/source closure')
        physical_close=raw_json(source_owner_path.with_name('SOURCE_CLOSE.json'))
        if physical_close.get('owner')!=source_owner:raise RuntimeError('Source-close receipt owner differs')
        copy_metadata(out,source_owner_path.with_name('SOURCE_CLOSE.json'),Path('sources')/identifier/'SOURCE_CLOSE.json')
        stopped=selected_database(root,identifier)
        if stopped['session']['status']!='stopped' or stopped['session']['processed_samples']<192000:raise RuntimeError('Stop did not commit the complete actual source')
        wait(lambda:has('Discard this temporary session'),'Actual post-Stop disposition prompt')
        invoke('Discard this temporary session');wait(lambda:has('Discard'),'Actual selected Discard confirmation');invoke('Discard')
        def purged():
            value=selected_database(root,identifier)
            if value['session_directory_absent'] and value['session'] is None and not any(value['selected_table_counts'].values()):return value
        discard=wait(purged,'Selected UUID audio/transcript/nine tables purged')
        deletion_path=root/'recordings/deletion_receipts'/(identifier+'.json')
        deletion=raw_json(deletion_path)
        if (deletion.get('schema')!='just-peachy.session-deletion.v1' or deletion.get('status')!='discarded'
                or deletion.get('session_id')!=identifier or deletion.get('request_kind')!='discard'
                or deletion.get('store_id')!=raw_json(root/'recordings/store.json').get('store_id')
                or os.path.lexists(root/'recordings/deletions'/(identifier+'.json'))):
            raise RuntimeError('Selected Discard intent is not durably complete')
        workflow.update(stopped=stopped,discard=discard,completed_deletion_receipt_sha256=hashlib.sha256(read(deletion_path)).hexdigest(),worker_closure_sha256=hashlib.sha256(read(launch/'HOST_CLOSURE.json')).hexdigest(),workers_closed=True,source_exact_owner_gone=True,complete_session_discard_passed=True)
        put(out/'NORMAL_DISCARD_PROOF.json',workflow)
        wait(lambda:has('Settings'),'Post-Discard settings');invoke('Settings');wait(lambda:has('Exit to desktop'),'Actual Settings Exit')
        try:invoke('Exit to desktop')
        except tk.TclError:pass  # Destruction may remove the reply; closure below remains mandatory.
        process.wait(timeout=max(1,min(15,deadline-time.monotonic())))
        if process.returncode!=0:raise RuntimeError('Actual production native_scope Exit failed')
        closure=raw_json(registration['root']/'UNIT_CLOSURE.json')
        if (closure.get('main_exact_owner_gone') is not True or closure.get('unit_stopped') is not True
                or closure.get('all_registered_source_owners_gone') is not True
                or not scope.cgroup_empty(receipt['control_group'])):
            raise RuntimeError('Actual production unit closure incomplete')
        for name in ('REGISTERED_OWNER.json','SERVICE_REQUEST.json','UNIT_OWNERSHIP.json','UNIT_CLOSURE.json','main/REGISTERED_OWNER.json','main/ENVELOPE.json','SERVICE_EXIT.json'):
            source_file=registration['root']/name
            if source_file.exists():copy_metadata(out,source_file,Path('unit-owners')/registration['root'].name/name)
        workflow['unit_closure']=dict(main_exact_owner_gone=True,unit_recursively_empty=True,all_registered_source_owners_gone=True,unit_closure_sha256=hashlib.sha256(read(registration['root']/'UNIT_CLOSURE.json')).hexdigest())
        normal_exit=True;workflow['actions']=actions
    except BaseException as exc:failure=repr(exc)
    finally:
        cleanup_error=None
        try:
            if registration is None:registration=base['nested_registration'](request)
            cleanup=base['close_owned_nested'](scope,registration,deadline+15)
            if not cleanup['closed']:raise RuntimeError('Exact newly-owned production unit not closed')
            if process is not None:process.wait(timeout=15)
            put(out/'CONTROL_COMPLETE.json',dict(normal_exit=normal_exit,failure=failure,cleanup=cleanup))
        except BaseException as exc:cleanup_error=repr(exc)
        std_out.close();std_err.close()
        until=max(time.monotonic()+15,deadline+20 if cleanup_error else time.monotonic()+15)
        while time.monotonic()<until:
            base['exact_unit'](scope,watcher)
            if not scope.alive(watcher['owner']) and scope.cgroup_empty(watcher['control_group']):watch_closed=True;break
            time.sleep(.1)
        after=base['unchanged_state'](request)
        put(out/'STATE_AFTER.json',after)
        passed=not failure and not cleanup_error and normal_exit and watch_closed and after==before
        put(out/'NORMAL_GUI_RESULT.json',dict(schema='just-peachy.normal-production-gui.v1',functional_success=passed,actual_desktop_exec=True,policy_overridden=False,service_room_bypassed=False,production_scope_runtime_seconds=None,lifetime_policy='manual_stop_storage_guarded',external_control_deadline_seconds=210,watchdog_seconds=270,desktop_double_click_tested=False,physical_touch_qualified=False,quality_qualified=False,manual_300_second_capture_qualified=False,normal_exit_observed=normal_exit,watchdog_closed=watch_closed,workflow=workflow,failure=failure,cleanup_error=cleanup_error))
        tkroot.destroy()
    if not passed:raise RuntimeError('Normal production GUI workflow failed: '+str(failure or cleanup_error))


def main(out):
    """A setup failure also waits for the separately armed exact-owner backstop."""
    try:return _main(out)
    except BaseException as exc:
        closed=False;cleanup_error=None
        try:
            base=reference(out);request=base['raw_json'](out/'IDLE_REQUEST.json')
            deadline=base['raw_json'](out/'DEADLINE.json')['deadline_monotonic']
            scope=base['scope_module'](request);path=out/'watchdog/UNIT_OWNERSHIP.json'
            while time.monotonic()<deadline+30:
                if path.exists():
                    watcher=base['raw_json'](path);base['exact_unit'](scope,watcher)
                    if not scope.alive(watcher['owner']) and scope.cgroup_empty(watcher['control_group']):closed=True;break
                elif (out/'WATCHDOG_START.json').exists() and base['raw_json'](out/'WATCHDOG_START.json')['returncode']:
                    closed=True;break
                time.sleep(.1)
        except BaseException as cleanup:cleanup_error=repr(cleanup)
        failure_receipt(out/'NORMAL_GUI_FAILURE_FINAL.json',dict(failure=repr(exc),watchdog_closed=closed,cleanup_error=cleanup_error))
        raise


if __name__=='__main__':
    if sys.argv[1]=='--watchdog':watchdog(Path(sys.argv[2]))
    else:main(Path(sys.argv[1]))
