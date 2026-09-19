"""Build a reviewed compact S6B handoff. See README_S6B_PACKAGE.md."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import uuid
import zipfile

MAX_ZIP_BYTES = 20 * 1024**2
MAX_SOURCE_BYTES = 64 * 1024**2
MAX_MEMBER_BYTES = 16 * 1024**2
MANIFEST_NAME = 'PACKAGE_MANIFEST.json'
ALLOWED = {'.md','.json','.csv','.tsv','.txt','.py','.ps1','.bat','.cmd','.toml','.yaml','.yml','.png','.svg'}
REQUIRED_GATES = {'final_review','challenge_completion','full_completion'}
SUCCESS = {'PASS','COMPLETE','COMPLETE_PASS'}


def utc(): return datetime.now(timezone.utc).isoformat()
def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def encode(value): return (json.dumps(value,indent=2,allow_nan=False)+'\n').encode('utf-8')
def binding(path, expected=None):
    path=Path(path).resolve(strict=True)
    if not path.is_file(): raise ValueError('Expected regular file: '+str(path))
    before=path.stat();h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024**2),b''):h.update(block)
    after=path.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('Source changed during read: '+str(path))
    if expected is not None and h.hexdigest()!=expected:raise ValueError('SHA256 mismatch: '+str(path))
    return dict(path=str(path),bytes=before.st_size,sha256=h.hexdigest())
def publish_bytes(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    with temporary.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    # A same-directory hard link atomically admits a fully closed file and never
    # replaces an existing archive/receipt, including a concurrent publisher.
    os.link(temporary,path)
    temporary.unlink()  # Only this invocation's own temporary link.
def archive_name(value):
    if not isinstance(value,str) or not value or '\\' in value or ':' in value or any(ord(x)<32 for x in value):raise ValueError('Invalid archive path')
    p=PurePosixPath(value)
    if p.is_absolute() or value!=p.as_posix() or any(x in {'','.','..'} for x in value.split('/')):raise ValueError('Noncanonical archive path: '+value)
    for part in p.parts:
        if part.endswith((' ','.')) or re.match(r'(?i)^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)',part):raise ValueError('Unsafe Windows member path')
    return value
def compact_member(name):
    p=PurePosixPath(name)
    if p.suffix.lower() not in ALLOWED:raise ValueError('Noncompact or forbidden member type: '+name)
    if any(x.lower() in {'logs','journals','sessions','models','audio','raw_audio'} for x in p.parts[:-1]):raise ValueError('Raw artifact folder forbidden: '+name)
    if p.name.lower() in {'events.json','events.txt','transcript_raw.txt','audio_spool.txt','stdout.txt','stderr.txt'}:raise ValueError('Full native log forbidden: '+name)
def pointer(value,path):
    if path=='':return value
    if not isinstance(path,str) or not path.startswith('/'):raise ValueError('Use a JSON pointer beginning /')
    for key in path[1:].split('/'):
        key=key.replace('~1','/').replace('~0','~')
        value=value[int(key)] if isinstance(value,list) else value[key]
    return value


def inspect_spec(path):
    spec_binding=binding(path);spec=read(path)
    if spec.get('schema')!='s6b-handoff-build.v1':raise ValueError('Unsupported package spec schema')
    if not isinstance(spec.get('metadata'),dict) or not isinstance(spec.get('stage_status'),dict):raise ValueError('Metadata and stage_status objects required')
    target=Path(spec['output_path'])
    if not target.is_absolute() or target.suffix.lower()!='.zip':raise ValueError('Absolute .zip output_path required')
    target=target.resolve();gates=[]
    if len(spec['gates'])!=3 or {g['name'] for g in spec['gates']}!=REQUIRED_GATES:raise ValueError('Exactly the three named completion/review gates are required')
    for gate in spec['gates']:
        if not Path(gate['source']).is_absolute():raise ValueError('Gate source must be absolute')
        expected=gate['expected_status']
        if expected not in SUCCESS or (gate['name']=='final_review' and expected!='PASS'):raise ValueError('Gate must require explicit successful status; final_review requires PASS')
        b=binding(gate['source'],gate['sha256']);value=read(b['path'])
        if pointer(value,gate.get('status_pointer','/status'))!=expected:raise ValueError('Gate not passed: '+gate['name'])
        if spec['stage_status'].get(gate['name'])!=expected:raise ValueError('stage_status must match the verified gate')
        checks=[]
        for assertion in gate.get('assertions',[]):
            actual=pointer(value,assertion['pointer'])
            if actual!=assertion['equals']:raise ValueError('Gate assertion failed: '+gate['name']+' '+assertion['pointer'])
            checks.append(dict(pointer=assertion['pointer'],equals=actual))
        gates.append(dict(name=gate['name'],binding=b,status_pointer=gate.get('status_pointer','/status'),verified_status=expected,assertions=checks))
    members=[];names=set();sources=set();figures={};total=0
    for member in spec['members']:
        if not Path(member['source']).is_absolute():raise ValueError('Whitelisted source must be absolute')
        name=archive_name(member['archive_path']);compact_member(name);normalized=name.casefold()
        if normalized in names or normalized==MANIFEST_NAME.casefold():raise ValueError('Duplicate/reserved archive path: '+name)
        names.add(normalized);b=binding(member['source'],member.get('sha256'));source=Path(b['path'])
        if source==target or source.suffix.lower() not in ALLOWED:raise ValueError('Forbidden source type even if renamed in archive')
        compact_member(source.name)
        if str(source).casefold() in sources:raise ValueError('Duplicate source under multiple archive names')
        sources.add(str(source).casefold())
        if b['bytes']>MAX_MEMBER_BYTES:raise ValueError('Member exceeds16MiB compact limit: '+name)
        total+=b['bytes']
        if total>MAX_SOURCE_BYTES:raise ValueError('Whitelisted payload exceeds64MiB uncompressed')
        row=dict(source=b,archive_path=name)
        if source.suffix.lower() in {'.png','.svg'} or PurePosixPath(name).suffix.lower() in {'.png','.svg'}:
            figure_id=member.get('figure_id')
            if not isinstance(figure_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',figure_id):raise ValueError('Scientific image needs an explicit figure_id')
            extension=PurePosixPath(name).suffix.lower()
            if extension!=source.suffix.lower():raise ValueError('Image source/member type differs')
            if extension in figures.setdefault(figure_id,set()):raise ValueError('At most one PNG and one SVG per scientific figure')
            figures[figure_id].add(extension);row['figure_id']=figure_id
        elif 'figure_id' in member:raise ValueError('figure_id only applies to PNG/SVG')
        members.append(row)
    if not members or len(members)>512 or len(figures)>6:raise ValueError('Require1..512 compact files and at most6 scientific figures')
    artifact_name=archive_name(spec['artifact_index_archive_path'])
    artifacts=next((r for r in members if r['archive_path']==artifact_name),None)
    if artifacts is None or PurePosixPath(artifact_name).suffix.lower()!='.json':raise ValueError('A supplied JSON local artifact index must be whitelisted')
    index=read(artifacts['source']['path'])
    index_rows=index.get('artifacts',index.get('rows'))
    if not isinstance(index_rows,list) or not index_rows:raise ValueError('Artifact index requires nonempty artifacts or rows')
    for row in index_rows:
        if not isinstance(row,dict) or not Path(row.get('path','')).is_absolute() or not re.fullmatch(r'[a-fA-F0-9]{64}',row.get('sha256','')):raise ValueError('Local artifact index rows require absolute path and SHA256')
    # Bind the spec again after reading all members to detect concurrent edits.
    binding(path,spec_binding['sha256'])
    return spec,target,dict(schema='s6b-package-member-manifest.v1',created_utc=utc(),metadata=spec['metadata'],stage_status=spec['stage_status'],
        build_spec=spec_binding,packager=binding(__file__),gates=gates,members=members,scientific_figure_count=len(figures),
        archive_member_count=len(members)+1,source_payload_bytes=total,artifact_index_archive_path=artifact_name,
        provenance='This manifest binds every copied member and excludes its own bytes. ZIP SHA256 and verification receipt are external.')


def verify_zip(archive,verification_root):
    root=Path(verification_root);root.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(archive,'r') as z:
        if z.testzip() is not None:raise ValueError('ZIP CRC failure')
        infos=z.infolist();names=[i.filename for i in infos]
        if len(names)!=len(set(n.casefold() for n in names)):raise ValueError('ZIP duplicate member')
        for info in infos:
            archive_name(info.filename)
            if info.is_dir() or info.file_size>MAX_MEMBER_BYTES:raise ValueError('Unexpected directory/oversized archive member')
        manifest=json.loads(z.read(MANIFEST_NAME));expected={r['archive_path']:r for r in manifest['members']}
        if set(names)!=set(expected)|{MANIFEST_NAME}:raise ValueError('ZIP member inventory differs')
        z.extractall(root)
    # New process, reopened ZIP, CRC plus filesystem extraction: hashes here are
    # computed from independently extracted bytes, not writer buffers.
    rows=[]
    for name,row in expected.items():
        b=binding(root/Path(*PurePosixPath(name).parts),row['source']['sha256'])
        if b['bytes']!=row['source']['bytes']:raise ValueError('Unzipped length differs')
        rows.append(dict(archive_path=name,bytes=b['bytes'],sha256=b['sha256']))
    result=dict(status='PASS',verified_members=len(rows),crc_pass=True,independent_extracted_hashes=rows,verifier_pid=os.getpid(),verification_root=str(root))
    publish_bytes(root/'VERIFICATION_RECEIPT.json',encode(result));return result


def build(path):
    spec,target,manifest=inspect_spec(path)
    receipt_path=target.with_suffix('.receipt.json');checksum_path=target.with_suffix('.sha256')
    if any(p.exists() for p in (target,receipt_path,checksum_path)):raise FileExistsError('Final archive/checksum/receipt already exists; no overwrite')
    target.parent.mkdir(parents=True,exist_ok=True)
    temporary=target.with_name('.'+target.name+'.'+uuid.uuid4().hex+'.building')
    with temporary.open('xb') as raw:
        with zipfile.ZipFile(raw,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=False) as z:
            for member in manifest['members']:
                b=member['source'];binding(b['path'],b['sha256'])
                with Path(b['path']).open('rb') as f:data=f.read()
                if len(data)!=b['bytes'] or hashlib.sha256(data).hexdigest()!=b['sha256']:raise ValueError('Copied member changed')
                z.writestr(member['archive_path'],data)
            z.writestr(MANIFEST_NAME,encode(manifest))
        raw.flush();os.fsync(raw.fileno())
    if temporary.stat().st_size>MAX_ZIP_BYTES:raise ValueError('ZIP exceeds20MiB; oversized staged archive retained for diagnosis')
    verification_root=target.parent/('.package_verification_'+uuid.uuid4().hex)
    command=[sys.executable,str(Path(__file__).resolve()),'verify','--archive',str(temporary),'--verification-root',str(verification_root)]
    completed=subprocess.run(command,capture_output=True,text=True,timeout=60,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if completed.returncode:raise RuntimeError('Independent ZIP verification failed: '+completed.stderr[-2000:])
    verification=read(verification_root/'VERIFICATION_RECEIPT.json')
    if verification['status']!='PASS' or verification['verified_members']!=len(manifest['members']):raise ValueError('Incomplete independent verification')
    for member in manifest['members']:binding(member['source']['path'],member['source']['sha256'])
    for gate in manifest['gates']:binding(gate['binding']['path'],gate['binding']['sha256'])
    binding(path,manifest['build_spec']['sha256'])
    # Publish without replacement only after all independent checks pass.
    os.link(temporary,target);temporary.unlink()
    archive_binding=binding(target)
    publish_bytes(checksum_path,(archive_binding['sha256']+'  '+target.name+'\n').encode())
    receipt=dict(schema='s6b-package-verification-receipt.v1',status='PASS',created_utc=utc(),archive=archive_binding,
        build_spec=manifest['build_spec'],packager=manifest['packager'],member_manifest_sha256=hashlib.sha256(encode(manifest)).hexdigest(),
        copied_members=len(manifest['members']),scientific_figure_count=manifest['scientific_figure_count'],gates=manifest['gates'],
        independent_verification=binding(verification_root/'VERIFICATION_RECEIPT.json'),checksum_file=binding(checksum_path),
        maximum_zip_bytes=MAX_ZIP_BYTES,no_prior_archive_overwritten=True,source_mutations=0,
        scope='Packages only the supplied reviewed compact whitelist; stage completion is asserted only by the bound supplied gate receipts.')
    publish_bytes(receipt_path,encode(receipt))
    return dict(status='PASS',archive=archive_binding,receipt=str(receipt_path),copied_members=len(manifest['members']))


def self_test(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=False);checks=[]
    proof=root/'proof.json';publish_bytes(proof,encode(dict(status='PASS',completed=4,requested=4)))
    report=root/'report.md';publish_bytes(report,b'# Synthetic package fixture\n')
    artifact=root/'LOCAL_ARTIFACT_INDEX.json';publish_bytes(artifact,encode(dict(artifacts=[binding(report)])))
    members=[dict(source=str(report),archive_path='report.md',sha256=binding(report)['sha256']),dict(source=str(artifact),archive_path='LOCAL_ARTIFACT_INDEX.json')]
    gates=[dict(name=name,source=str(proof),sha256=binding(proof)['sha256'],expected_status='PASS',assertions=[dict(pointer='/completed',equals=4)]) for name in sorted(REQUIRED_GATES)]
    spec=dict(schema='s6b-handoff-build.v1',metadata=dict(stage='SYNTHETIC_FIXTURE_ONLY'),stage_status={k:'PASS' for k in REQUIRED_GATES},
        output_path=str(root/'fixture.zip'),members=members,gates=gates,artifact_index_archive_path='LOCAL_ARTIFACT_INDEX.json')
    spec_path=root/'spec.json';publish_bytes(spec_path,encode(spec));result=build(spec_path)
    assert result['status']=='PASS';checks.append('Valid fixture: copy hashes, independent subprocess unzip, CRC, external checksum and receipt')
    original=binding(root/'fixture.zip')
    try:build(spec_path)
    except FileExistsError:checks.append('Existing final archive cannot be overwritten')
    else:raise AssertionError('Overwrite accepted')
    assert binding(root/'fixture.zip')==original
    with zipfile.ZipFile(root/'fixture.zip') as z:
        m=json.loads(z.read(MANIFEST_NAME));assert MANIFEST_NAME not in {x['archive_path'] for x in m['members']}
    checks.append('Finite member manifest excludes itself')
    def reject(label,change):
        variant=json.loads(json.dumps(spec));variant['output_path']=str(root/(str(len(checks))+'.zip'));change(variant)
        p=root/(str(len(checks))+'.json');publish_bytes(p,encode(variant))
        try:inspect_spec(p)
        except (ValueError,KeyError):checks.append(label)
        else:raise AssertionError('Invalid fixture accepted: '+label)
    reject('Traversal member rejected',lambda s:s['members'][0].update(archive_path='../report.md'))
    reject('Absolute member rejected',lambda s:s['members'][0].update(archive_path='C:/report.md'))
    reject('Casefold duplicate member rejected',lambda s:s['members'].append(dict(source=str(proof),archive_path='REPORT.MD')))
    reject('Audio member rejected',lambda s:s['members'][0].update(archive_path='audio.wav'))
    reject('Word member rejected',lambda s:s['members'][0].update(archive_path='workbook.docx'))
    reject('Model member rejected',lambda s:s['members'][0].update(archive_path='weights.onnx'))
    reject('Vector bank member rejected',lambda s:s['members'][0].update(archive_path='vectors.npz'))
    reject('Full journal/log member rejected',lambda s:s['members'][0].update(archive_path='logs/events.json'))
    reject('Changed source bytes rejected',lambda s:s['members'][0].update(sha256='0'*64))
    reject('Incomplete gate rejected',lambda s:s['gates'][0].update(expected_status='INCOMPLETE'))
    reject('Changed gate binding rejected',lambda s:s['gates'][0].update(sha256='0'*64))
    reject('Completion count assertion rejected',lambda s:s['gates'][0].update(assertions=[dict(pointer='/completed',equals=5)]))
    reject('Missing local artifact index rejected',lambda s:s.update(artifact_index_archive_path='absent.json'))
    image=root/'figure.svg';publish_bytes(image,b'<svg xmlns="http://www.w3.org/2000/svg"/>')
    reject('Unlabelled scientific figure rejected',lambda s:s['members'].append(dict(source=str(image),archive_path='figure.svg')))
    figure_sources=[]
    for i in range(7):
        p=root/('figure'+str(i)+'.svg');publish_bytes(p,('<svg><!--'+str(i)+'--></svg>').encode());figure_sources.append(p)
    reject('Seventh scientific figure rejected',lambda s:s['members'].extend(dict(source=str(p),archive_path=p.name,figure_id='F'+str(i)) for i,p in enumerate(figure_sources)))
    paired=json.loads(json.dumps(spec));paired['output_path']=str(root/'paired.zip')
    png=root/'figure.png';publish_bytes(png,bytes.fromhex('89504e470d0a1a0a'))
    paired['members'].extend([dict(source=str(image),archive_path='figure.svg',figure_id='F1'),dict(source=str(png),archive_path='figure.png',figure_id='F1')])
    paired_path=root/'paired.json';publish_bytes(paired_path,encode(paired));_,_,paired_manifest=inspect_spec(paired_path)
    assert paired_manifest['scientific_figure_count']==1;checks.append('PNG/SVG pair counts as one scientific figure')
    # Exercise the actual size refusal with a tiny fixture ceiling, restoring
    # the20MiB production constant immediately; no large useless test payload.
    global MAX_ZIP_BYTES
    saved_limit=MAX_ZIP_BYTES;MAX_ZIP_BYTES=1
    try:
        try:build(paired_path)
        except ValueError as exc:
            assert 'exceeds20MiB' in str(exc);checks.append('Oversized staged archive refused before final publication')
        else:raise AssertionError('Size cap ignored')
    finally:MAX_ZIP_BYTES=saved_limit
    assert not (root/'paired.zip').exists()
    damaged=root/'damaged.zip';data=bytearray((root/'fixture.zip').read_bytes())
    with zipfile.ZipFile(root/'fixture.zip') as z:
        info=z.infolist()[0];offset=info.header_offset+30+len(info.filename.encode())+len(info.extra)
    data[offset]^=0x20;publish_bytes(damaged,data)
    try:verify_zip(damaged,root/'damaged_extract')
    except (ValueError,RuntimeError,zipfile.BadZipFile):checks.append('Corrupt archive CRC/decoded member rejected')
    else:raise AssertionError('Corrupt archive accepted')
    result=dict(status='PASS',tests=len(checks),fixtures=checks,code=binding(__file__),root=str(root),real_handoff_built=False,neural_models_started=0)
    publish_bytes(root/'TEST_RECEIPT.json',encode(result));return result


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    b=sub.add_parser('build');b.add_argument('--spec',type=Path,required=True)
    c=sub.add_parser('check');c.add_argument('--root',type=Path,required=True)
    v=sub.add_parser('verify');v.add_argument('--archive',type=Path,required=True);v.add_argument('--verification-root',type=Path,required=True)
    args=p.parse_args()
    if args.command=='build':result=build(args.spec)
    elif args.command=='check':result=self_test(args.root)
    else:result=verify_zip(args.archive,args.verification_root)
    print(json.dumps({k:v for k,v in result.items() if k not in {'fixtures','independent_extracted_hashes'}},indent=2))
if __name__=='__main__':main()
