"""Exact registered cross-route paced option; README_S6C_PACED_CROSS_ROUTES_FAST_V1.md."""
from __future__ import annotations
import argparse,ast,hashlib,importlib,json,math,os,re,sys,tempfile,time
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
PINS={'s6c_paced_epoch4_fast_v1.py':'c13ed3849fb86aeb50341d823c2969b5084cd6e90aa8fee4c24785405e8d20c4',
      's6c_long_b36_v1.py':'09b809f6301e696054c4563fdad0d48072ae22716bafcf9002a33bdffd866c66'}
for name,sha in PINS.items():
    if hashlib.sha256((HERE/name).read_bytes()).hexdigest()!=sha:raise ValueError('Held dependency changed: '+name)
C=importlib.import_module('s6c_paced_epoch4_fast_v1');D=importlib.import_module('s6c_long_b36_v1')
for module in (C,D):
    if Path(module.__file__).resolve()!=HERE/(module.__name__+'.py'):raise ValueError('Wrong dependency import')
L=C.L;REPORT=C.REPORT;PAYLOAD=C.PAYLOAD
EPOCH_SHA='720a6cc6c1f9a11ea5d39c3c7f2ab52452aad507ea3d0e0a56fa2c3074af9945'
SCHEMA='s6c-cross-route-paired-paced.v1'
CELL_SCHEMA='s6c-cross-route-paced-cell-result.v1'
PAIR=['C085','C086'];ROUTES={'C085':('O0','O1'),'C086':('O1','O0')}
OVERRIDES={'source_bindings','candidate_routes','selected_panel','grid'}
EXCLUDED=OVERRIDES|{'checks','reuse_checks','source_checks'}
TEXT_REPLACEMENTS={
 'paced_candidates':'paced_cross_routes',
 's6c-canonical-paced-cell-result.v1':CELL_SCHEMA,
 'S6C_CANONICAL_PACED_EPOCH4':'S6C_CROSS_ROUTE_PACED_EPOCH4',
 'Canonical single-scene paced candidate panel, 16 cases plus four repeats, both ASR routes, fresh process/model/session/gallery state per cell. No finalist is implied before explicit selected IDs are supplied.':
 'Exact registered C085 O0-ASR/O1-ID and C086 O1-ASR/O0-ID; original16 whole cases plus repeat4,40 fresh cells. No invented routes, aliases, audio transformation or finalist selection.'}

def require(ok,message):
    if not ok:raise ValueError(message)

def source_bindings():
    own=[L.bind(Path(__file__)),L.bind(HERE/'README_S6C_PACED_CROSS_ROUTES_FAST_V1.md'),L.bind(HERE/'s6c_long_b36_v1.py'),L.bind(HERE/'README_S6C_LONG_B36_V1.md')]
    return own+C.source_bindings()

def selected_panel(value,mode,candidates):
    require(mode=='cross16_plus4' and candidates==PAIR,'Only exact ordered C085,C086 cross-route pair is admitted')
    return C.selected_panel(value,'full16_plus4',candidates)

def candidate_routes(spec,candidates):
    require(candidates==PAIR,'No substituted or duplicated cross-route candidate')
    result={}
    for cid,(asr,identity) in ROUTES.items():
        rows=[r for r in spec['profiles'] if r['candidate_id']==cid]
        require(len(rows)==1,'Exactly the one registered route per cross-route label required')
        row=rows[0];p=row['profile'];parent=[r for r in spec['profiles'] if r['candidate_id']=='C065' and r['asr_tap']==r['identity_tap']==asr]
        require(len(parent)==1,'Exact same-ASR C065 parent required')
        require((row['asr_tap'],row['identity_tap'])==(asr,identity) and (p['input']['asr_tap'],p['input']['identity_tap'])==(asr,identity),'Registered split routing differs')
        require(row['parent']=='C065' and row['recipe_id']=='N01' and row['cue_condition']=='CUES_OFF' and row['gallery_condition']=='NONE' and row['enrollment_tier'] is None,'Registered cross-route condition differs')
        require(p['identity']['mode']=='none' and p['tracker']['cues_enabled'] is False and p['xvf']['mode']=='none','Cross-route none/off execution required')
        changed=deepcopy(p);changed['profile_id']=parent[0]['profile']['profile_id'];changed['input']['identity_tap']=asr
        require(changed==parent[0]['profile'],'Cross route changed more than ID and identity audio tap')
        result[cid,asr]=row
    return result

