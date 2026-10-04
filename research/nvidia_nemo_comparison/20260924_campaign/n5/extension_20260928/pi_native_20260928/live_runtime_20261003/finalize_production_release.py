"""Host-only explicitly reviewed frozen release builder; README_PRODUCTION_FINALIZATION.md."""
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import time
import uuid

BUILDER_SHAS = {'8deb7b4f6ae26071597b00e27b85b401f3f9606205f026fcd451b85a46099876',
                '0a706522770d21d8b4846d3121cc430eef81ec73fcced965eca7d804fbf47832'}
PRIVATE = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
PARENT = '/home/peachyprototype/JustPeachy/research/nemotron-20260928/'
IMPORTS = ('profiles','optional_refiner_admission','release_authorization','optional_refiner_dispatch','install_candidate')
PLAN_FIELDS = ('target','candidate_content_sha256','installed_manifest_sha256','previous_desktop_sha256',
               'allowed_selections','optional_refiner_admissions','assets','limits','full_backup')
PROOF_PURPOSES = {'qualification','history_export','full_backup','selection_matrix','limitations'}


def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def strict(raw):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('Duplicate review key')
            result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda v:(_ for _ in ()).throw(ValueError(v)))


def sha(raw):return hashlib.sha256(raw).hexdigest()


def read(path,maximum=2*1024**2):
    path=Path(path);before=path.lstat()
    if path.resolve(strict=True)!=path or not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>maximum:
        raise ValueError('Canonical bounded single-link input required')
    with path.open('rb') as handle:raw=handle.read(maximum+1)
    after=path.stat()
    if len(raw)>maximum or (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):
        raise ValueError('Input changed while reading')
    return raw


def pinned(row,maximum=2*1024**2):
    if set(row)!={'path','sha256'} or re.fullmatch('[0-9a-f]{64}',row['sha256']) is None:
        raise ValueError('Exact local path and SHA256 required')
    raw=read(Path(row['path']),maximum)
    if sha(raw)!=row['sha256']:raise ValueError('Pinned input changed')
    return raw


def write(path,raw):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as handle:
        if handle.write(raw)!=len(raw):raise OSError('Short publication')
        handle.flush();os.fsync(handle.fileno())
    if path.read_bytes()!=raw:raise OSError('Independent readback mismatch')


def reviewed_acceptance(review,plan,source_binding):
    expected={'schema','reviewed','reviewer','reviewed_unix','source','destination_target','builder',
              'relocation_certificate','production_plan','proofs','optional_documents','limitations'}
    if (set(review)!=expected or review['schema']!='just-peachy.production-finalization-review.v1'
        or review['reviewed'] is not True or not isinstance(review['reviewer'],str) or not review['reviewer'].strip()
        or type(review['reviewed_unix']) not in (int,float) or not math.isfinite(review['reviewed_unix'])
        or not 0<review['reviewed_unix']<=time.time()+60):raise ValueError('Explicit completed final human/agent review required')
    destination=review['destination_target']
    if (re.fullmatch(re.escape(PARENT)+r'field-runtime-v29-build-[0-9]+',destination) is None
        or destination==source_binding['target']):raise ValueError('Fresh independent destination release required')
    if (plan.get('accepted') is not False or plan['target']!=destination
        or plan['candidate_content_sha256']!=source_binding['candidate_content_sha256']
        or plan['installed_manifest_sha256']!=source_binding['installed_manifest_sha256']):
        raise ValueError('Exact unaccepted same-content production plan required')
    if (type(review['limitations']) is not list or not 1<=len(review['limitations'])<=32
        or any(type(v) is not str or not 1<=len(v)<=2048 for v in review['limitations'])):
        raise ValueError('Explicit bounded limitations review required')
    proofs=review['proofs']
    if (type(proofs) is not list or not 5<=len(proofs)<=32
        or not PROOF_PURPOSES<={row.get('purpose') for row in proofs}):raise ValueError('Actual proof review is incomplete')
    if any(row.get('optional_d1_refiner') for row in plan['allowed_selections']):
        if 'optional_live_measured' not in {row.get('purpose') for row in proofs}:raise ValueError('Optional actual live review missing')
    acceptance={key:copy.deepcopy(plan[key]) for key in PLAN_FIELDS}
    acceptance.update(schema='just-peachy.v29.production-acceptance.v1',accepted=True,
        reviewer=review['reviewer'],accepted_unix=review['reviewed_unix'],limitations=review['limitations'],
        review_evidence=[dict(purpose=row['purpose'],sha256=row['sha256']) for row in proofs])
    return acceptance


