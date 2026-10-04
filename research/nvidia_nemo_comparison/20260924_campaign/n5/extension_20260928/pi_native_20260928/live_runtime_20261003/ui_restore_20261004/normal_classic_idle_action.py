"""Normal desktop Exec opens idle chooser and exits. README_NORMAL_CLASSIC_IDLE.md."""
import ast
import hashlib
import json
from pathlib import Path
import shlex


def once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Exact retained idle-helper derivation boundary required: '+old[:90])
    return source.replace(old, new)


def replace_function(source, name, replacement):
    tree = ast.parse(source)
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(functions) != 1:
        raise ValueError('One exact retained helper function required: '+name)
    node = functions[0]; lines = source.splitlines(keepends=True)
    return ''.join(lines[:node.lineno-1])+replacement+'\n'+''.join(lines[node.end_lineno:])


def derive_control(source):
    source = once(source, "    folders=list(owners.iterdir())\n", "    folders=[root for root in owners.iterdir() if root.name not in request['prior_unit_owner_names']]\n")
    source = once(source,
        "        if base.exists() and (not base.is_dir() or next(base.iterdir(),None) is not None):\n            raise ValueError('Default production data appeared before exact desktop Exec; preserve it')\n",
        "        if not base.is_dir() or base.is_symlink():\n            raise ValueError('Actual existing production store must be preserved')\n")
    begin = "        todo=['.'];buttons=[];visited=0\n"
    end = "        while len(geometry)<10 and time.monotonic()<request['deadline_monotonic']-15:\n"
    if source.count(begin) != 1 or source.count(end) != 1:
        raise ValueError('Exact actual Tk widget inspection block required')
    start, finish = source.index(begin), source.index(end)
    source = source[:start]+'''        if str(send('wm','title','.'))!='Just Peachy · choose combination':
            raise ValueError('Actual normal desktop must open the backend chooser')
        todo=['.'];buttons=[];boxes=[];combos=[];visited=0
        while todo:
            widget=todo.pop();visited+=1
            if visited>512:raise ValueError('Bounded actual chooser widget census')
            kind=str(send('winfo','class',widget))
            if kind in ('Button','TButton'):buttons.append((widget,str(send(widget,'cget','-text'))))
            if kind=='Listbox':boxes.append(widget)
            if kind=='TCombobox':combos.append(widget)
            todo.extend(control.tk.splitlist(send('winfo','children',widget)))
        ok=[w for w,text in buttons if text=='OK · open application']
        exit_buttons=[w for w,text in buttons if text=='Exit to desktop']
        if len(ok)!=1 or len(exit_buttons)!=1 or len(boxes)!=1 or len(combos)!=1:
            raise ValueError('Actual one scrollable backend/source chooser required')
        if any(text in ('Start','Stop') for _,text in buttons):
            raise ValueError('Chooser must have no microphone Start/Stop control')
        source_values=tuple(control.tk.splitlist(send(combos[0],'cget','-values')))
        source_value=str(send(combos[0],'get'))
        backend_labels=tuple(control.tk.splitlist(send(boxes[0],'get',0,'end')))
        if source_values!=('live','saved') or source_value!='live' or not 3<=len(backend_labels)<=128:
            raise ValueError('Actual idle source/backend chooser defaults differ')
        if backend_labels[:3]!=('Pyannote + ReDimNet','Pyannote + NeMo TitaNet','Pyannote + Anonymous'):
            raise ValueError('Actual retained baseline combinations must be present')
''' +source[finish:]
    source = once(source,
        "        policy_check=inspect_optional_policy(send,control.tk.splitlist,start[0])\n        put(out/'OPTIONAL_POLICY_GUI_CHECK.json',policy_check)\n        time.sleep(5)\n        if list((Path(request['data_root'])/'launches').iterdir()):raise RuntimeError('Idle launcher unexpectedly created worker records')\n        if not int(send(start[0],'instate','disabled')):raise ValueError('Start must remain disabled before Exit')\n",
        "        policy_check=dict(actual_chooser=True,backend_labels=backend_labels,input_source=source_value,ok_invocations=0,start_invocations=0,capture_off=True)\n        put(out/'CHOOSER_IDLE_CHECK.json',policy_check)\n        time.sleep(2)\n        if sorted(path.name for path in (Path(request['data_root'])/'launches').iterdir())!=request['prior_launch_names']:\n            raise RuntimeError('Idle chooser unexpectedly created a worker launch')\n")
    source = once(source,
        "    copied=[];total=0;walked=0;base=Path(request['data_root']);mirror=out/'production-data-readback';mirror.mkdir()\n",
        "    copied=[];total=0;walked=0;base=registration['root'] if registration else Path(request['data_root'])/'absent';mirror=out/'production-data-readback';mirror.mkdir()\n")
    source = once(source,
        "    worker_records=len(list((base/'launches').iterdir())) if (base/'launches').is_dir() else None\n",
        "    actual_launches=sorted(path.name for path in (Path(request['data_root'])/'launches').iterdir())\n    worker_records=len(set(actual_launches)-set(request['prior_launch_names']))\n    if actual_launches!=request['prior_launch_names']:failure=failure or 'Previous launches changed during idle chooser proof'\n")
    # Keep original identity, normal Exit, independent watchdog and complete
    # natural nested closure logic. Only its unique fresh owner tree is mirrored.
    original_tail = "if __name__=='__main__':\n"
    additions = '''_original_unchanged_state=unchanged_state
def unchanged_state(request):
    value=_original_unchanged_state(request)
    desktop=Path('/home/peachyprototype/Desktop')
    icons=sorted(path.name for path in desktop.glob('*.desktop') if 'peachy' in path.name.casefold())
    if icons!=['Just Peachy.desktop']:
        raise ValueError('Exactly one activated Just Peachy desktop shortcut required')
    value['just_peachy_shortcuts']=icons
    value['normal_desktop_chooser_idle']=True
    return value

'''
    source = once(source, original_tail, additions+original_tail)
    compile(source, '<normal-classic-idle-control>', 'exec')
    return source