def grid(selected,p):
    require(selected==PAIR and len(p['case_ids'])==len(set(p['case_ids']))==16 and len(p['repeated_case_ids'])==len(set(p['repeated_case_ids']))==4 and set(p['repeated_case_ids'])<=set(p['case_ids']),'Exact16+repeat4 source grid required')
    return [(cid,case,ROUTES[cid][0],rep) for rep,cases in ((1,p['case_ids']),(2,p['repeated_case_ids'])) for case in cases for cid in (selected if rep==1 else list(reversed(selected)))]

def record_spawn(child,folder,argv,manifest,job):
    """A successful Popen is evidence even if the following identity lookup fails."""
    return D.save(Path(folder)/'SPAWNED_PROCESS.json',dict(status='SPAWNED_CREATION_UNVERIFIED',pid=child.pid,creation_time=None,
        created_utc=L.utc(),argv=argv,manifest=manifest,job_key=job['job_key'],job_id=job['job_id'],
        scope='Successful owned Popen handle; no creation time or descendant closure inferred. Later LAUNCH/native/COMPLETE records must admit exact identity.'))

def compile_adapter():
    tree=ast.parse((HERE/'s6c_paced_epoch4_fast_v1.py').read_bytes());nodes=[];edits=[];originals={}
    class Metadata(ast.NodeTransformer):
        def visit_Constant(self,node):
            if isinstance(node.value,str) and node.value in TEXT_REPLACEMENTS:
                edits.append(dict(kind='literal',before=node.value,after=TEXT_REPLACEMENTS[node.value]));return ast.copy_location(ast.Constant(TEXT_REPLACEMENTS[node.value]),node)
            return node
        def visit_Compare(self,node):
            if ast.unparse(node)=="'s6c_paced_epoch4.py' in names":
                edits.append(dict(kind='quiet_process_name_addition'))
                return ast.copy_location(ast.parse("bool({'s6c_paced_epoch4.py','s6c_paced_cross_routes_v1.py','s6c_paced_epoch4_fast_v1.py','s6c_paced_cross_routes_fast_v1.py'} & names)",mode='eval').body,node)
            return self.generic_visit(node)
    for node in tree.body:
        if not isinstance(node,ast.FunctionDef) or node.name in EXCLUDED:continue
        originals[node.name]=deepcopy(node);node=Metadata().visit(deepcopy(node))
        if node.name=='run':
            initial=[i for i,n in enumerate(node.body) if isinstance(n,ast.Assign) and ast.unparse(n.targets[0])=='child']
            require(len(initial)==1 and ast.unparse(node.body[initial[0]].value)=='None','Original coordinator child initialization differs')
            node.body.insert(initial[0]+1,ast.parse('launch_cleanup = None').body[0])
            outer=[n for n in node.body if isinstance(n,ast.Try)];require(len(outer)==1,'Original coordinator try shape differs');outer=outer[0]
            handler=outer.handlers[0];require(len(handler.body)==4 and isinstance(handler.body[1],ast.Try) and isinstance(handler.body[2],ast.Try),'Original cleanup exception shape differs')
            require('terminate_owned(owned)' in ast.unparse(handler.body[1]) and 'child.wait(timeout=10)' in ast.unparse(handler.body[2]),'Original cleanup operations differ')
            handler.body[1:3]=ast.parse("try:\n    launch_cleanup = D.cleanup_attempt(child, owned)\nexcept Exception:\n    cleanup_errors.append(traceback.format_exc())").body
            assignments=[n for n in ast.walk(outer) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='remaining' for t in n.targets)]
            require(len(assignments)==1 and ast.unparse(assignments[0].value)=='owned_states(owned)','Original final owner query differs')
            assignments[0].value=ast.parse('D.final_owner_states(owned, child)',mode='eval').body
            class Spawn(ast.NodeTransformer):
                def visit_Assign(self,n):
                    if ast.unparse(n.targets[0])=='child' and isinstance(n.value,ast.Call) and ast.unparse(n.value.func)=='subprocess.Popen':
                        edits.append(dict(kind='immediate_successful_popen_record'))
                        return [n,ast.parse('record_spawn(child, folder, argv, pb, job)').body[0]]
                    return self.generic_visit(n)
                def visit_Call(self,n):
                    if isinstance(n.func,ast.Name) and n.func.id=='dict' and {'remaining_owned','cleanup_errors'}<={k.arg for k in n.keywords}:
                        n.keywords.append(ast.keyword(arg='launch_cleanup',value=ast.Name(id='launch_cleanup',ctx=ast.Load())))
                    return self.generic_visit(n)
            node=Spawn().visit(node);edits.append(dict(kind='reviewed_shared25s_cleanup_and_unknown_creation_lease_retention'))
        nodes.append(node)
    require(len([e for e in edits if e['kind']=='immediate_successful_popen_record'])==1,'Exactly one owned launch hook required')
    ns=dict(C.__dict__);ns.update(__file__=str(Path(__file__).resolve()),__name__=__name__,SCHEMA=SCHEMA,D=D,record_spawn=record_spawn,
        source_bindings=source_bindings,candidate_routes=candidate_routes,selected_panel=selected_panel,grid=grid)
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),str(Path(__file__).resolve()),'exec'),ns)
    unchanged=[n.name for n in nodes if ast.dump(n,include_attributes=False)==ast.dump(originals[n.name],include_attributes=False)]
    evidence=dict(reused_functions=[n.name for n in nodes],ast_identical_functions=unchanged,controlled_edits=edits,
        function_ast_sha256={n.name:hashlib.sha256(ast.dump(n,include_attributes=False).encode()).hexdigest() for n in nodes},
        native_function_is_original_unchanged='s6c_long_session.native; invoked by schema-adjusted original canonical worker',original_module_globals_unmodified=True)
    return ns,evidence

