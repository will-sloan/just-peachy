"""Explicit journal-derivative lineage for application preparation. See README_APPLICATION_SOURCE_CONTEXT.md."""
from copy import deepcopy
from pathlib import Path

from common import bind, fingerprint, freeze, load, verify
from metric_process import exact_process
from paced_child_admission import assert_plain_path
from review_scoring_bank import require

HERE=Path(__file__).resolve().parent
CHANGED={'app/buffers.py','app/pipeline.py'}
ADDED={'app/native_complete_text.py','README_N4_COMPLETE_JOURNAL.md'}
POLICY=dict(events='CompleteText',max_events_bytes=256*1024**2,max_record_bytes=1024**2,
            queue_capacity=4096,overflow='explicit writer failure; preserve prefix',other_journals='unchanged rotating')


def validate_lineage(parent_binding,parent,child):
    require(child['schema']=='n4-complete-journal-derivative-v1' and child['status']=='IMPLEMENTED_NOT_APPLICATION_ADMITTED'
        and child['parent']==parent_binding and child['policy']==POLICY,'Wrong journal derivative lineage or policy')
    require(set(child['changed_files'])==CHANGED and len(child['changed_files'])==2
        and set(child['added_files'])==ADDED and len(child['added_files'])==2,'Journal derivative file changes differ')
    require(set(child['files'])==set(parent['files'])|ADDED and not set(parent['files']).intersection(ADDED),
        'Journal derivative has missing or extra source files')
    changes={name for name in parent['files'] if parent['files'][name]!=child['files'][name]}
    require(changes==CHANGED,'A prediction, frontend or unrelated source file changed')
    require(child['files_sha256']==fingerprint(child['files']) and parent['files_sha256']==fingerprint(parent['files']),
        'Source inventory fingerprint differs')
    for field in ('common_ui_source_sha256','common_ui_files','auxiliary_files','implemented_compositions'):
        require(child[field]==parent[field],'Shared frontend, auxiliary files or composition population changed')
    require(child['implemented_compositions']==16 and child['active_component_source_modified'] is False
        and child['actual_N4_inference_cells']==0 and child['N4_accepted'] is False,'Unsupported source acceptance claim')
    for name,digest in parent['common_ui_files'].items():
        require(child['files'][name]['sha256']==digest,'Common frontend file differs')


def gallery_for_catalog(original,parent_catalog,application_catalog):
    require(original['status']=='PREPARED_VERIFIED_RESEARCH_GALLERIES_ONLY' and original['catalog']==parent_catalog,
        'Gallery is not from the qualified parent catalog')
    require({k:v for k,v in parent_catalog.items() if k!='path'}==
            {k:v for k,v in application_catalog.items() if k!='path'},'Copied catalog bytes differ')
    value=deepcopy(original);value['catalog']=deepcopy(application_catalog)
    return value


def verify_source(binding):
    verify(binding);value=load(binding['path']);root=Path(value['prototype'])
    require(len(value['files'])<=4096,'Source inventory exceeds bound')
    for rel,meta in value['files'].items():
        file=assert_plain_path(root/rel,root);verify(dict(path=str(file),**meta))
    for rel,meta in value['auxiliary_files'].items():
        file=assert_plain_path(root.parent/rel,root.parent);verify(dict(path=str(file),**meta))
    return value


def parents():
    retention=bind(HERE/'NATIVE_JOURNAL_RETENTION_CHECK_V1.json');q=load(retention['path'])
    require(q['status']=='PASS_NATIVE_JOURNAL_RETENTION_DEVELOPMENT_ONLY' and q['tests_passed']==8,
        'Qualified native retention repair required')
    for b in q['code']+[q['private_receipt']]:verify(b)
    tested=load(q['private_receipt']['path']);verify(tested['admission']);admission=load(tested['admission']['path'])
    require(tested['status']=='PASS_NATIVE_JOURNAL_RETENTION_CHECKS_ONLY' and exact_process(admission['owner']) is None
        and tested['source_receipt']==q['source_receipt'] and admission['parent_source']==q['parent_source'],
        'Retention test/source or stopped owner differs')
    application=bind(HERE/'PACED_APPLICATION_CELL_CHECK_V1.json');app=load(application['path'])
    require(app['status']=='PASS_PRIVATE_TK_AND_APPLICATION_PRESTART_ONLY' and app['source_receipt']==q['parent_source'],
        'Original application/source qualification differs')
    for b in app['code']+[app['private_receipt'],app['gallery_preparation']]:verify(b)
    old_test=load(app['private_receipt']['path']);verify(old_test['admission']);old_admission=load(old_test['admission']['path'])
    require(exact_process(old_admission['owner']) is None,'Original application preparation helper still active')
    parent=verify_source(q['parent_source']);child=verify_source(q['source_receipt'])
    validate_lineage(q['parent_source'],parent,child)
    parent_catalog=bind(Path(parent['prototype'])/'config/backends.json')
    catalog=bind(Path(child['prototype'])/'config/backends.json')
    require(old_admission['catalog']==parent_catalog,'Original application catalog differs')
    for b in old_admission['runtimes']:verify(b)
    gallery=gallery_for_catalog(load(app['gallery_preparation']['path']),parent_catalog,catalog)
    return dict(retention_qualification=retention,parent_application_qualification=application,
        component_source_receipt=q['parent_source'],source_receipt=q['source_receipt'],
        component_catalog=parent_catalog,catalog=catalog,component_gallery_preparation=app['gallery_preparation'],
        runtimes=old_admission['runtimes']),gallery


def prepare(output):
    """Prepare metadata only. No voice vector, prediction, roster or threshold changes."""
    output=Path(output);require(not output.exists(),'Fresh application source context output required')
    context,gallery=parents()
    freeze(output/'GALLERIES_PREPARED.json',gallery)
    context.update(schema='n4-journal-application-source-context-v1',status='PREPARED_APPLICATION_SOURCE_CONTEXT_ONLY',
        gallery_preparation=bind(output/'GALLERIES_PREPARED.json'),logging_policy=POLICY,
        copied_catalog_bytes_identical=True,gallery_payload_unchanged_except_catalog_location=True,
        application_prestart_retested=False,model_or_source_started=False,integrated_N4_cells=0,N4_accepted=False)
    freeze(output/'CONTEXT.json',context)
    return bind(output/'CONTEXT.json')


def review(binding):
    """Reconstruct exact context; application plans must separately bind this result."""
    verify(binding);value=load(binding['path']);context,gallery=parents()
    for key,expected in context.items():require(value[key]==expected,'Application context lineage changed')
    require(value['schema']=='n4-journal-application-source-context-v1' and value['status']=='PREPARED_APPLICATION_SOURCE_CONTEXT_ONLY'
        and value['logging_policy']==POLICY and value['copied_catalog_bytes_identical'] is True
        and value['gallery_payload_unchanged_except_catalog_location'] is True
        and value['application_prestart_retested'] is False and value['model_or_source_started'] is False
        and value['integrated_N4_cells']==0 and value['N4_accepted'] is False,'Context contains unsupported preparation claims')
    require(Path(value['gallery_preparation']['path'])==Path(binding['path']).parent/'GALLERIES_PREPARED.json',
        'Rebound gallery is outside the context directory')
    verify(value['gallery_preparation']);require(load(value['gallery_preparation']['path'])==gallery,'Gallery payload changed')
    return value