def dispatch(payload, baseline):
    p = dict(payload)
    package = Path(p['package'])
    manifest_raw = (package/'PACKAGE_MANIFEST.json').read_bytes()
    if len(manifest_raw)>262144 or hashlib.sha256(manifest_raw).hexdigest()!=p['package_manifest_sha256']:
        raise ValueError('Exact immutable normal desktop package required')
    manifest = json.loads(manifest_raw)
    pin = next(row for row in manifest['files'] if row['path']=='launch_production_idle_action_v2.py')
    path = package/pin['path']; raw = path.read_bytes()
    if path.is_symlink() or (len(raw), hashlib.sha256(raw).hexdigest())!=(pin['bytes'], pin['sha256']):
        raise ValueError('Exact retained production idle action required')
    source = raw.decode('utf-8')
    # Original action validates the actual production acceptance, full package,
    # fresh ownership baseline and original independent16MiB output allocation.
    source = once(source,
        "    expected=('Exec='+binding['python']+' -B '+str(package/'native_scope.py')+' --binding '+str(package/'BINDING.json')+\n        ' --manifest-sha256 '+p['package_manifest_sha256']+' --data-root /home/peachyprototype/JustPeachy/data/runtime-v29')\n",
        "    entries=[line for line in raw.decode().splitlines() if line.startswith('Exec=')]\n    if len(entries)!=1:raise ValueError('One actual current Desktop Exec required')\n    expected=entries[0]\n    exact=[binding['python'],'-B',str(package/'native_scope.py'),'--binding',str(package/'BINDING.json'),'--manifest-sha256',p['package_manifest_sha256'],'--data-root','/home/peachyprototype/JustPeachy/data/runtime-v29']\n    if shlex.split(expected[5:])!=exact:raise ValueError('Actual normal production shortcut command differs')\n")
    source = once(source,
        "    if data_root.exists() and (not data_root.is_dir() or next(data_root.iterdir(),None) is not None):\n        raise ValueError('Idle proof requires the actual default data root absent or empty; preserve existing data')\n",
        "    if not data_root.is_dir():raise ValueError('Actual current recording store required')\n    owners=data_root/'unit-owners'\n    prior_unit_owner_names=sorted(path.name for path in owners.iterdir()) if owners.is_dir() else []\n    prior_launch_names=sorted(path.name for path in (data_root/'launches').iterdir())\n    if len(prior_unit_owner_names)>512 or len(prior_launch_names)>4096:raise ValueError('Finite existing metadata inventory required')\n")
    source = once(source,
        "        data_root_precondition='absent_or_empty',command=shlex.split(expected[5:]),watchdog_unit=watchdog_unit,\n",
        "        data_root_precondition='existing_store_preserved',prior_unit_owner_names=prior_unit_owner_names,prior_launch_names=prior_launch_names,command=shlex.split(expected[5:]),watchdog_unit=watchdog_unit,\n")
    namespace = dict(__name__='verified_normal_classic_idle', __file__=str(path))
    exec(compile(source, '<normal-classic-idle-action-derivative>', 'exec'), namespace)
    namespace['CONTROL_SOURCE'] = derive_control(namespace['CONTROL_SOURCE'])
    p['verify_optional_policy'] = True  # Existing dispatcher admission flag; test itself checks chooser only.
    if p.get('independent_pc_copy_bytes') != 16*1024**2:
        raise ValueError('Independent16MiB PC mirror reservation required before dispatch')
    return namespace['dispatch'](p, baseline)


if 'PAYLOAD' in globals():
    RESULT=dispatch(PAYLOAD,BASELINE)
