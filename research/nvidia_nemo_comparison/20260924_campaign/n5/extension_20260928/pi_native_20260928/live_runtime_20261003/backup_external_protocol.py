"""Exact08 external-common probe derivation. README_BACKUP_EXTERNAL.md."""
COMMON_SHA256='103c24c099b946289172cf432288ef1db5abf1c744afb2f27b3f7b361d6d7aa8'
SCHEMA='just-peachy.external-backup-common.v1'


def native_probe_overlay(source):
    anchor="    common=load(package/'backup_reconciliation.py',request['backup_reconciliation_sha256'])"
    if source.count(anchor)!=1:raise ValueError('Exact08 probe common-module boundary required')
    replacement="""    import re
    external=Path(request['job']['output_root'])
    if (re.fullmatch(re.escape(probe.ROOT)+r'production-backup-[0-9]{2}',str(external)) is None or
        request['job'].get('external_backup_schema')!='just-peachy.external-backup-common.v1' or
        request['job'].get('external_backup_common_sha256')!='103c24c099b946289172cf432288ef1db5abf1c744afb2f27b3f7b361d6d7aa8' or
        request['backup_reconciliation_sha256']!='103c24c099b946289172cf432288ef1db5abf1c744afb2f27b3f7b361d6d7aa8'):
        raise ValueError('Exact reviewed external backup job/source pin required')
    common=load(external/'backup_reconciliation.py','103c24c099b946289172cf432288ef1db5abf1c744afb2f27b3f7b361d6d7aa8')"""
    result=source.replace(anchor,replacement)
    anchor="    emit(status)\n    if request['mode']=='catalog':"
    if result.count(anchor)!=1:raise ValueError('Exact08 probe admission boundary required')
    result=result.replace(anchor,"""    external_pin=admission['payload'].get('external_backup_common',{})
    if external_pin.get('schema')!='just-peachy.external-backup-common.v1' or external_pin.get('sha256')!='103c24c099b946289172cf432288ef1db5abf1c744afb2f27b3f7b361d6d7aa8':
        raise ValueError('Actual backup admission external helper pin differs')
"""+anchor)
    compile(result,'<owned-external-backup-probe>','exec');return result.encode()