def optional_metadata(acceptance,binding,documents,modules):
    """Only exact measured references become post-content package members."""
    dispatch=modules['optional_refiner_dispatch'];admission=modules['optional_refiner_admission'];profiles=modules['profiles']
    refs=dispatch.validate_references(acceptance.get('optional_refiner_admissions',[]))
    if type(documents) is not list or len(documents)!=len(refs):raise ValueError('Every optional reference needs exactly one document')
    documents_by_path={row['native_path']:row for row in documents}
    if len(documents_by_path)!=len(documents) or set(documents_by_path)!={ref['path'] for ref in refs}:
        raise ValueError('Optional document membership differs')
    files={}
    for ref in refs:
        row=documents_by_path[ref['path']]
        if set(row)!={'native_path','path','sha256'} or row['sha256']!=ref['sha256']:
            raise ValueError('Exact optional source document pin required')
        prefix=binding['target']+'/authorization/'
        if not ref['path'].startswith(prefix):raise ValueError('Optional proof must live in destination authorization directory')
        name=ref['path'][len(binding['target'])+1:]
        if re.fullmatch(r'authorization/optional-[0-9a-f]{64}\.json',name) is None or PurePosixPath(name).as_posix()!=name:
            raise ValueError('Content-addressed optional package member required')
        if name!='authorization/optional-'+ref['sha256']+'.json':raise ValueError('Optional filename must bind actual SHA256')
        raw=pinned({key:row[key] for key in ('path','sha256')},65536);value=strict(raw)
        if value.get('schema')!=admission.SCHEMA:raise ValueError('Measured normal admission required, never first qualification permit')
        selection=profiles.RuntimeSelection(**ref['selection']);policy=profiles.SessionPolicy(**ref['policy'])
        admission.validate_admission(raw,ref['sha256'],selection,policy,dispatch.expected_pins(binding,ref),0,
            physical_ram_bytes=value.get('measured',{}).get('total_ram_bytes'),phase='historical_evidence')
        if ref['selection'] not in acceptance['allowed_selections']:raise ValueError('Optional document has no accepted selection')
        files[name]=raw
    return files


def extend_builder(raw,filename,post_content):
    """One AST insertion: after BINDING exists, before backups/manifest/archive."""
    if sha(raw) not in BUILDER_SHAS:raise ValueError('Exact reviewed external builder required')
    tree=ast.parse(raw,filename=filename);build=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='build')
    matches=[i for i,node in enumerate(build.body) if isinstance(node,ast.Assign)
        and len(node.targets)==1 and ast.unparse(node.targets[0])=="files['BINDING.json']"]
    if len(matches)!=1:raise ValueError('Exact post-content builder insertion point required')
    build.body.insert(matches[0]+1,ast.parse('files.update(_reviewed_post_content(production, binding))').body[0])
    ast.fix_missing_locations(tree)
    namespace={'__name__':'_reviewed_production_builder','__file__':filename,'_reviewed_post_content':post_content}
    exec(compile(tree,filename,'exec'),namespace)
    return namespace,tree


def load_modules(source,manifest):
    pins={row['path']:row for row in manifest['files']};modules={}
    for name in IMPORTS:
        if name in sys.modules:raise ValueError('Production dependency already imported: '+name)
        path=source/(name+'.py');raw=read(path);row=pins[name+'.py']
        if (len(raw),sha(raw))!=(row['bytes'],row['sha256']):raise ValueError('Frozen dependency pin changed')
        spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
        sys.modules[name]=module;exec(compile(raw,str(path),'exec'),module.__dict__)
        if Path(module.__file__).resolve()!=path:raise ValueError('Dependency import origin differs')
        modules[name]=module
    return modules


