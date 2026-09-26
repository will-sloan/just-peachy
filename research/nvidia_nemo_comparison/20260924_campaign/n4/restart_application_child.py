"""Fixed private-desktop restart child; see README_RESTART_CHILD.md."""
import argparse
import ctypes as C
from ctypes import wintypes as W
from pathlib import Path
import sys

import psutil
from common import bind, fingerprint, freeze, load
from metric_process import identity
from paced_child_admission import ChildAdmission, validate_input
from private_application_process_v3 import api, checked
from restart_plan_policy import POLICY, stop_after_samples
from review_scoring_bank import require

HERE=Path(__file__).resolve().parent
OWN=('restart_application_child.py','test_restart_child.py','probe_restart_child.py','README_RESTART_CHILD.md')
SUCCESS='COLLECTED_RESTART_PAIR_CLOSED_REQUIRES_REVIEW'
CHILD_SUCCESS='COLLECTED_RESTART_APPLICATION_PAIR_REQUIRES_REVIEW'


def code_bindings():
    """Preserve the full qualified planner/lifecycle set, plus this fixed child.

    Parent-only native census and coordinator code are not imported here. Their
    larger manifests belong to the parent's separate admission/qualification.
    No existing binding is removed and the child's 128-record limit is unchanged.
    """
    qb=bind(HERE/'RESTART_PLAN_CHECK_V1.json'); q=load(qb['path'])
    require(q['status']=='PASS_RESTART_PLANNER_DEVELOPMENT_ONLY', 'Restart planner qualification differs')
    unique={}
    for b in q['code']+[qb]+[bind(HERE/name) for name in OWN]:
        require(b['path'] not in unique or unique[b['path']]==b, 'Conflicting child dependency')
        unique[b['path']]=b
    require(0<len(unique)<=128, 'Child code binding count exceeded')
    return [b for _,b in sorted(unique.items())]


def actual_desktop():
    kernel,user=api(); kernel.GetCurrentThreadId.argtypes=[]; kernel.GetCurrentThreadId.restype=W.DWORD
    user.GetThreadDesktop.argtypes=[W.DWORD]; user.GetThreadDesktop.restype=W.HANDLE
    desktop=checked(user.GetThreadDesktop(kernel.GetCurrentThreadId()))
    buffer=C.create_unicode_buffer(512); needed=W.DWORD()
    checked(user.GetUserObjectInformationW(desktop,2,buffer,C.sizeof(buffer),C.byref(needed)))
    return buffer.value


def control(payload):
    validate_input(payload)
    job=payload['job']; contract=payload['contract']; threshold=stop_after_samples(job)
    composition='_'.join(contract[k] for k in ('variant','diarization','encoder'))
    require(payload['cell_id']=='restart_0_'+job['job_id']+'_'+composition, 'Wrong paired restart cell identity')
    return dict(policy_sha256=fingerprint(POLICY),stop_after_samples=threshold,full_job_sha256=fingerprint(job),sessions=2)


def closed_result(result, output):
    require(result == load(output/'RESULT.json'), 'Returned closure differs from persisted result')
    require(result['schema']=='n4-restart-application-cell-v1' and result['status']==SUCCESS
        and result['source_start_requested'] is True and result['completed_sessions']==2
        and result['errors']==result['callback_errors']==[] and result['controller_closed'] is True
        and result['controller_worker_exited'] is True and result['failure_delivery_capture'] is None,
        'Restart application did not close both sessions normally')
    require(result['actual_restart_qualified'] is False and result['source_to_widget_latency_qualified'] is False
        and result['complete_N4_acceptance'] is False and result['integrated_N4_cells']==0,
        'Child collection cannot grant acceptance')
    require(result['pair_observation']==bind(output/'PAIR_OBSERVATION.json')
        and result['sessions']==[bind(output/'sessions'/n/'RESULT.json') for n in ('01','02')],
        'Restart pair/session result binding differs')


def child_main(permit_path, nonce):
    # No helper pin(): the admitted suspended launcher already assigned CPU4.
    # An invalid constructor/desktop cannot write evidence to an untrusted path.
    gate=ChildAdmission(permit_path,nonce=nonce,desktop=actual_desktop(),expected_code=code_bindings())
    cell=None; error=None; result=None; planned=None
    try:
        planned=control(gate.payload); gate.check()
        primed=gate.prime(); source=Path(primed['source'])
        sys.path[:0]=[str(source),str(source/'vendor'),str(source.parent)]
        from restart_application_cell import RestartApplicationCell
        gate.check(); payload=gate.payload
        cell=RestartApplicationCell(gate.output,payload['job'],payload['contract'])
        cell.prepare(source=source,models_root=Path(payload['models_root']),runtimes=payload['runtimes'],
            gallery_preparation=payload['gallery_preparation'])
        gate.check(payload['job'],payload['contract'])
        cell.run_pair(admission_check=gate.check,stop_after_samples=planned['stop_after_samples'])
        gate.check(payload['job'],payload['contract'])
    except BaseException as exc:
        error=type(exc).__name__+': '+str(exc)[:2000]
    finally:
        if cell is not None:
            try:
                result=cell.close(); closed_result(result,gate.output)
            except BaseException as exc:error=(error or '')+'; close: '+type(exc).__name__+': '+str(exc)[:1000]
        okay=error is None and result is not None and result['status']==SUCCESS
        freeze(gate.transport/'CHILD_RESULT.json',dict(status=CHILD_SUCCESS if okay else 'FAILED_RESTART_APPLICATION_CHILD_PRESERVED',
            owner=identity(psutil.Process()),input=gate.permit['input'],error=error,restart_control=planned,
            cell_result=bind(gate.output/'RESULT.json') if (gate.output/'RESULT.json').exists() else None,
            actual_restart_qualified=False,integrated_N4_cells=0,N4_accepted=False))
    require(okay, 'Restart child failed; evidence preserved')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--permit',type=Path,required=True);parser.add_argument('--nonce',required=True)
    args=parser.parse_args();child_main(args.permit,args.nonce)
