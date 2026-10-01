"""Live and transfer independent slots; README_FIELD_OPERATOR_V1.md."""
from field_transfer_layout_v1 import specification as previous
from field_live_layout_v3 import encoded,finite_json

def specification():
    value=previous()
    value['schema']='just-peachy.operator-child-layout.v1'
    value['status']='PREPARED_LIVE_DATA_COMPOSITION_UNEXECUTED'
    return value

def validate(value):
    if type(value) is not dict or encoded(value)!=encoded(specification()):
        raise ValueError('Exact operator child allocation required')
    return value