PRIVATE,ADAPTATION=compile_adapter()

def checks():
    passed=[]
    def good(name,ok):require(ok,name);passed.append(name)
    def bad(name,fn):
        try:fn()
        except (ValueError,KeyError):passed.append(name)
        else:raise AssertionError('Invalid cross-route fixture admitted: '+name)
    before={k:id(v) for k,v in C.__dict__.items()};original_checks=C.checks();good('original72 canonical guard group',original_checks['checks']==72)
    p=dict(case_ids=[str(i) for i in range(16)],repeated_case_ids=[str(i) for i in range(4)])
    rows=grid(PAIR,p);good('exact40 distinct scientific routes',len(rows)==len(set(rows))==40 and {r[0:1]+r[2:3] for r in rows}=={('C085','O0'),('C086','O1')})
    good('counterbalanced repeat4 order',rows[0][0]=='C085' and rows[32][0]=='C086')
    for ids in (['C085'],['C085','C085'],['C086','C085'],['C083','C084']):bad('candidate selection '+str(ids),lambda ids=ids:grid(ids,p))
    bad('wrong panel mode',lambda:selected_panel(p,'full16_plus4',PAIR));bad('path traversal',lambda:PRIVATE['namespace_roots']('../x'))
    pb=dict(schema='tiny');profile=dict(profile_id='C065_O0_O0',input=dict(asr_tap='O0',identity_tap='O0'),identity=dict(mode='none'),tracker=dict(cues_enabled=False),xvf=dict(mode='none'))
    synthetic=[]
    for cid,(asr,identity) in ROUTES.items():
        parent=deepcopy(profile);parent['profile_id']='C065_'+asr;parent['input']=dict(asr_tap=asr,identity_tap=asr)
        synthetic.append(dict(candidate_id='C065',asr_tap=asr,identity_tap=asr,profile=parent))
        child=deepcopy(parent);child['profile_id']=cid;child['input']['identity_tap']=identity
        synthetic.append(dict(candidate_id=cid,asr_tap=asr,identity_tap=identity,profile=child,parent='C065',recipe_id='N01',cue_condition='CUES_OFF',gallery_condition='NONE',enrollment_tier=None))
    good('one actual route admitted per ID',len(candidate_routes(dict(profiles=synthetic),PAIR))==2)
    for field,value in [('identity_tap','O0'),('cue_condition','REAL_ALIGNED_CUES'),('gallery_condition','FIXED_ROTATION_A')]:
        wrong=deepcopy(synthetic);wrong[1][field]=value;bad('route/condition '+field,lambda wrong=wrong:candidate_routes(dict(profiles=wrong),PAIR))
    wrong=deepcopy(synthetic);wrong[1]['profile']['tracker']['cues_enabled']=True;bad('changed actual tracker',lambda:candidate_routes(dict(profiles=wrong),PAIR))
    wrong=deepcopy(synthetic);wrong.append(deepcopy(wrong[1]));bad('invented duplicate route',lambda:candidate_routes(dict(profiles=wrong),PAIR))
    class Child:
        pid=123
        def __init__(self):self.done=False;self.terminated=0
        def poll(self):return 0 if self.done else None
        def terminate(self):self.terminated+=1;self.done=True
        def kill(self):self.done=True
        def wait(self,timeout):return self.poll()
    with tempfile.TemporaryDirectory(prefix='cross_paced_guards_') as td:
        child=Child();spawn=record_spawn(child,td,['original-child'],{},dict(job_id='fixture',job_key='fixture'));record,_=L.read_bound(spawn['path'],spawn)
        good('durable successful Popen before creation lookup',record['pid']==123 and record['creation_time'] is None)
        with patch.object(D.psutil,'Process',side_effect=D.psutil.AccessDenied(123)):
            try:C.psutil.Process(child.pid).create_time()
            except D.psutil.AccessDenied:passed.append('injected post-Popen creation query failure')
            else:raise AssertionError('Creation failure injection did not activate')
            cleaned=D.cleanup_attempt(child,{})
        good('creation lookup failure uses only owned handle',child.terminated==1 and cleaned['unregistered_child_handle']['process_handle_exited'] is True)
        remaining=D.final_owner_states({},child);good('unknown creation retains quiet lease despite handle exit',PRIVATE['release_after_closure'](Path('lock'),Path('archive'),{},remaining)['status']=='RETAINED_OWNED_CLOSURE_UNVERIFIED')
    class Stuck(Child):
        def __init__(self,clock):super().__init__();self.clock=clock;self.waits=[]
        def terminate(self):self.terminated+=1
        def kill(self):pass
        def wait(self,timeout):self.waits.append(timeout);self.clock[0]+=timeout;raise D.subprocess.TimeoutExpired('synthetic',timeout)
    clock=[0.];child=Stuck(clock)
    with patch.object(D.time,'monotonic',side_effect=lambda:clock[0]):result=D.cleanup_attempt(child,{})
    good('shared25s cleanup cap across handle/tree/reap',child.waits==[5.,5.,15.] and result['elapsed_sec']==25.)
    good('original globals remain unchanged',before=={k:id(v) for k,v in C.__dict__.items()})
    return dict(status='PASS_SOURCE_ONLY',checks=passed,inherited_canonical_checks=72,adaptation=ADAPTATION,model_calls=0,native_calls=0,pcm_reads=0)

