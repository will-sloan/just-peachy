"""Read-only N4 allocation discovery. See README_RESERVATION_CENSUS_V1.md."""
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import stat
import time

from common import bind, load, verify
from metric_process import exact_process, identity
from reservation_budget_v1 import (calculate, live_allocation, owner_key,
                                    read_closed_components, require)


def admission_paths(root):
    """Enumerate every recorded admission without traversing a reparse point."""
    root = Path(root)
    top = root.lstat()
    require(not (stat.S_ISLNK(top.st_mode) or
        getattr(top, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT),
        'N4 admission root is a link/reparse point')
    root = root.resolve(strict=True)
    paths = []
    def error(exc):
        raise exc
    for directory, names, files in os.walk(root, followlinks=False, onerror=error):
        for name in names + files:
            p = Path(directory)/name
            s = p.lstat()
            require(not (stat.S_ISLNK(s.st_mode) or
                getattr(s, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT),
                'N4 admission scan encountered a link/reparse point')
        if 'ADMISSION.json' in files:
            paths.append(Path(directory)/'ADMISSION.json')
    return sorted(paths)


def epoch(worker, spec):
    """Heartbeat timestamps may advance; ownership and launch state may not."""
    return dict(worker={k: worker.get(k) for k in
        ('run_id', 'status', 'pid', 'create_time', 'child_pid',
         'child_create_time', 'child_launch_pending', 'exit_code')}, spec=spec)


def output_argument(argv, local):
    require(isinstance(argv, list) and all(isinstance(x, str) for x in argv)
            and argv.count('--output') == 1, 'Exactly one explicit output argument required')
    i = argv.index('--output')
    require(i+1 < len(argv), 'Output argument is missing')
    root = Path(argv[i+1]).resolve(strict=True)
    require(root.is_relative_to(Path(local).resolve()/'n4') and root != Path(local).resolve()/'n4',
            'Output is outside its private N4 allocation')
    return root


def execution_children(terminal):
    """Only execution-owner fields; historical input snapshots are not children."""
    values = []
    child = terminal.get('child')
    if child is not None:
        owner_key(child); values.append(child)
    for worker in terminal.get('workers', []):
        for owner in worker.get('owners', []):
            owner_key(owner); values.append(owner)
    return values


def classify(path, local, *, lookup=exact_process):
    """Resolve direct, legacy terminal, dispatch, and historical launcher receipts."""
    ab = bind(path); admission = load(path); root = Path(path).parent
    dependencies = [ab]
    terminal = None
    for name in ('RESULT.json', 'FAILED.json'):
        if (root/name).exists():
            tb = bind(root/name); terminal = load(tb['path']); dependencies.append(tb)
            break
    owner = admission.get('owner')
    kind = 'DIRECT_OWNER'
    if owner is None and terminal is not None and 'owner' in terminal:
        require(terminal.get('admission') == ab, 'Legacy terminal/admission join differs')
        owner = terminal['owner']; kind = 'TERMINAL_OWNER'
    if owner is not None:
        owner_key(owner)
        if terminal is not None and 'owner' in terminal:
            require(terminal['owner'] == owner, 'Terminal names a different allocation owner')
        if terminal is not None and 'admission' in terminal:
            require(terminal['admission'] == ab, 'Terminal names a different admission')
        process = lookup(owner)
        if process is not None:
            require(kind == 'DIRECT_OWNER', 'Active legacy terminal-owned allocation is unsupported')
            return dict(kind=kind, state='ACTIVE', admission=ab, root=str(root), owner=owner,
                        dependencies=[ab])
        if terminal is not None:
            require(all(lookup(x) is None for x in execution_children(terminal)),
                    'A child outlived its recorded allocation owner')
        return dict(kind=kind, state='CLOSED_OWNER', admission=ab, root=str(root),
                    owner=owner, dependencies=dependencies)
    if 'worker_spec' in admission:
        sb = admission['worker_spec']; verify(sb); spec = load(sb['path'])
        target = output_argument(spec['argv'], local)
        require(target != root and not root.is_relative_to(target)
                and not target.is_relative_to(root), 'Dispatch must not overlap the delegated output')
        started = bind(root/'STARTED.json'); launch = load(started['path'])
        require(launch['worker_spec'] == sb, 'Dispatch start/spec join differs')
        target_ab = bind(target/'ADMISSION.json'); target_admission = load(target_ab['path'])
        owner_key(target_admission['owner'])
        start = launch['supervisor_start']; supervisor = {k: start[k] for k in ('pid','create_time')}
        owner_key(supervisor)
        require(lookup(supervisor) is None or lookup(target_admission['owner']) is not None,
                'Unresolved live dispatch without its admitted driver')
        return dict(kind='DELEGATED_DISPATCH', state='ALIAS_NOT_SECOND_ALLOCATION',
                    admission=ab, root=str(root), delegate=target_ab,
                    supervisor=supervisor, dependencies=[ab, sb, started, target_ab])
    if terminal is not None and 'launcher' in admission and 'isolation' in terminal:
        require(terminal.get('admission') == ab and terminal.get('status') in
                ('FAILED_PRESERVED', 'PASS_PRIVATE_TK_VIEWPORT_QUALIFICATION'),
                'Historical private-desktop terminal differs')
        verify(admission['launcher']); verify(terminal['isolation'])
        isolation = load(terminal['isolation']['path'])
        require(isolation.get('schema') == 'just-peachy.private-desktop-launch.v1'
                and type(isolation.get('exit_code')) is int and isolation.get('timed_out') is False
                and isolation.get('desktop_handle_closed') is True,
                'Historical launcher has no completed process-handle wait')
        require(Path(terminal['isolation']['path']).resolve() == root/'isolation.json',
                'Foreign historical launcher receipt')
        return dict(kind='HISTORICAL_PROCESS_HANDLE_WAIT', state='CLOSED_LEGACY_HANDLE',
                    admission=ab, root=str(root), exact_pid_reconstructed=False,
                    dependencies=dependencies+[admission['launcher'], terminal['isolation']])
    raise ValueError('Unclassified ownerless admission: '+str(path))


def validate_live(record, local, *, lookup=exact_process):
    ab = record['admission']; admission = load(ab['path']); process = lookup(record['owner'])
    require(process is not None, 'Allocation owner exited during scan; resample')
    argv = process.cmdline()
    require(output_argument(argv, local) == Path(record['root']).resolve(), 'Owner output command differs')
    code = admission.get('code', [])
    scripts = [b for b in code if b['path'] in argv]
    require(len(scripts) == 1, 'Live command is not bound to exactly one admitted source')
    verify(scripts[0])
    return live_allocation(ab, record['root'], local, lookup=lookup)


def validate_supervision(worker, spec, active, *, lookup=exact_process, now=None):
    require(worker.get('child_launch_pending') is False, 'Supervisor launch remains unresolved')
    host = dict(pid=worker['pid'], create_time=worker['create_time']); owner_key(host)
    launcher = dict(pid=worker['child_pid'], create_time=worker['child_create_time']); owner_key(launcher)
    if worker['status'] in ('COMPLETED', 'FAILED'):
        require(lookup(host) is None and lookup(launcher) is None, 'Terminal supervisor is still alive')
        return dict(state='CLOSED', host=host, launcher=launcher)
    require(worker['status'] == 'RUNNING' and
            0 <= (time.time() if now is None else now)-worker['heartbeat_unix'] < 120,
            'Supervisor is not healthy and stable')
    hp, lp = lookup(host), lookup(launcher)
    require(hp is not None and lp is not None and lp.ppid() == host['pid']
            and lp.cmdline() == spec['argv'], 'Supervisor launcher identity/command differs')
    matches = []
    for item in active:
        p = lookup(item['owner'])
        require(p is not None, 'Live allocation disappeared')
        if p.pid == lp.pid or p.ppid() == lp.pid:
            require(p.cmdline()[1:] == spec['argv'][1:], 'Actual interpreter command differs')
            matches.append(item['owner'])
    require(len(matches) == 1, 'Supervisor must join exactly one discovered active driver')
    return dict(state='RUNNING', host=host, launcher=launcher, driver=matches[0])


def visible_python_census(local, stage, active, supervision):
    """Catch visible unregistered N4 Python processes; never claim whole-host exclusivity."""
    import psutil
    covered = set()
    for item in active:
        p = exact_process(item['owner']); require(p is not None, 'Allocation owner disappeared')
        covered.add((p.pid, p.create_time()))
        for child in p.children(recursive=True):
            try: covered.add((child.pid, child.create_time()))
            except psutil.NoSuchProcess: pass
    for key in ('host', 'launcher'):
        if supervision['state'] == 'RUNNING': covered.add(owner_key(supervision[key]))
    scopes = [str(Path(x).resolve()).replace('/', '\\').lower() for x in (Path(local)/'n4', stage)]
    matched = []
    for p in psutil.process_iter(['pid', 'name']):
        if (p.info['name'] or '').lower() not in ('python.exe', 'pythonw.exe'): continue
        try:
            argv = p.cmdline()
            if not any(scope in arg.replace('/', '\\').lower() for scope in scopes for arg in argv): continue
            key = (p.pid, p.create_time())
            require(key in covered, 'Visible unregistered N4 Python process: '+str(p.pid))
            matched.append(dict(pid=p.pid, create_time=p.create_time()))
        except psutil.NoSuchProcess: continue
        # AccessDenied is deliberately propagated: its command cannot be excluded.
    return matched


def snapshot(local, stage, main_plan, requested_bytes, *, peak_bytes=0):
    from asr_full_bank import payload_inventory
    local = Path(local).resolve(strict=True)
    closed = read_closed_components(main_plan)
    state = local/'supervision'
    worker = load(state/'worker.json'); spec = load(state/'worker_spec.json'); before = epoch(worker, spec)
    paths = admission_paths(local/'n4')
    records = [classify(p, local) for p in paths]
    active = [validate_live(r, local) for r in records if r['state'] == 'ACTIVE']
    require(len({owner_key(a['owner']) for a in active}) == len(active), 'Duplicate active owner')
    fresh_worker = load(state/'worker.json')
    require(epoch(fresh_worker, load(state/'worker_spec.json')) == before,
            'Supervisor ownership changed during admission scan; resample')
    supervision = validate_supervision(fresh_worker, spec, active)
    visible = visible_python_census(local, stage, active, supervision)
    # All live usage is measured before the whole inventory, retaining growth conservatively.
    inventory = payload_inventory(local)
    policy_binding = bind(state/'campaign.json'); policy = load(policy_binding['path'])
    free = {d: shutil.disk_usage(d+'/').free for d in ('C:', 'G:')}
    calculation = calculate(inventory, closed, active, requested_bytes, policy, free,
                            datetime.now(timezone.utc), peak_bytes=peak_bytes)
    require(admission_paths(local/'n4') == paths, 'Admission set changed during census; resample')
    for record in records:
        for b in record['dependencies']: verify(b)
        if record['state'] == 'ACTIVE': require(exact_process(record['owner']) is not None, 'Live owner exited')
        if record['state'] == 'CLOSED_OWNER': require(exact_process(record['owner']) is None, 'Closed owner changed')
    require(epoch(load(state/'worker.json'), load(state/'worker_spec.json')) == before,
            'Supervisor ownership changed during census; resample')
    validate_supervision(load(state/'worker.json'), spec, active)
    visible_python_census(local, stage, active, supervision)
    verify(main_plan); verify(policy_binding)
    return dict(records=records, active_allocations=active, supervisor=supervision,
        visible_N4_python_processes=visible, inventory=inventory, closed_components=closed,
        policy=policy_binding, free_bytes=free, calculation=calculation,
        complete_recorded_N4_admission_census=True, active_set_supplied_by_caller=False,
        whole_host_exclusivity_proved=False, serialized_production_admission=False,
        production_guard_integration_complete=False, worker_execution_authorized=False,
        N4_accepted=False, N5_complete=False)
