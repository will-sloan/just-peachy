"""Outer broker allocation; README_FIELD_OPERATOR_BROKER_NATIVE_V1.md."""
from field_operator_session_plan_v1 import allocation as previous
KIB=1024
# Every once file has a separately reserved pending copy. Append files do not.
ONCE={'OWNER.json':16*KIB,'ACK.json':16*KIB,'ENVELOPE.json':32*KIB,
      'CONFIG.json':64*KIB,'MANIFEST.json':128*KIB,'TEMPLATE.json':128*KIB,
      'RESULT.json':64*KIB,'FAILURE.json':16*KIB,
      'STAGE_OWNER.json':16*KIB,'GATE_OWNER.json':16*KIB,'GATE_RESULT.json':16*KIB}
APPEND={'service.log':128*KIB,'telemetry.jsonl':256*KIB}
CODE_MAXIMUM=2*1024**2
CODE_COUNT=64
CODE_MEMBER_MAXIMUM=128*KIB
DIRECTORY_MAXIMUM=64*KIB
EXTRA=2*sum(ONCE.values())+sum(APPEND.values())+CODE_MAXIMUM+2*DIRECTORY_MAXIMUM

def allocation(count):
    value=previous(count)
    value['schema']='just-peachy.operator-broker-allocation.v1'
    value['broker']=dict(once=ONCE,append=APPEND,code_maximum_bytes=CODE_MAXIMUM,
        code_maximum_files=CODE_COUNT,code_member_maximum_bytes=CODE_MEMBER_MAXIMUM,
        directory_names=['broker','code'],maximum_write_bytes=16*KIB,
        extra_per_side_bytes=EXTRA)
    value['metadata_maximum_bytes']+=EXTRA
    value['target_maximum_bytes']+=EXTRA
    value['host_maximum_bytes']+=EXTRA
    value['combined_request_bytes']+=2*EXTRA
    return value
