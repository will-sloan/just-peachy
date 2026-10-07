"""Explicit complete transfer plus closed-tree backup reservation; README_FIELD_TRANSFER_UI_V1.md."""
from copy import deepcopy
from field_live_layout_v3 import specification as previous,encoded
from field_transfer_paths_v2 import EXTRA_BYTES,TARGET_MAX,HOST_MAX,COMBINED_MAX

def specification():
    value=deepcopy(previous())
    value.update(schema='just-peachy.transfer-layout.v1',status='SAVED_TRANSFER_ONLY',
        target_maximum_bytes=TARGET_MAX,host_maximum_bytes=HOST_MAX,
        host_target_copy_maximum_bytes=TARGET_MAX,combined_request_bytes=COMBINED_MAX)
    value['transfer_extra_maximum_bytes']=EXTRA_BYTES
    value['directories']+=['conversation_exports','data/.archive-imports',
        'data/.archive-imports/<import>','data/.archive-imports/<import>/conversations',
        'data/.archive-imports/<import>/conversations/<conversation>',
        'data/.archive-imports/<import>/conversations/<conversation>/epochs',
        'data/.archive-imports/<import>/conversations/<conversation>/epochs/<epoch>']
    return value
