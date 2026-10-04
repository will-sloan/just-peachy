"""Host-only activation01 readback repair; README_ACTIVATION_READBACK_V2.md."""
import argparse
import ast
import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import uuid

ACTION_SHA='0d62cf0f688493a8a66de27ee2fbae007b4e72600748778b9cca34767e172ef9'
NATIVE_SHA='462108079aa62e9adc70a44c7979a9a859a9f81e2d6b249cc7741f2ad588a895'
BASELINE_SHA='8872bc2ee78e94c5e3449f7bc2379b383f1bcd23e91f0b1a9862c0e3262646eb'
PRIVATE=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')


def digest(raw):return hashlib.sha256(raw).hexdigest()


def reader(action,native):
    if digest(action)!=ACTION_SHA or digest(native)!=NATIVE_SHA:raise ValueError('Exact executed action/native source pins required')
    tree=ast.parse(native);values={}
    for node in tree.body:
        if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
            if node.targets[0].id in ('ACTION_SOURCE','OPERATION_WRITES'):values[node.targets[0].id]=ast.literal_eval(node.value)
    if values!=dict(ACTION_SOURCE=action.decode().replace('\r\n','\n'),OPERATION_WRITES=True):
        raise ValueError('Executed embedded action/write mode differs')
    initial=[(i,n) for i,n in enumerate(tree.body) if isinstance(n,ast.Assign) and ast.unparse(n.targets[0])=='value']
    if len(initial)!=1 or not isinstance(initial[0][1].value,ast.Call):raise ValueError('Unique captured baseline required')
    flags=[k.value for k in initial[0][1].value.keywords if k.arg=='native_writes']
    if len(flags)!=1 or ast.literal_eval(flags[0]) is not False:raise ValueError('Captured baseline did not initialize writes false')
    endings=[ast.unparse(n) for n in tree.body]
    action_i=endings.index("exec(compile(ACTION_SOURCE, '<pinned-native-action>', 'exec'), action_namespace)")
    update_i=endings.index("value['native_writes'] = OPERATION_WRITES")
    if not initial[0][0]<action_i<update_i or endings[action_i+1]!="value['action_result'] = action_namespace['RESULT']":
        raise ValueError('Actual post-action write flag ordering differs')
    namespace=dict(__name__='_pinned_activation_readback_only',__file__='<executed-action>')
    exec(compile(action,'<executed-action>','exec'),namespace)
    original=next(n for n in ast.parse(action).body if isinstance(n,ast.FunctionDef) and n.name=='readback_payload')
    derived=copy.deepcopy(original)
    class Boundary(ast.NodeTransformer):
        forbidden=0
        baseline=0
        def visit_Tuple(self,node):
            if ast.dump(node,include_attributes=False)==ast.dump(ast.parse("('action_result','native_writes')",mode='eval').body,include_attributes=False):
                self.forbidden+=1;return ast.copy_location(ast.parse("('action_result',)",mode='eval').body,node)
            return self.generic_visit(node)
        def visit_Assign(self,node):
            if len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id=='baseline':
                self.baseline+=1
                node.value=ast.parse("encoded({name:(False if name=='native_writes' else outer[name]) for name in fields})",mode='eval').body
            return self.generic_visit(node)
    transform=Boundary();derived=transform.visit(derived)
    if (transform.forbidden,transform.baseline)!=(1,1):raise ValueError('Only the exact two baseline reconstruction nodes may change')
    module=ast.fix_missing_locations(ast.Module(body=[derived],type_ignores=[]));exec(compile(module,'<host-only-baseline-reconstruction>','exec'),namespace)
    return namespace


def main():
    import psutil
    me=psutil.Process();me.cpu_affinity([14]);ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--operation',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    if args.operation!=PRIVATE/'operation-desktop-activation-01' or args.output!=PRIVATE/'desktop-activation-01-readback-02':raise ValueError('Exact actual01/fresh readback02 scope required')
    args.output.mkdir();owner=json.dumps(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])).encode()
    with (args.output/'REGISTERED_OWNER.json').open('xb') as stream:stream.write(owner);stream.flush();os.fsync(stream.fileno())
    for drive,floor in (('C:/',50),('G:/',75)):
        if shutil.disk_usage(drive).free<floor*1024**3+16*1024**2:raise OSError('Independent readback reserve')
    op=args.operation
    action=(op/'ACTION.py.backup').read_bytes();native=(op/'dispatch/NATIVE_SOURCE.py').read_bytes()
    if len(action)>131072 or len(native)>1024**2 or (op/'ACTION.py.restore').read_bytes()!=action:raise ValueError('Exact bounded independent action copies')
    ns=reader(action,native);read,strict,write,encoded=map(ns.get,('read','strict','write','encoded'))
    if read(op/'ACTION.py.backup',131072)!=action or read(op/'dispatch/NATIVE_SOURCE.py',1024**2)!=native:raise ValueError('Source changed during proof')
    admission=strict(read(op/'dispatch/READONLY_ADMISSION.json',16384));phase=strict(read(op/'dispatch/PHASE.json',16384))
    if admission['source_sha256']!=NATIVE_SHA or admission['native_writes'] is not True or phase!=dict(fault=None,overflow=False,reader_error=[],readers_joined=True,returncode=0,ssh_reaped=True,writer_error=[]):raise ValueError('Exact command-bound natural phase required')
    raw=read(op/'dispatch/RESULT.json');outer=strict(raw);closure=strict(read(op/'dispatch/NATIVE_CLOSURE.json',16384));owner=strict(read(op/'dispatch/NATIVE_OWNER.json',16384))
    if closure!=dict(owner=owner,exact_pid_absent=True,natural_returncode=0) or owner!=outer['utility_owner']:raise ValueError('Exact natural inspector closure required')
    result=outer['action_result']
    if outer.get('native_writes') is not True or result['baseline_sha256']!=BASELINE_SHA or result['baseline_bytes']!=99894 or 'native_writes' not in result['baseline_fields']:raise ValueError('Only actual post-action flag discrepancy is admitted')
    files=ns['readback_payload'](outer);manifest=[]
    for source,value in files.items():
        target=args.output/'native'/Path(*PurePosixPath(source).parts[1:]);target.parent.mkdir(parents=True,exist_ok=True);write(target,value)
        manifest.append(dict(source=source,path=target.relative_to(args.output).as_posix(),bytes=len(value),sha256=digest(value)))
    for name,value in (('RESULT.json.backup',raw),('RESULT.json.restore',raw),('EXECUTED_ACTION.py.backup',action),('EXECUTED_ACTION.py.restore',action),('NATIVE_SOURCE.py.backup',native),('NATIVE_SOURCE.py.restore',native)):
        write(args.output/name,value)
    receipt=dict(status='COMPLETE_ACTIVATION_METADATA_READBACK',files=manifest,native_inspector=owner,closure=closure,source_result_sha256=digest(raw),native_actions=False,
        reconstruction=dict(field='native_writes',captured_value=False,outer_post_action_value=True,executed_action_sha256=ACTION_SHA,native_command_source_sha256=NATIVE_SHA,baseline_bytes=99894,baseline_sha256=BASELINE_SHA,all_other_readback_checks_unchanged=True))
    write(args.output/'VERIFY.json',encoded(receipt));write(args.output/'VERIFY.restore.json',encoded(receipt))
    print(json.dumps(dict(status=receipt['status'],files=len(files),output=str(args.output),verify_sha256=digest(encoded(receipt)))))


if __name__=='__main__':main()