def source_checks(output):
    result=checks();spec,eb=L.read_bound(REPORT/'EPOCH4_EXECUTION_MANIFEST.json');require(eb['sha256']==EPOCH_SHA,'Exact epoch4 required')
    p,pb=PRIVATE['panel']();routes=candidate_routes(spec,PAIR);selection=selected_panel(p,'cross16_plus4',PAIR)
    result.update(sources=source_bindings(),execution_manifest=eb,panel=pb,exact_registered_routes=list(routes.values()),grid=grid(PAIR,selection),
        source_admission='Metadata only; no current resources, PCM, assets, native body execution or actual candidate manifest prepared.')
    return D.save(output,result)

def main():
    p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);p.add_argument('action',choices=('checks','source-checks','prepare','run','worker'));p.add_argument('--output',type=Path);p.add_argument('--namespace');p.add_argument('--candidates',default='C085,C086');p.add_argument('--panel-mode',choices=('cross16_plus4',),default='cross16_plus4');p.add_argument('--deadline-utc');p.add_argument('--manifest',type=Path);p.add_argument('--quiet-admission',type=Path);p.add_argument('--job-id');p.add_argument('--owner-lease',type=Path);a=p.parse_args()
    required={'source-checks':('output',),'prepare':('namespace','deadline_utc'),'run':('manifest','quiet_admission'),'worker':('manifest','job_id','owner_lease')}
    if any(getattr(a,k) is None for k in required.get(a.action,())):p.error('Missing exact arguments for '+a.action)
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
    sys.dont_write_bytecode=True
    if a.action=='checks':return checks()
    if a.action=='source-checks':return source_checks(a.output)
    return PRIVATE[a.action](a)

if __name__=='__main__':print(json.dumps(main(),indent=2,allow_nan=False))
