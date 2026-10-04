"""Pure explicit-selection and reviewed path-relocation helpers. See README.md."""
import copy
import hashlib
import json


def encoded(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def operator_matrix(profiles):
    """Default control values only; not permission or a native qualification."""
    rows=[]
    for source in ('live','saved'):
        for embedding in ('redimnet','titanet','anonymous'):
            rows.append(profiles.RuntimeSelection('pyannote',embedding,source).validate())
        for profile in profiles.catalog():
            for embedding in ('redimnet','titanet','anonymous'):
                for attribution in ('retained','single_d1_late_labels'):
                    schedules=('continuous',) if embedding=='anonymous' else ('continuous','sparse_clean_turn')
                    for schedule in schedules:
                        experimental=bool(profile['experimental'] or attribution!='retained' or schedule!='continuous')
                        rows.append(profiles.RuntimeSelection('nemotron',embedding,source,profile['id'],
                            allow_experimental=experimental,embedding_schedule=schedule,speaker_attribution=attribution).validate())
    canonical={encoded(row) for row in rows}
    if len(canonical)!=len(rows) or len(rows)>256:raise ValueError('Explicit unique matrix exceeds existing acceptance capacity')
    return dict(schema='just-peachy.operator-selection-review-matrix.v1',accepted=False,native_qualification_claimed=False,
        optional_parallel_included=False,provisional_correction_included=False,rows=rows,
        defaults=dict(embedding_refresh_seconds=2.0,revision_window_seconds=30,refinement_period_seconds=5,
            refinement_profile='current_delayed'),
        experimental_flag_policy='minimum required by selected profile or presentation/schedule; default false otherwise',
        scope='reviewable supported default control combinations, not a native Cartesian campaign or automatic release authorization')


def relocation_certificate(source_binding,source_raw,manifest_sha,destination_target,reviewer,reviewed_unix,builder):
    """Generate only after explicit review; builder is the exact reviewed guard."""
    destination=copy.deepcopy(source_binding);before=source_binding['target'];moves=[]
    def move(field,value):
        if value==before:updated=destination_target
        elif type(value) is str and value.startswith(before+'/'):updated=destination_target+value[len(before):]
        else:raise ValueError('Only exact source-root paths can move')
        moves.append(dict(field=field,source=value,destination=updated));return updated
    for key in ('target','reference_code','raw_factory_path'):destination[key]=move(key,destination[key])
    for key,row in destination['profiles'].items():row['path']=move('profiles.'+key+'.path',row['path'])
    certificate=dict(schema='just-peachy.reviewed-runtime-relocation.v1',reviewed=True,reviewer=reviewer,
        reviewed_unix=reviewed_unix,source_target=before,destination_target=destination_target,
        source_manifest_sha256=manifest_sha,source_binding_sha256=hashlib.sha256(source_raw).hexdigest(),
        candidate_content_sha256=source_binding['candidate_content_sha256'],installed_manifest_sha256=source_binding['installed_manifest_sha256'],
        source_operational_binding_sha256=hashlib.sha256(encoded(builder.operational_binding(source_binding))).hexdigest(),
        destination_operational_binding_sha256=hashlib.sha256(encoded(builder.operational_binding(destination))).hexdigest(),
        relocations=sorted(moves,key=lambda row:row['field']),runtime_behavior_changed=False,measurement_reuse_requires_separate_review=True)
    builder.validate_relocation(certificate,source_binding,destination,manifest_sha,source_raw)
    return certificate,destination


def reuse_measured_admission(source_receipt_raw,source_receipt_sha,certificate_raw,certificate_sha,
        source_binding,source_binding_raw,destination_binding,source_manifest_sha,builder,admission,profiles,
        reviewer,reviewed_unix):
    """Preserve actual facts; issue a separately reviewed destination identity.

    Caller must independently approve the actual measurement and closure before
    passing the source receipt. No measured receipt is created from estimates.
    """
    if hashlib.sha256(source_receipt_raw).hexdigest()!=source_receipt_sha or hashlib.sha256(certificate_raw).hexdigest()!=certificate_sha:
        raise ValueError('Exact original measurement and reviewed certificate pins required')
    certificate=json.loads(certificate_raw)
    builder.validate_relocation(certificate,source_binding,destination_binding,source_manifest_sha,source_binding_raw)
    original=json.loads(source_receipt_raw)
    if (original.get('reuse_basis') is not None or original.get('qualified_binding_sha256')!=hashlib.sha256(source_binding_raw).hexdigest() or
        original.get('qualified_package_manifest_sha256')!=source_manifest_sha or
        original.get('pins',{}).get('operational_binding_sha256')!=certificate['source_operational_binding_sha256'] or
        original['pins']['candidate_content_sha256']!=certificate['candidate_content_sha256'] or
        original['pins']['installed_manifest_sha256']!=certificate['installed_manifest_sha256']):
        raise ValueError('Only actual source-root measurement can be reused, never a chain of relabelled receipts')
    selection=profiles.RuntimeSelection(**original['selection']);policy=profiles.SessionPolicy(**original['policy'])
    memory=original['measured']['total_ram_bytes']
    admission.validate_admission(source_receipt_raw,source_receipt_sha,selection,policy,original['pins'],memory,
        physical_ram_bytes=memory,phase='historical_evidence')
    derived=copy.deepcopy(original)
    derived['pins']['operational_binding_sha256']=certificate['destination_operational_binding_sha256']
    derived['reuse_basis']=dict(schema='just-peachy.reviewed-measurement-relocation.v1',reviewed=True,
        reviewer=reviewer,reviewed_unix=reviewed_unix,
        scope='reviewed reuse of '+source_binding['target'].rsplit('-',1)[-1]+' measurement, not '+destination_binding['target'].rsplit('-',1)[-1]+' native execution',
        original_measured_root=source_binding['target'],destination_root=destination_binding['target'],
        original_measured_receipt_sha256=source_receipt_sha,original_qualified_binding_sha256=original['qualified_binding_sha256'],
        original_qualified_package_manifest_sha256=original['qualified_package_manifest_sha256'],
        certificate_sha256=certificate_sha,source_operational_binding_sha256=certificate['source_operational_binding_sha256'],
        destination_operational_binding_sha256=certificate['destination_operational_binding_sha256'],
        destination_native_execution_claimed=False,measured_facts_changed=False)
    # Every measured fact and closure/source pin remains byte-value identical.
    unchanged=copy.deepcopy(derived);unchanged.pop('reuse_basis')
    unchanged['pins']['operational_binding_sha256']=original['pins']['operational_binding_sha256']
    if encoded(unchanged)!=encoded(original):raise AssertionError('Measured facts changed during relocation')
    raw=encoded(derived)
    admission.validate_admission(raw,hashlib.sha256(raw).hexdigest(),selection,policy,derived['pins'],memory,
        physical_ram_bytes=memory,phase='historical_evidence')
    return derived
