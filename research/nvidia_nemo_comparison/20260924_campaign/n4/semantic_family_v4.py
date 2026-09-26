"""Exact selected-panel runner/reviewer lineage. README_SEMANTIC_FAMILY_V4.md."""
from pathlib import Path
import json
import os

from common import bind, load, verify, freeze
from metric_process import exact_process
from review_scoring_bank import require

HERE=Path(__file__).resolve().parent
LOCAL=HERE.parents[4]/'local'
QUALIFICATION='SEMANTIC_FAMILY_CHECK_V4.json'
STATUS='PASS_V4_SEMANTIC_FAMILY_DEVELOPMENT_ONLY'
MAX_CODE_RECORDS=512
OWN=('semantic_family_v4.py','review_application_semantics_v4.py','review_semantic_panel_v4.py',
    'review_application_content_panel_v4.py','test_application_semantics_v4.py','test_semantic_panel_v4.py',
    'test_application_content_panel_v4.py','test_semantic_family_v4.py','probe_semantic_family_v4.py',
    'README_SEMANTIC_FAMILY_V4.md')
PARENTS={
    'APPLICATION_FAMILY_CHECK_V4.json':'PASS_V4_APPLICATION_FAMILY_DEVELOPMENT_ONLY',
    'SEMANTIC_PANEL_CHECK_V3.json':'PASS_V3_SEMANTIC_PANEL_DEVELOPMENT_ONLY',
    'APPLICATION_CONTENT_PANEL_CHECK_V1.json':'PASS_APPLICATION_CONTENT_PANEL_DEVELOPMENT_ONLY',
    'RESTART_CONTENT_RUN_CHECK_V1.json':'PASS_RESTART_CONTENT_RUN_DEVELOPMENT_ONLY',
}



def code_bindings():
    """Retain every parent dependency, including tests and preserved implementations."""
    values=[bind(HERE/name) for name in OWN]
    for name,status in PARENTS.items():
        qb=bind(HERE/name);q=load(qb['path'])
        require(q['status']==status and q['N4_accepted'] is False and q['integrated_N4_cells']==0,
            'Unqualified semantic-family parent')
        verify(q['private_receipt']);proof=load(q['private_receipt']['path']);verify(proof['admission'])
        a=load(proof['admission']['path'])
        require(a['code']==q['code'] and exact_process(a['owner']) is None,
            'Semantic-family parent probe remains active or code differs')
        values += [qb,*q['code']]
    unique={}
    for b in values:
        require(b['path'] not in unique or unique[b['path']]==b,'Conflicting semantic-family dependency')
        unique[b['path']]=b
    require(0<len(unique)<=MAX_CODE_RECORDS,'Semantic-family code census exceeds fixed cap')
    result=[b for _,b in sorted(unique.items())]
    for b in result:verify(b)
    return result


OUTPUT_LIMIT=8*1024**2


def freeze_bounded(path,value,output):
    """Account for encoded Windows newlines before writing; keep failure space."""
    require(Path(path).resolve().is_relative_to(Path(output).resolve()),'Output escaped review directory')
    used=sum(p.stat().st_size for p in output.rglob('*') if p.is_file()) if output.exists() else 0
    size=len(os.linesep.encode())
    for chunk in json.JSONEncoder(indent=2,ensure_ascii=False,allow_nan=False).iterencode(value):
        size+=len(chunk.replace('\n',os.linesep).encode('utf-8'))
        require(used+size+65536<=OUTPUT_LIMIT,'Next complete review receipt exceeds output bound')
    freeze(path,value)


def qualification(code=None):
    code=code_bindings() if code is None else code
    qb=bind(HERE/QUALIFICATION);q=load(qb['path'])
    require(q['status']==STATUS and q['code']==code and q['N4_accepted'] is False
        and q['integrated_N4_cells']==0,'Semantic family is not qualified')
    verify(q['private_receipt']);verify(q['private_admission'])
    proof=load(q['private_receipt']['path']);a=load(q['private_admission']['path'])
    require(proof['status']=='PASS_V4_SEMANTIC_FAMILY_CHECKS_ONLY' and proof['admission']==q['private_admission']
        and a['code']==code and exact_process(a['owner']) is None and proof['N4_accepted'] is False,
        'Semantic family probe active or changed')
    verify(qb);return qb,q
