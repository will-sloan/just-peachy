"""Exact selected-panel runner/reviewer lineage. README_APPLICATION_FAMILY_V4.md."""
from pathlib import Path

from common import bind, load, verify
from metric_process import exact_process
from review_scoring_bank import require

HERE=Path(__file__).resolve().parent
LOCAL=HERE.parents[4]/'local'
QUALIFICATION='APPLICATION_FAMILY_CHECK_V4.json'
STATUS='PASS_V4_APPLICATION_FAMILY_DEVELOPMENT_ONLY'
MAX_CODE_RECORDS=256
OWN=('application_family_v4.py','paced_child_admission_v2.py','paced_application_runner_v4.py',
    'review_application_transport_v4.py','review_application_cell_v4.py','review_application_panel_v4.py',
    'test_paced_child_admission_v2.py','test_paced_application_runner_v4.py',
    'test_application_transport_review_v4.py','test_application_cell_review_v4.py',
    'test_application_panel_review_v4.py','test_application_family_v4.py',
    'probe_application_family_v4.py','README_APPLICATION_FAMILY_V4.md')
PARENTS={
    'PACED_PANEL_PLAN_CHECK_V4.json':'PASS_V3_SCORED_PANEL_PLANNER_DEVELOPMENT_ONLY',
    'PACED_RUNNER_CHECK_V3.json':'PASS_PACED_RUNNER_V3_DEVELOPMENT_ONLY',
    'PACED_CHILD_ADMISSION_CHECK_V1.json':'PASS_CHILD_ADMISSION_GUARD_DEVELOPMENT_ONLY',
    'APPLICATION_TRANSPORT_REVIEW_CHECK_V3.json':'PASS_APPLICATION_TRANSPORT_V3_REVIEW_DEVELOPMENT_ONLY',
    'APPLICATION_CELL_REVIEW_CHECK_V3.json':'PASS_V3_APPLICATION_CELL_REVIEW_DEVELOPMENT_ONLY',
    'APPLICATION_PANEL_REVIEW_CHECK_V3.json':'PASS_V3_PANEL_CENSUS_REVIEW_DEVELOPMENT_ONLY',
}


def code_bindings():
    """Retain every parent dependency, including tests and preserved implementations."""
    values=[bind(HERE/name) for name in OWN]
    for name,status in PARENTS.items():
        qb=bind(HERE/name);q=load(qb['path'])
        require(q['status']==status and q['N4_accepted'] is False and q['integrated_N4_cells']==0,
            'Unqualified application-family parent')
        verify(q['private_receipt']);proof=load(q['private_receipt']['path']);verify(proof['admission'])
        a=load(proof['admission']['path'])
        require(a['code']==q['code'] and exact_process(a['owner']) is None,
            'Application-family parent probe remains active or code differs')
        values += [qb,*q['code']]
    unique={}
    for b in values:
        require(b['path'] not in unique or unique[b['path']]==b,'Conflicting application-family dependency')
        unique[b['path']]=b
    require(0<len(unique)<=MAX_CODE_RECORDS,'Application-family code census exceeds fixed cap')
    result=[b for _,b in sorted(unique.items())]
    for b in result:verify(b)
    return result
