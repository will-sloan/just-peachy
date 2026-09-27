"""Serialized output-allocation checks; README_RESERVATION_GUARD_V1.md."""
import argparse
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import shutil
import sys
import time

from common import bind, load, verify
from metric_process import exact_process, identity
from reservation_budget_v1 import DEADLINE, GIB, calculate, owner_key, require
from reservation_census_v2 import snapshot

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'supervision'))
from supervisor import lock

OWN = ('reservation_guard_v1.py', 'test_reservation_guard_v1.py',
       'probe_reservation_guard_v1.py', 'README_RESERVATION_GUARD_V1.md')
TERMINAL_RESERVE = 1024**2


def code_bindings():
    from probe_reservation_census_v2 import code_bindings as previous
    code = previous()+[bind(HERE/name) for name in OWN]
    supervisor = bind(HERE.parent/'supervision/supervisor.py')
    if supervisor not in code: code.append(supervisor)
    require(len({b['path'] for b in code}) == len(code), 'Duplicate guard source binding')
    return code


def qualification():
    path = HERE/'RESERVATION_GUARD_CHECK_V1.json'; value = load(path)
    require(value.get('status') == 'PASS_SERIALIZED_RESOURCE_GUARD_DEVELOPMENT_ONLY'
            and value.get('code') == code_bindings()
            and value.get('exact_probe_owner_exited') is True,
            'Resource guard library has not been qualified')
    for b in value['code']+[value['private_result']]: verify(b)
    require(exact_process(value['probe_owner']) is None, 'Guard qualification owner remains active')
    return bind(path)


def output_limit(admission):
    fields = [k for k in ('allocation_bytes', 'maximum_output_bytes') if k in admission]
    require(len(fields) == 1, 'Require exactly one admitted output cap')
    cap = admission[fields[0]]
    require(type(cap) is int and TERMINAL_RESERVE < cap <= 8*GIB, 'Invalid output cap')
    return cap


def validate_boundary(admission, owner, output, local, code, *, lookup=exact_process):
    owner_key(owner)
    require(admission.get('owner') == owner and lookup(owner) is not None,
            'Guard must belong to its exact live admission owner')
    output, local = Path(output).resolve(strict=True), Path(local).resolve(strict=True)
    require(output.is_relative_to(local/'n4') and output != local/'n4', 'Foreign guarded output')
    require(admission.get('code') == code and code and len({b['path'] for b in code}) == len(code),
            'Guard producer source bindings differ')
    return output_limit(admission)


def exact_projection(observed, owner, output, policy, now, peak, *, production, lookup=exact_process):
    """Re-express this already admitted cap as its remainder, exactly once."""
    require(type(production) is bool, 'Explicit production/development scope required')
    active = observed['active_allocations']
    own = [a for a in active if owner_key(a['owner']) == owner_key(owner)]
    require(len(own) == 1 and Path(own[0]['root']).resolve() == Path(output).resolve(),
            'Census must find exactly this guarded allocation')
    require(observed.get('complete_recorded_N4_admission_census') is True
            and observed.get('active_set_supplied_by_caller') is False,
            'Complete discovered allocation set required')
    other = [a for a in active if a is not own[0]]
    cap, used, remainder = (own[0][k] for k in ('allocation_bytes', 'observed_used_bytes', 'remaining_bytes'))
    require(type(cap) is int and TERMINAL_RESERVE < cap <= 8*GIB and type(used) is int
            and 0 <= used <= cap and type(remainder) is int and remainder == cap-used,
            'Discovered own remainder is invalid')
    require(lookup(owner) is not None, 'Guard owner exited during calculation')
    own_root = Path(own[0]['root']).resolve()
    require(all(not Path(a['root']).resolve().is_relative_to(own_root)
                and not own_root.is_relative_to(Path(a['root']).resolve()) for a in other),
            'Another allocation overlaps the guarded output')
    require(observed['inventory']['total_logical_bytes'] >= sum(a['observed_used_bytes'] for a in active),
            'Campaign inventory predates guarded output usage')
    if production:
        require(not other, 'Production waits for every other admitted N4 allocation to close')
        supervision = observed['supervisor']
        require(supervision['state'] == 'RUNNING' and supervision.get('driver') == owner,
                'Production allocation must be the exact supervised driver')
    require(type(peak) is int and peak >= 0 and remainder >= peak+TERMINAL_RESERVE,
            'Own allocation lacks peak and terminal headroom')
    # snapshot(1 byte) conservatively discovers an already admitted owner. Its
    # provisional extra byte is not a second allocation or reclaimable credit.
    result = calculate(observed['inventory'], observed['closed_components'], other,
        remainder, policy, observed['free_bytes'], now, peak_bytes=peak, lookup=lookup)
    expected = observed['inventory']['total_logical_bytes']+sum(a['remaining_bytes'] for a in active)
    expected += result['retained_pending_bytes']+result['contingency_bytes']
    require(result['projected_bytes'] == expected, 'Own allocation counted more or less than once')
    return dict(result, own_admission=own[0]['admission'], own_allocation_bytes=own[0]['allocation_bytes'],
        own_observed_used_bytes=own[0]['observed_used_bytes'], own_remaining_bytes=remainder,
        other_allocation_count=len(other), own_allocation_counted_once=True,
        production_scope_checked=production, new_unrecorded_allocations_authorized=False)


