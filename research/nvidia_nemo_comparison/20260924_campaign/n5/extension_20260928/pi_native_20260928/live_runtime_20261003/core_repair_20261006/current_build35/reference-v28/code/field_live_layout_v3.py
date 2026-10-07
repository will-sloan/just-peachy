"""Explicit parent/child output slots; README_FIELD_LIVE_SOURCE_V1.md."""
from copy import deepcopy
from field_live_layout_v2 import specification as previous, slot, encoded, finite_json


def specification():
    value = deepcopy(previous())
    # Parent TRACE/config/transport and child terminal failures are independent
    # producers. They must never compete for one diagnostic/closure slot.
    value['groups']['failure']['transport_child.bin'] = slot('transport_child', 65536, 65536)
    value['groups']['failure']['transport_child.json'] = slot('transport_child', 8192, 8192)
    value['groups']['closure']['transport_child.json'] = slot('transport_child', 32768, 32768)
    value['artifacts']['raw_microphones']=dict(path='data/RAW_MICROPHONES.s32le',**slot('source',33280000,65536,'append'))
    value['artifact_maximum_bytes']+=33280000
    value['groups']['source']['RAW_CAPTURE.json']=slot('source',65536,65536)
    value['groups']['config']['RAW_SELECTION.json']=slot('entry',65536,65536)
    extra = 65536+8192+32768+131072
    value['sidecar_maximum_bytes'] += extra
    for key in ('target_maximum_bytes','host_target_copy_maximum_bytes','host_maximum_bytes'):
        value[key] += extra+33280000
    value['combined_request_bytes'] += 2*(extra+33280000)
    value['schema'] = 'just-peachy.live-layout.v2'
    value['status'] = 'LIVE_SOURCE_BINDING_PREPARED_FULL_ENTRY_OPEN'
    return value


def validate(value):
    if type(value) is not dict or encoded(value) != encoded(specification()):
        raise ValueError('Exact production live layout required')
    return value
