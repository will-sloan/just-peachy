"""Exact installed compact transfer derivative; README_FIELD_TRANSFER_V1.md."""
import ast
import hashlib
from pathlib import Path
import types

MIB = 1024**2
ZIP_MAX = 32*MIB
TOTAL_MAX = 31*MIB
META_MAX = 65536
CAPS = {'conversation.json':65536, 'epoch.json':65536, 'events.jsonl':16*MIB,
        'resources.jsonl':2*MIB, 'windows.jsonl':2*MIB,
        'model_input.f32le':8*MIB, 'model_input.wav':4*MIB,
        'TRANSFER_MANIFEST.json':65536}
EPOCH_FILES = frozenset(CAPS)-{'conversation.json','TRANSFER_MANIFEST.json'}


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def derive(raw, expected_sha256, module_name='field_transfer_derived'):
    """Retain installed validators/Store bodies except exact reviewed replacements."""
    if hashlib.sha256(raw).hexdigest()!=expected_sha256:
        raise ValueError('Installed transfer source changed')
    source=raw.decode('utf-8')
    changes=[
        ("ZIP_MAX = 8*MIB","ZIP_MAX = 32*MIB"),
        ("TOTAL_MAX = 32*MIB","TOTAL_MAX = 31*MIB"),
        ("FILE_MAX = 8*MIB","FILE_MAX = 16*MIB"),
        ("META_MAX = MIB","META_MAX = 65536"),
        ("'model_input.f32le', 'model_input.wav', 'captions.sqlite'}",
         "'model_input.f32le', 'model_input.wav'}"),
        ("if len(files)>128 or sum(files.values())>TOTAL_MAX or max(files.values(),default=0)>FILE_MAX:",
         "if len(files)>7 or sum(files.values())>TOTAL_MAX or any(size>member_cap(name) for name,size in files.items()):"),
        ("not 1<=len(epochs)<=8","len(epochs)!=1"),
        ("if len(wav.readframes(n))!=n*2:raise ValueError('Truncated PCM')",
         "left=n\n            while left:\n                frames=min(left,8192);block=wav.readframes(frames)\n                if len(block)!=frames*2:raise ValueError('Truncated PCM')\n                left-=frames"),
        ("with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:",
         "with zipfile.ZipFile(output,'w',zipfile.ZIP_STORED) as z:"),
        ("z.writestr(MANIFEST,json.dumps(manifest,sort_keys=True))",
         "manifest_raw=json.dumps(manifest,sort_keys=True).encode('utf-8')\n                if len(manifest_raw)>META_MAX:raise ValueError('Transfer manifest limit')\n                z.writestr(MANIFEST,manifest_raw)"),
        ("len(infos)>129","len(infos)!=8"),
        ("info.file_size>FILE_MAX","info.file_size>member_cap(info.filename)"),
        ("staging=self.data_root/'.archive-imports'/uuid.uuid4().hex;staging.mkdir(parents=True,exist_ok=False)",
         "imports=self.data_root/'.archive-imports';imports.mkdir(exist_ok=True)\n                staging=imports/uuid.uuid4().hex;staging.mkdir(exist_ok=False)"),
        ("content=staging/'conversations'/identifier;content.mkdir(parents=True)",
         "parents=staging/'conversations';parents.mkdir()\n                content=parents/identifier;content.mkdir()"),
        ("(staging/MANIFEST).write_text(json.dumps(m,indent=2),encoding='utf-8')",
         "write_control(staging/MANIFEST,m)"),
        ("target=content/name;target.parent.mkdir(parents=True,exist_ok=True);h=hashlib.sha256();count=0",
         "target=content/name\n                        ensure_parents(content,target.parent)\n                        h=hashlib.sha256();count=0"),
        ("(staging/'RECEIPT.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')",
         "write_control(staging/'RECEIPT.json',receipt)"),
    ]
    for old,new in changes:
        if source.count(old)!=1:
            raise ValueError('Installed transfer shape changed: '+old[:96])
        source=source.replace(old,new)
    ast.parse(source)
    module=types.ModuleType(module_name)
    module.__file__='<exact-installed-transfer-derivative>'
    exec(compile(source,module.__file__,'exec'),module.__dict__)
    def member_cap(name):
        module.safe_name(name)
        return CAPS[name.rsplit('/',1)[-1]]
    original_json=module.strict_json
    def strict_json(data):
        value=original_json(data)
        module.bounded_json(value)
        return value
    def ensure_parents(root, target):
        if not target.is_relative_to(root):raise ValueError('Import parent escape')
        for part in reversed((target,)+tuple(target.parents)):
            if part==root or part.is_relative_to(root):part.mkdir(exist_ok=True)
    def write_control(path,value):
        raw=module.json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
        if len(raw)>META_MAX:raise ValueError('Transfer control limit')
        with path.open('xb') as stream:
            if stream.write(raw)!=len(raw):raise OSError('Short transfer control write')
            stream.flush();module.os.fsync(stream.fileno())
    module.member_cap=member_cap
    module.strict_json=strict_json
    module.ensure_parents=ensure_parents
    module.write_control=write_control
    module.derivation=dict(source_sha256=expected_sha256,changes=len(changes),
                           zip_max=ZIP_MAX,total_max=TOTAL_MAX,member_caps=CAPS,
                           epochs=1,stream_chunk_bytes=65536,pcm_read_bytes=16384,
                           scope='one complete compact audio epoch; persisted event bytes unchanged')
    return module


def bind_installed(module, expected_sha256, guard):
    """Bind the exact derived installed Store class before Field construction."""
    raw=Path(module.__file__).read_bytes()
    derived=derive(raw,expected_sha256)
    # Class function global lookups must use the same derived dictionary.
    derived.rename_noreplace=guard.publish_import
    module.FieldArchiveStore=derived.FieldArchiveStore
    return derived


def verify_zip(module,path,folder,identifier):
    """Full unencrypted ZIP readback before any explicitly authorized copied delete."""
    summary=module.validate_folder(folder,identifier)
    files=module.regular_tree(folder)
    with module.zipfile.ZipFile(path) as archive:
        infos=archive.infolist()
        if len(infos)!=8 or len({x.filename for x in infos})!=8:
            raise ValueError('Exact transfer ZIP membership')
        if set(x.filename for x in infos)!=set(files)|{module.MANIFEST}:
            raise ValueError('Transfer ZIP membership changed')
        manifest=module.strict_json(archive.read(module.MANIFEST))
        if manifest.get('schema')!=module.SCHEMA or manifest.get('identifier')!=identifier:
            raise ValueError('Transfer identity')
        if set(manifest.get('files',{}))!=set(files):raise ValueError('Transfer bindings')
        checked={}
        for name,size in files.items():
            info=archive.getinfo(name)
            if info.file_size!=size or info.compress_type!=module.zipfile.ZIP_STORED or info.flag_bits&1:
                raise ValueError('Transfer member size/type')
            h=hashlib.sha256();count=0
            with archive.open(name) as stream:
                while block:=stream.read(16384):h.update(block);count+=len(block)
            digest=h.hexdigest()
            if count!=size or digest!=sha(folder/name) or manifest['files'][name]!={'bytes':size,'sha256':digest}:
                raise ValueError('Transfer member readback')
            checked[name]=dict(bytes=size,sha256=digest)
    if path.stat().st_size>ZIP_MAX:raise ValueError('ZIP physical limit')
    return dict(identifier=identifier,files=checked,zip_sha256=sha(path),zip_bytes=path.stat().st_size,
                validation=summary,readback=True)