def finalize(review_path,review_sha,output):
    raw=pinned(dict(path=str(review_path),sha256=review_sha),262144);review=strict(raw)
    source_ref=review['source']
    if set(source_ref)!={'path','manifest_sha256','binding_sha256','content_sha256'}:raise ValueError('Complete frozen source pins required')
    source=Path(source_ref['path']);manifest_raw=pinned(dict(path=str(source/'PACKAGE_MANIFEST.json'),sha256=source_ref['manifest_sha256']))
    binding_raw=pinned(dict(path=str(source/'BINDING.json'),sha256=source_ref['binding_sha256']),65536)
    manifest=strict(manifest_raw);binding=strict(binding_raw)
    if (manifest['candidate_content_sha256']!=source_ref['content_sha256']
        or binding['candidate_content_sha256']!=source_ref['content_sha256'] or manifest['target']!=binding['target']):
        raise ValueError('Source content pins differ')
    plan_raw=pinned(review['production_plan'],262144);plan=strict(plan_raw)
    acceptance=reviewed_acceptance(review,plan,binding)
    builder_raw=pinned(review['builder']);certificate_raw=pinned(review['relocation_certificate'],65536)
    proof_rows=[]
    for index,row in enumerate(review['proofs']):
        if set(row)!={'purpose','path','sha256'} or not isinstance(row['purpose'],str) or len(row['purpose'])>64:
            raise ValueError('Bounded exact proof reference required')
        proof_raw=pinned({key:row[key] for key in ('path','sha256')})
        write(output/'review-proofs'/('%02d.json'%index),proof_raw);proof_rows.append(dict(row,bytes=len(proof_raw)))
    modules=load_modules(source,manifest)
    try:
        modules['install_candidate'].verify_tree(source,source_ref['manifest_sha256'])
        modules['release_authorization'].validate_acceptance(acceptance,dict(binding,target=review['destination_target']))
        captured={}
        def post_content(production,destination_binding):
            if production!=acceptance:raise ValueError('Builder production acceptance differs')
            additions=optional_metadata(acceptance,destination_binding,review['optional_documents'],modules)
            captured.update(additions);return additions
        builder,tree=extend_builder(builder_raw,review['builder']['path'],post_content)
        for name,data in (('REVIEW.json',raw),('PRODUCTION_ACCEPTANCE.json',encoded(acceptance)),
                          ('RELOCATION_CERTIFICATE.json',certificate_raw),('prepare_package.py',builder_raw)):
            write(output/'inputs'/name,data);write(output/'input-restores'/name,data)
        result=builder['build'](source,source/'profiles',output,
            release_id=review['destination_target'].rsplit('/',1)[1],production_path=output/'inputs/PRODUCTION_ACCEPTANCE.json',
            snapshot_manifest_sha256=source_ref['manifest_sha256'],
            relocation_certificate_path=output/'inputs/RELOCATION_CERTIFICATE.json',
            relocation_certificate_sha256=sha(certificate_raw))
        if result['candidate_content_sha256']!=source_ref['content_sha256']:raise ValueError('Runtime content changed during finalization')
        modules['install_candidate'].verify_tree(Path(result['package']),result['manifest_sha256'])
        for name,data in captured.items():
            if read(Path(result['package'])/name,65536)!=data:raise ValueError('Optional authorization publication differs')
        receipt=dict(status='BUILT_REVIEWED_PRODUCTION_NOT_INSTALLED',source=source_ref,destination=result,
            review_sha256=review_sha,optional_metadata=[dict(path=name,bytes=len(data),sha256=sha(data)) for name,data in captured.items()],
            builder_ast_change='one post-content metadata insertion; all other builder AST unchanged',
            proof_pins=proof_rows,native_executed=False,desktop_changed=False)
        write(output/'FINALIZATION.json',encoded(receipt));return receipt
    finally:
        for name in IMPORTS:sys.modules.pop(name,None)


def main():
    import psutil
    me=psutil.Process();me.cpu_affinity([14])
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--review',type=Path,required=True);ap.add_argument('--review-sha256',required=True)
    ap.add_argument('--execute-reviewed-build',action='store_true',required=True)
    args=ap.parse_args()
    output=PRIVATE/'storage-preparation'/('production-finalization-'+uuid.uuid4().hex);output.mkdir()
    write(output/'REGISTERED_OWNER.json',encoded(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])))
    for drive,gib in (('C:/',50),('G:/',75)):
        if shutil.disk_usage(drive).free<gib*1024**3+128*1024**2:raise OSError('Independent finite finalization reserve')
    try:result=finalize(args.review,args.review_sha256,output)
    except BaseException as error:
        write(output/'FAILED.json',encoded(dict(status='FAILED_PRESERVED',error=repr(error),native_executed=False)));raise
    print(json.dumps(dict(status=result['status'],output=str(output),manifest_sha256=result['destination']['manifest_sha256'])))


if __name__=='__main__':main()
