"""Concrete parent metadata extension; README_FIELD_OPERATOR_PARENT_V1.md."""
from field_transfer_paths_v2 import project as previous
from field_operator_layout_v2 import PARENT_NAMES,PARENT_EXTRA,TARGET_MAX,HOST_MAX,COMBINED_MAX
def project(**kwargs):
    value=previous(**kwargs)
    if 'parent_control' in value['directories']:raise ValueError('Parent directory collision')
    value['directories']=sorted(value['directories']+['parent_control'])
    value['paths']['parent_control/.budget.guard']=dict(maximum_bytes=0,bucket='parent_guard')
    value['buckets']['parent_guard']=dict(maximum_bytes=0,maximum_files=1)
    for name in PARENT_NAMES:
        key='parent_control/'+name
        value['paths'][key]=dict(maximum_bytes=16384,bucket=key)
        value['paths'][key+'.pending']=dict(maximum_bytes=16384,bucket=key)
        value['buckets'][key]=dict(maximum_bytes=16384,maximum_files=1)
    value['maximum_bytes']+=PARENT_EXTRA
    value['source_layout_maximum_bytes']=TARGET_MAX
    value['schema']='just-peachy.operator-parent-physical.v1'
    value['parent_extra_maximum_bytes']=PARENT_EXTRA
    value['transfer'].update(target_maximum_bytes=TARGET_MAX,host_maximum_bytes=HOST_MAX,combined_request_bytes=COMBINED_MAX)
    if value['maximum_bytes']>TARGET_MAX:raise ValueError('Parent physical maximum')
    return value