def check_runtime(policy, cap, used, peak, elapsed, maximum_seconds, free, now):
    require(now.tzinfo is not None, 'Timezone-aware runtime check required')
    configured = datetime.fromisoformat(policy['target_utc'])
    require(configured.tzinfo is not None, 'Timezone-aware campaign cutoff required')
    require(now < min(DEADLINE, configured)-timedelta(hours=12), 'Packaging reserve reached')
    require(type(maximum_seconds) is int and 0 < maximum_seconds <= 14400
            and 0 <= elapsed < maximum_seconds, 'Runtime allowance exhausted')
    require(type(cap) is int and TERMINAL_RESERVE < cap <= 8*GIB
            and type(used) is int and used >= 0 and type(peak) is int and peak >= 0
            and used+peak+TERMINAL_RESERVE <= cap, 'Output cap or terminal headroom exhausted')
    for d, floor in (('C:', 50), ('G:', 75)):
        configured_floor = policy['resource_policy']['minimum_free_gib'][d]
        require(type(configured_floor) in (int, float) and configured_floor >= 0,
                'Invalid configured free-space floor')
        require(type(free[d]) is int and free[d] >= max(floor, configured_floor)*GIB+peak,
                'Drive floor or temporary peak headroom exhausted')


class OutputGuard:
    """Holds a separate OS lock; caller writes only a provisional admission first.

    This library cannot authorize a producer by itself. A production caller must
    also require its own qualified execution family, bind that family to its plan
    and admission, and preserve RESULT/FAILED. Do not start work before refresh.
    """
    def __init__(self, local, output, code, main_plan, maximum_seconds, *, production):
        import psutil
        require(type(production) is bool, 'Explicit production/development scope required')
        self.local = Path(local).resolve(strict=True); self.output = Path(output).resolve(strict=True)
        self.code = code; self.main_plan = main_plan; self.maximum_seconds = maximum_seconds
        self.production = production; self.started = time.monotonic(); self.process = psutil.Process()
        self.owner = identity(self.process); self.admission = bind(self.output/'ADMISSION.json')
        admission = load(self.admission['path'])
        self.cap = validate_boundary(admission, self.owner, self.output, self.local, code)
        admitted_seconds = admission.get('maximum_seconds', admission.get('max_seconds'))
        require(type(admitted_seconds) is int and type(maximum_seconds) is int
                and 0 < maximum_seconds <= admitted_seconds <= 14400, 'Runtime exceeds admitted budget')
        self.policy_binding = bind(self.local/'supervision/campaign.json')
        self.lock_context = None; self.held = False; self.last_check = None

    def __enter__(self):
        if self.production: qualification()
        for b in self.code: verify(b)
        self.lock_context = lock(self.local/'n4/reservation-guard.owner.lock', wait=0)
        self.lock_context.__enter__(); self.held = True
        return self

    def fast_check(self, peak=0):
        import psutil
        from asr_full_bank import payload_inventory
        require(self.held, 'Resource lock is not held')
        verify(self.admission)
        require(exact_process(self.owner) is not None and identity(self.process) == self.owner,
                'Guard process identity changed')
        require(self.process.cpu_affinity() == [14]
                and self.process.nice() == psutil.BELOW_NORMAL_PRIORITY_CLASS,
                'Guard coordinator affinity or priority differs')
        require(all(os.environ.get(k) == '1' for k in
                    ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'))
                and os.environ.get('CUDA_VISIBLE_DEVICES') == '', 'Coordinator CPU-only environment differs')
        verify(self.policy_binding); policy = load(self.policy_binding['path'])
        inventory = payload_inventory(self.output)
        require(not inventory['errors'] and not inventory['reparse_not_traversed'],
                'Guarded output inventory failed or escaped')
        free = {d: shutil.disk_usage(d+'/').free for d in ('C:', 'G:')}
        check_runtime(policy, self.cap, inventory['total_logical_bytes'], peak,
            time.monotonic()-self.started, self.maximum_seconds, free, datetime.now(timezone.utc))
        return dict(used_bytes=inventory['total_logical_bytes'], free_bytes=free)

    def refresh(self, peak=0):
        self.fast_check(peak)
        observed = snapshot(self.local, HERE, self.main_plan, 1, peak_bytes=0)
        require(next(a for a in observed['active_allocations'] if a['owner'] == self.owner)['admission']
                == self.admission, 'Discovered own admission differs')
        policy = load(observed['policy']['path']); verify(observed['policy'])
        require(observed['policy'] == self.policy_binding, 'Campaign policy changed during guard observation')
        projection = exact_projection(observed, self.owner, self.output, policy,
            datetime.now(timezone.utc), peak, production=self.production)
        self.fast_check(peak)
        for b in self.code: verify(b)
        self.last_check = dict(observed=observed, projection=projection,
            allocation_lock='reservation-guard.owner.lock', supervisor_writer_lock_held=False,
            producer_family_qualification_required=True, worker_execution_authorized=False,
            N4_accepted=False, N5_complete=False)
        return self.last_check

    def __exit__(self, kind, value, traceback):
        try:
            if self.lock_context is not None: return self.lock_context.__exit__(kind, value, traceback)
        finally: self.held = False


if __name__ == '__main__':
    from metric_process import pin
    pin(); parser = argparse.ArgumentParser(description='Bounded cross-process lock contention probe only')
    parser.add_argument('--test-lock', type=Path, required=True); args = parser.parse_args()
    expected = HERE.parents[4]/'local/n4/reservation-guard.owner.lock'
    require(args.test_lock.resolve() == expected.resolve(), 'Only the stage resource lock may be tested')
    try:
        with lock(expected, wait=0): pass
    except BlockingIOError: sys.exit(0)
    sys.exit(5)
