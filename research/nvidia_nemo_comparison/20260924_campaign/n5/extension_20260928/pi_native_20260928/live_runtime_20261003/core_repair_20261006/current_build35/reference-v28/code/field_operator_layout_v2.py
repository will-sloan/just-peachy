"""Explicit parent plus child allocation; README_FIELD_OPERATOR_PARENT_V1.md."""
from field_transfer_layout_v1 import specification as previous
from field_live_layout_v3 import encoded,finite_json
PARENT_NAMES=('REQUEST.json','OWNER.json','ACK.json','RESULT.json','FAILURE.json','LIVE_ENVELOPE.json')
PARENT_EXTRA=6*16384+65536
TARGET_MAX=180167212+PARENT_EXTRA
HOST_MAX=TARGET_MAX+4194304
COMBINED_MAX=TARGET_MAX+HOST_MAX
def specification():
    value=previous()
    value['schema']='just-peachy.operator-parent-layout.v1'
    value['status']='PREPARED_PARENT_CHILD_NATIVE_UNEXECUTED'
    value['groups']['parent_control']={name:dict(producer='launcher',maximum_bytes=16384,
        maximum_write_bytes=16384,mode='once',maximum_files=1) for name in PARENT_NAMES}
    value['directories'].append('parent_control')
    value['sidecar_maximum_bytes']+=6*16384
    value['directory_reserve_bytes']+=65536
    value.update(parent_extra_maximum_bytes=PARENT_EXTRA,target_maximum_bytes=TARGET_MAX,
        host_target_copy_maximum_bytes=TARGET_MAX,host_maximum_bytes=HOST_MAX,combined_request_bytes=COMBINED_MAX)
    return value
def validate(value):
    if type(value) is not dict or encoded(value)!=encoded(specification()):
        raise ValueError('Exact parent/child allocation required')
    return value
