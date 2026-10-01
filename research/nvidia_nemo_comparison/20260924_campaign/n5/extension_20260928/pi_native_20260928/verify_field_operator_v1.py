"""Changed operator contract checks only; README_FIELD_OPERATOR_V2.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,ast,hashlib,json,sys,time,traceback
from pathlib import Path
from types import SimpleNamespace as NS
from datetime import datetime,timezone

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installed-release',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--expires-utc',required=True)
    args=parser.parse_args()
    args.output.mkdir(exist_ok=False)
    owner=dict(pid=psutil.Process().pid,create_time=psutil.Process().create_time(),affinity=[14])
    (args.output/'REGISTERED_OWNER.json').open('x').write(json.dumps(owner))
    sys.dont_write_bytecode=True
    assert datetime.now(timezone.utc)<datetime.fromisoformat(args.expires_utc)
    began=time.monotonic();checks=[]
    try:
        code=Path(__file__).parent
        sys.path[:0]=[str(code),str(args.installed_release),str(args.installed_release/'vendor'),str(args.installed_release/'native')]
        from field_operator_actions_v2 import Actions
        from field_operator_controller_v2 import store_class,COMMANDS
        from field_transfer_v2 import derive
        import threading,importlib.util,app
        spec=importlib.util.spec_from_file_location('app.sessions',code/'archive_stop_sessions_v1.py')
        sessions=importlib.util.module_from_spec(spec);sys.modules['app.sessions']=sessions;spec.loader.exec_module(sessions);app.sessions=sessions
        import field_archive_v3 as installed
        manifest=json.loads((args.installed_release/'RELEASE_MANIFEST.json').read_bytes())
        pin=next(x for x in manifest['files'] if x['path']=='native/field_archive_v3.py')
        assert hashlib.sha256(Path(installed.__file__).read_bytes()).hexdigest()==pin['sha256']
        derived=derive(Path(installed.__file__).read_bytes(),pin['sha256'])
        old=store_class(installed,sessions,None,None,{})
        OneRun=old.__bases__[0]
        Combined=type('ContractOnlyStore',(derived.FieldArchiveStore,OneRun),{})
        assert Combined.__mro__[:4]==(Combined,derived.FieldArchiveStore,OneRun,sessions.SessionStore)
        assert Combined.export is derived.FieldArchiveStore.export
        assert Combined.new is OneRun.new and Combined._publish is OneRun._publish
        checks.append('actual-class-MRO-and-method-routing-without-constructor')
        outputs=NS(stop_event=threading.Event())
        actions=Actions(Path('operator-fixture'),outputs,derived)
        identifier='a'*32
        c=NS(engine=None,archive=None,_epoch_archive=None,_playback=None,enrollment=False,_archive_failure=None,
             session_store=NS(delivery_identifier=identifier,delivery_epoch=True,
                              metadata=lambda unused:dict(state='SAVED',pinned=True)))
        assert actions.check(c,'save',dict(identifier=identifier))==identifier
        assert actions.check(c,'open',dict(identifier=identifier))==identifier
        assert actions.check(c,'export',dict(identifier=identifier,path=str(actions.destination),audio=True,consent=True))==identifier
        checks.append('owned-save-open-export-preconditions')
        rejects=[]
        def reject(label,fn):
            try:fn()
            except (ValueError,RuntimeError):rejects.append(label)
            else:raise AssertionError('Expected reject '+label)
        reject('foreign-id',lambda:actions.check(c,'open',dict(identifier='b'*32)))
        reject('foreign-export-path',lambda:actions.check(c,'export',dict(identifier=identifier,path='elsewhere',audio=True,consent=True)))
        reject('missing-export-consent',lambda:actions.check(c,'export',dict(identifier=identifier,path=str(actions.destination),audio=True,consent=False)))
        reject('delete-before-readback',lambda:actions.check(c,'delete',dict(identifier=identifier,confirmed=True)))
        reject('import-before-delete',lambda:actions.check(c,'import',dict(path=str(actions.destination),consent=True)))
        reject('unavailable-play',lambda:actions.check(c,'play',dict(identifier=identifier)))
        c.engine=object();reject('active-engine',lambda:actions.check(c,'save',dict(identifier=identifier)));c.engine=None
        c.archive=object();reject('unclosed-archive',lambda:actions.check(c,'save',dict(identifier=identifier)));c.archive=None
        actions.counts['open']=16;reject('open-cardinality',lambda:actions.check(c,'open',dict(identifier=identifier)));actions.counts['open']=0
        outputs.stop_event.set();reject('latched-writer-failure',lambda:actions.check(c,'open',dict(identifier=identifier)));outputs.stop_event.clear()
        # Execute the selected nested methods against a non-I/O base. No installed constructor.
        tree=ast.parse((code/'field_operator_controller_v2.py').read_bytes())
        node=next(n for n in ast.walk(tree) if isinstance(n,ast.ClassDef) and n.name=='DeliveryController')
        keep={'_delivery_command','_do_session_action','_start_session'}
        methods=[n for n in node.body if isinstance(n,ast.FunctionDef) and n.name in keep]
        wrapper=ast.ClassDef(name='Boundary',bases=[ast.Name(id='Base',ctx=ast.Load())],keywords=[],body=methods,decorator_list=[])
        class Base:
            def _do_session_action(self,action,values):return (action,values)
            def _start_session(self):return 'START_REACHED'
        recorder=NS(run=lambda obj,action,values,perform:perform(action,values))
        env=dict(Base=Base,COMMANDS=COMMANDS,actions=recorder)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[wrapper],type_ignores=[])),'<operator-boundaries>','exec'),env)
        b=env['Boundary']()
        b._delivery_attempted=False;b._delivery_new_requested=False;b.conversation_id=None;b.source_kind='live'
        b.session_store=NS(delivery_new=False,delivery_identifier=None,metadata=lambda unused:dict(audio_requested=True,consent=dict(audio_storage=True)))
        reject('Start-before-audio-New',b._start_session)
        b._delivery_command('session_action',('new',dict(audio=True,consent=True)),{})
        assert b._delivery_new_requested
        b.session_store.delivery_new=True;b.session_store.delivery_identifier=identifier;b.conversation_id=identifier
        assert b._do_session_action('save',{})==('save',dict(identifier=identifier))
        assert b._start_session()=='START_REACHED'
        reject('same-process-second-Start',b._start_session)
        checks.append('actual-UI-New-args-Save-current-and-first-Start-boundary')
        result=dict(status='PASS_CHANGED_OPERATOR_HOST_CONTRACT_ONLY',owner=owner,checks=checks,rejects=rejects,
            constructors_executed=False,capture=False,models=False,gui=False,filesystem_mutations=False,
            seconds=time.monotonic()-began,ended_utc=datetime.now(timezone.utc).isoformat())
        (args.output/'REVIEW.json').open('x').write(json.dumps(result,indent=2))
        print(json.dumps(dict(status=result['status'],checks=len(checks),rejects=len(rejects))))
    except BaseException:
        (args.output/'FAILURE.txt').open('x').write(traceback.format_exc()[:32768]);raise
if __name__=='__main__':main()
