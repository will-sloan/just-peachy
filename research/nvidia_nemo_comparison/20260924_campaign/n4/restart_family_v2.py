"""Exact selected-panel runner/reviewer lineage. README_RESTART_FAMILY_V2.md."""
from pathlib import Path

from common import bind, load, verify
from metric_process import exact_process
from review_scoring_bank import require

HERE=Path(__file__).resolve().parent
LOCAL=HERE.parents[4]/'local'
QUALIFICATION='RESTART_FAMILY_CHECK_V2.json'
STATUS='PASS_V2_RESTART_FAMILY_DEVELOPMENT_ONLY'
MAX_CODE_RECORDS=512
OWN=('restart_family_v2.py','restart_application_plan_v2.py','restart_application_runner_v2.py',
    'review_restart_run_v2.py','review_restart_content_run_v2.py','test_restart_plan_v2.py',
    'test_restart_runner_v2.py','test_restart_run_review_v2.py','test_restart_content_run_v2.py',
    'test_restart_family_v2.py','probe_restart_family_v2.py','README_RESTART_FAMILY_V2.md')
PARENTS={
    'APPLICATION_FAMILY_CHECK_V4.json':'PASS_V4_APPLICATION_FAMILY_DEVELOPMENT_ONLY',
    'RESTART_PLAN_CHECK_V1.json':'PASS_RESTART_PLANNER_DEVELOPMENT_ONLY',
    'RESTART_RUNNER_CHECK_V1.json':'PASS_RESTART_RUNNER_DEVELOPMENT_ONLY',
    'RESTART_CONTENT_RUN_CHECK_V1.json':'PASS_RESTART_CONTENT_RUN_DEVELOPMENT_ONLY',
}



def code_bindings():
    """Retain every parent dependency, including tests and preserved implementations."""
    values=[bind(HERE/name) for name in OWN]
    for name,status in PARENTS.items():
        qb=bind(HERE/name);q=load(qb['path'])
        require(q['status']==status and q['N4_accepted'] is False and q['integrated_N4_cells']==0,
            'Unqualified restart-family parent')
        verify(q['private_receipt']);proof=load(q['private_receipt']['path']);verify(proof['admission'])
        a=load(proof['admission']['path'])
        require(a['code']==q['code'] and exact_process(a['owner']) is None,
            'Restart-family parent probe remains active or code differs')
        values += [qb,*q['code']]
    unique={}
    for b in values:
        require(b['path'] not in unique or unique[b['path']]==b,'Conflicting restart-family dependency')
        unique[b['path']]=b
    require(0<len(unique)<=MAX_CODE_RECORDS,'Restart-family code census exceeds fixed cap')
    result=[b for _,b in sorted(unique.items())]
    for b in result:verify(b)
    return result


def qualification(code=None):
    code=code_bindings() if code is None else code
    qb=bind(HERE/QUALIFICATION);q=load(qb['path'])
    require(q['status']==STATUS and q['code']==code and q['N4_accepted'] is False
        and q['actual_restart_qualified'] is False and q['integrated_N4_cells']==0,
        'Restart family is not qualified')
    verify(q['private_receipt']);verify(q['private_admission'])
    proof=load(q['private_receipt']['path']);a=load(q['private_admission']['path'])
    require(proof['status']=='PASS_V2_RESTART_FAMILY_CHECKS_ONLY'
        and proof['admission']==q['private_admission'] and a['code']==code
        and exact_process(a['owner']) is None and proof['N4_accepted'] is False
        and proof['actual_restart_qualified'] is False,'Restart family probe is active or differs')
    verify(qb)
    return qb,q
