"""Add explicit qualification-only saved-to-live composition review. See README.md."""
import psutil
psutil.Process().cpu_affinity([14])
import os,json,uuid,hashlib,ast
from pathlib import Path
Q=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
owner=Q/('presets-preparation-optional-bridge09-'+uuid.uuid4().hex);owner.mkdir()
with (owner/'REGISTERED_OWNER.json').open('x') as stream:
    json.dump(dict(pid=os.getpid(),create_time=psutil.Process().create_time(),affinity=[14]),stream)
    stream.flush();os.fsync(stream.fileno())
base=Path(__file__).parent
source=base/'runtime_derivative09/optional_refiner_qualification.py';raw=source.read_bytes()
if hashlib.sha256(raw).hexdigest()!='727b5935e2d095ff243e9c987177290333e3b17c2b8e06e2c38d1c672ab46cab':
    raise ValueError('Exact reviewed allocation-only derivative required')
text=raw.decode().replace('\r\n','\n')
addition='''def validate_prerequisite_gate(gate,row,selection,binding,pins):
    """Review composition permission without claiming an unrun live primary."""
    selected=selection.validate()
    primary=dict(selected,optional_d1_refiner=False)
    actual_primary=gate.get('primary_selection',{})
    bridge=gate.get('live_composition_review')
    if bridge is not None:
        if row['stage']!='followup_policy' or selected['input_source']!='live':
            raise ValueError('Live composition bridge is followup-only')
        primary['input_source']='saved'
    if actual_primary.get('allow_experimental')!=primary['allow_experimental']:
        if gate.get('permission_only_difference_reviewed') is not True:
            raise ValueError('Explicit prerequisite permission-bit review required')
        primary['allow_experimental']=actual_primary.get('allow_experimental')
    if (gate.get('schema')!='just-peachy.optional-first-prerequisites.v2' or gate.get('reviewed') is not True or
        gate.get('candidate_content_sha256')!=binding['candidate_content_sha256'] or actual_primary!=primary or
        any(gate.get(key) is not True for key in ('primary_functional_pass','gui_functional_pass',
            'all_owners_closed','allow_first_combined_measurement'))):
        raise ValueError('Reviewed exact actual primary and same-code GUI gates required')
    if bridge is None:
        if gate.get('source')!=row['source']:raise ValueError('Exact primary source prerequisite required')
        return False
    expected=dict(schema='just-peachy.optional-live-composition-review.v1',reviewed=True,
        qualification_only=True,live_primary_pass_claimed=False,source_change_reviewed=True,
        matched_model_options_unchanged=True,measured_primary_selection=actual_primary,
        measured_primary_source=gate.get('source'),followup_selection=selected,live_source=row['source'],pins=pins,
        first_combined_feasibility_sha256=row['feasibility_review_sha256'],
        raw_qualification_evidence=binding.get('raw_qualification_evidence'),
        live_config_sha256=hashlib.sha256(encoded(binding['live_config'])).hexdigest(),
        gui_review_sha256=gate['gui_review']['sha256'])
    if bridge!=expected:
        raise ValueError('Exact reviewed saved-primary/live-source composition permission required')
    feasibility=row['reviewed_feasibility']
    validate_feasibility(feasibility,selection,pins)
    if (gate.get('source',{}).get('kind')!='saved' or feasibility.get('source')!=gate['source'] or
        feasibility.get('source_change_reviewed') is not True or
        binding.get('raw_adapter_enabled') is not True or
        binding.get('raw_qualification_evidence',{}).get('qualified') is not True or
        binding.get('raw_qualification_evidence',{}).get('adapter_native_qualified') is not True or
        row['source']!={'kind':'live','config_sha256':bridge['live_config_sha256']}):
        raise ValueError('Actual matched first-combined source and qualified live adapter required')
    # Preserve actual saved primary identity/source. This return authorizes only
    # collection of new live combined evidence; it is never a production pass.
    return True


'''
anchor='def initialize(request,binding,owner_directory,identity,authorization):\n'
if text.count(anchor)!=1:raise ValueError('Exact initializer boundary changed')
text=text.replace(anchor,addition+anchor)
before="""    primary=dict(selection.validate(),optional_d1_refiner=False)
    # Permission-only opt-in is allowed to differ if the reviewer says so;
    # every model/source/identity/presentation field must still match.
    actual_primary=gate.get('primary_selection',{})
    if actual_primary.get('allow_experimental')!=primary['allow_experimental']:
        if gate.get('permission_only_difference_reviewed') is not True:raise ValueError('Explicit prerequisite permission-bit review required')
        primary['allow_experimental']=actual_primary.get('allow_experimental')
    if (gate.get('schema')!='just-peachy.optional-first-prerequisites.v2' or gate.get('reviewed') is not True or
        gate.get('candidate_content_sha256')!=binding['candidate_content_sha256'] or actual_primary!=primary or
        gate.get('source')!=row['source'] or gate.get('primary_functional_pass') is not True or
        gate.get('gui_functional_pass') is not True or gate.get('all_owners_closed') is not True or
        gate.get('allow_first_combined_measurement') is not True):
        raise ValueError('Reviewed same-candidate primary and GUI gates required')
    for key in ('primary_review','gui_review'):read_json(gate[key]['path'],gate[key]['sha256'])
"""
after="""    live_bridge=validate_prerequisite_gate(gate,row,selection,binding,pins)
    for key in ('primary_review','gui_review'):read_json(gate[key]['path'],gate[key]['sha256'])
    if live_bridge:
        raw_proof=binding['raw_qualification_evidence']
        read_json(raw_proof['evidence'],raw_proof['evidence_sha256'])
"""
if text.count(before)!=1:raise ValueError('Exact prior prerequisite guard changed')
text=text.replace(before,after);ast.parse(text)
new=text.replace('\n','\r\n').encode()
destination=base/'runtime_derivative09_bridge';destination.mkdir()
with (destination/'optional_refiner_qualification.py').open('xb') as stream:
    stream.write(new);stream.flush();os.fsync(stream.fileno())
receipt=dict(source_path=str(source),source_sha256=hashlib.sha256(raw).hexdigest(),
    replacement_path=str(destination/'optional_refiner_qualification.py'),replacement_sha256=hashlib.sha256(new).hexdigest(),
    changes=['extract strict actual prerequisite comparison','add followup-only reviewed saved-primary/qualified-live-source composition gate'],
    actual_saved_primary_preserved=True,live_primary_pass_claimed=False,qualification_only=True,
    model_constructor_changes=False,native_execution=False)
with (owner/'SOURCE_DIFFERENCE.json').open('x') as stream:json.dump(receipt,stream,indent=2)
print(json.dumps(receipt));print(owner)
