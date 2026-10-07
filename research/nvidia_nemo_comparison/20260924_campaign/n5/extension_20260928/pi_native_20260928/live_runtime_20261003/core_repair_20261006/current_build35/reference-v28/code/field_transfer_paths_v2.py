"""Additional exact transfer slots; README_FIELD_TRANSFER_V2.md."""
import re
from pathlib import PurePosixPath
from field_live_paths_v1 import project as base_project
from field_transfer_v2 import CAPS,TOTAL_MAX,ZIP_MAX,META_MAX

EXTRA_BYTES = ZIP_MAX+TOTAL_MAX+2*META_MAX+7*65536
TARGET_MAX = 113517100+EXTRA_BYTES
HOST_MAX = TARGET_MAX+4*1024**2
COMBINED_MAX = TARGET_MAX+HOST_MAX


def project(*,session,conversation,epoch,runtime_token,code_files,import_token):
    if not re.fullmatch('[0-9a-f]{32}',import_token):raise ValueError('One exact import token required')
    value=base_project(session,conversation,epoch,runtime_token,code_files)
    root='data/.archive-imports/'+import_token
    content=root+'/conversations/'+conversation
    paths=value['paths'];buckets=value['buckets']
    directories=set(value['directories'])
    extra={'conversation_exports', 'data/.archive-imports', root,
           root+'/conversations',content,content+'/epochs',content+'/epochs/'+epoch}
    if len(extra)!=7 or extra&directories:raise ValueError('Independent transfer directory reservation')
    directories.update(extra)
    def add(path,cap,bucket,total,count):
        if path in paths:raise ValueError('Duplicate transfer slot')
        paths[path]=dict(maximum_bytes=cap,bucket=bucket)
        entry=dict(maximum_bytes=total,maximum_files=count)
        if bucket in buckets and buckets[bucket]!=entry:raise ValueError('Transfer aggregate disagreement')
        buckets[bucket]=entry
    add('conversation_exports/transfer.zip',ZIP_MAX,'transfer_zip',ZIP_MAX,1)
    for name,cap in CAPS.items():
        if name=='TRANSFER_MANIFEST.json':continue
        rel=name if name=='conversation.json' else 'epochs/'+epoch+'/'+name
        add(content+'/'+rel,cap,'transfer_import',TOTAL_MAX,7)
    for name in ('TRANSFER_MANIFEST.json','RECEIPT.json'):
        add(root+'/'+name,META_MAX,'transfer_controls',2*META_MAX,2)
    value['directories']=sorted(directories)
    value['maximum_bytes']+=EXTRA_BYTES
    value['source_layout_maximum_bytes']=TARGET_MAX
    value['schema']='just-peachy.transfer-physical-paths.v1'
    value['transfer']=dict(import_token=import_token,extra_bytes=EXTRA_BYTES,
                            target_maximum_bytes=TARGET_MAX,host_maximum_bytes=HOST_MAX,
                            combined_request_bytes=COMBINED_MAX)
    if value['maximum_bytes']>TARGET_MAX:raise ValueError('Transfer physical ceiling')
    for name in paths:
        if any(p.as_posix()!='.' and p.as_posix() not in directories for p in PurePosixPath(name).parents):
            raise ValueError('Unreserved transfer parent')
    return value
