"""Explicit archive accounting; README_FIELD_ARCHIVE_FINALIZATION_V1.md."""
import hashlib
import json
import os
from pathlib import Path
import uuid

MIB=1024**2
DEFAULT=dict(schema='just-peachy.archive-budget.v2', metadata_input_bytes=16*MIB,
             auxiliary_bytes=2*MIB, control_file_bytes=65536, compact_index='none',initial_control_bytes=32768,
             runtime_control_bytes=24576,detail_file_bytes=262144,detail_reserve_bytes=1048576)

def validate(value):
    if type(value) is not dict or set(value)!=set(DEFAULT):
        raise ValueError('Archive budget fields must be exact')
    if value['schema']!=DEFAULT['schema'] or value['compact_index']!='none':
        raise ValueError('Only compact decoding without SQLite is supported')
    for key,low,high in [('metadata_input_bytes',1024,16*MIB),('auxiliary_bytes',512,2*MIB),('control_file_bytes',16384,65536)]:
        if type(value[key]) is not int or not low<=value[key]<=high:
            raise ValueError('Invalid archive budget: '+key)
    for key in ('initial_control_bytes','runtime_control_bytes','detail_file_bytes','detail_reserve_bytes'):
        if type(value[key]) is not int or value[key]!=DEFAULT[key]:raise ValueError('Fixed finalization reserve: '+key)
    if value['control_file_bytes']<value['initial_control_bytes']+value['runtime_control_bytes']+1024:
        raise ValueError('Finalization reserve exceeds control file')
    if value['auxiliary_bytes']<value['detail_reserve_bytes']:
        raise ValueError('No reserved diagnostic capacity')
    return dict(value)

def digest(value):
    return hashlib.sha256(json.dumps(validate(value),sort_keys=True,separators=(',',':')).encode()).hexdigest()

def encode_control(value,limit):
    raw=(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8')
    if len(raw)>limit:raise ValueError('ARCHIVE_CONTROL_BYTE_LIMIT')
    return raw

def publish(path,value,limit):
    # Check exact serialized bytes before creating a temporary file or replacing old data.
    raw=encode_control(value,limit);path=Path(path)
    temporary=path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temporary.open('xb') as f:
            if f.write(raw)!=len(raw):raise OSError('Short control write')
            f.flush();os.fsync(f.fileno())
        os.replace(temporary,path)
        fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
    finally:
        temporary.unlink(missing_ok=True)

class CompactIndex:
    """Compact events never use byte-offset SQLite tables; no index file is created."""
    def commit(self):pass
    def close(self):pass

def error_view(reason):
    raw=str(reason).encode('utf-8')
    if len(raw)<=1024:return str(reason)
    return raw[:768].decode('utf-8',errors='ignore')+' [full failure.txt; bytes='+str(len(raw))+'; sha256='+hashlib.sha256(raw).hexdigest()+']'

def detail(path,raw,limit):
    if len(raw)>limit:return dict(retained=False,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),reason='DIAGNOSTIC_LIMIT')
    path=Path(path)
    if path.exists():
        if path.read_bytes()!=raw:raise ValueError('Immutable failure detail changed')
    else:
        with path.open('xb') as f:
            if f.write(raw)!=len(raw):raise OSError('Short diagnostic write')
            f.flush();os.fsync(f.fileno())
    return dict(retained=True,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),path=path.name)
