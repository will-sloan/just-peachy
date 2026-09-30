"""Explicit archive accounting; README_FIELD_ARCHIVE_BUDGET_V1.md."""
import hashlib
import json
import os
from pathlib import Path
import uuid

MIB=1024**2
DEFAULT=dict(schema='just-peachy.archive-budget.v1', metadata_input_bytes=16*MIB,
             auxiliary_bytes=2*MIB, control_file_bytes=65536, compact_index='none')

def validate(value):
    if type(value) is not dict or set(value)!=set(DEFAULT):
        raise ValueError('Archive budget fields must be exact')
    if value['schema']!=DEFAULT['schema'] or value['compact_index']!='none':
        raise ValueError('Only compact decoding without SQLite is supported')
    for key,low,high in [('metadata_input_bytes',1024,16*MIB),('auxiliary_bytes',512,2*MIB),('control_file_bytes',16384,65536)]:
        if type(value[key]) is not int or not low<=value[key]<=high:
            raise ValueError('Invalid archive budget: '+key)
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
