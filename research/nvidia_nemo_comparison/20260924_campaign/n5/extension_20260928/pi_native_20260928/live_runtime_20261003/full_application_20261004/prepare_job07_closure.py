"""Prepare the exact job07 closure/copy derivative. See README_JOB07_CLOSURE.md."""
import psutil
psutil.Process().cpu_affinity([14])
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import uuid


def main():
    here=Path(__file__).resolve().parent
    private=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
    output=private/'audit-preparation'/('job07-closure-'+uuid.uuid4().hex);output.mkdir()
    owner=psutil.Process();started=time.time()
    def put(name,value):
        with (output/name).open('x') as stream:
            json.dump(value,stream,sort_keys=True,allow_nan=False);stream.flush();os.fsync(stream.fileno())
    put('REGISTERED_OWNER.json',dict(pid=owner.pid,create_time=owner.create_time(),affinity=[14]))
    put('HOST_SCOPE.json',dict(issued_unix=started,maximum_seconds=600,maximum_bytes=2*1024**2,native_action=False))
    exact_root='/home/peachyprototype/JustPeachy/research/nemotron-20260928/live-runtime-tests-20261003/classic-ui-check-07'
    branch='''    # Only the already issued build20 manual-Stop job has this larger copy reservation.
    if job.get('output_root') == %r:
        if (job.get('unit') != 'jp-v29-classic-ui-check-07.service'
                or job.get('package_manifest_sha256') != 'f42216e8169aa2b0be0b40c7fd0d9cf45542e2bf04b0e4405a95cc2189437659'
                or job.get('helper_source_sha256') != '4d0bef169c54d90769d50bb0f9a1becb6ae7ff80d438892e6dc7c57d59754b87'
                or type(job.get('maximum_output_bytes')) is not int
                or job['maximum_output_bytes'] != 512*1024**2
                or not 0 < job['deadline_unix']-job['issued_unix'] <= 581):
            raise ValueError('Exact issued job07 manual-Stop closure/copy contract required')
        return 512*1024**2,256
''' % exact_root
    destination=here/'job07_closure';destination.mkdir(exist_ok=False)
    job=json.loads((private/'classic-ui-check-07-JOB.json').read_text())
    rows=[]
    for name in ('monitor_native_job.py','native_job_probe.py'):
        original=(here.parent/name).read_bytes()
        text=original.decode();marker='def job_limits(job):\n'
        assert text.count(marker)==1
        # insert after the function's optional docstring, retaining all other AST nodes.
        tree=ast.parse(text);node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='job_limits')
        first=node.body[0]
        line=first.end_lineno if isinstance(first,ast.Expr) and isinstance(first.value,ast.Constant) and isinstance(first.value.value,str) else node.lineno
        lines=text.splitlines(keepends=True);lines.insert(line,branch)
        raw=''.join(lines).encode();after=ast.parse(raw)
        before_functions={n.name:ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        after_functions={n.name:ast.dump(n,include_attributes=False) for n in after.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        assert set(before_functions)==set(after_functions)
        assert {n for n in before_functions if before_functions[n]!=after_functions[n]}=={'job_limits'}
        fn=next(n for n in after.body if isinstance(n,ast.FunctionDef) and n.name=='job_limits')
        scope={'ROOT':exact_root.rsplit('/',1)[0]+'/', 'MAX_OUTPUT':256*1024**2,'MAX_FILES':256,'re':__import__('re'),'encoded':lambda v:json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'<pure-job-limits>','exec'),scope)
        assert scope['job_limits'](job)==(512*1024**2,256)
        rejects=0
        for field,value in [('unit','wrong'),('package_manifest_sha256','0'*64),('helper_source_sha256','0'*64),('maximum_output_bytes',True),('maximum_output_bytes',512*1024**2+1),('deadline_unix',job['issued_unix']+582)]:
            bad=dict(job);bad[field]=value
            try:scope['job_limits'](bad)
            except ValueError:rejects+=1
            else:raise AssertionError(field)
        generic=dict(job,output_root=exact_root[:-2]+'08')
        assert scope['job_limits'](generic)==(256*1024**2,256)
        compile(raw,str(destination/name),'exec')
        for directory,data in [('original',original),('backup',raw),('restore',raw)]:
            (output/directory).mkdir(exist_ok=True)
            with (output/directory/name).open('xb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
            assert (output/directory/name).read_bytes()==data
        (destination/name).write_bytes(raw)
        assert (destination/name).read_bytes()==raw
        rows.append(dict(path=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),rejects=rejects,only_changed_function='job_limits'))
    for name in ('prepare_job07_closure.py','README_JOB07_CLOSURE.md'):
        for directory in ('backup','restore'):
            shutil.copyfile(here/name,output/directory/name)
            assert (output/directory/name).read_bytes()==(here/name).read_bytes()
    total=sum(p.stat().st_size for p in output.rglob('*') if p.is_file())
    assert total<2*1024**2 and time.time()-started<600
    put('SOURCE_CLOSED.json',dict(files=rows,independent_restores=True,native_action=False,closed_unix=time.time(),bytes_before_receipt=total))
    print(json.dumps(dict(status='PASS',output=str(output),derivative=str(destination))))


if __name__=='__main__':main()
