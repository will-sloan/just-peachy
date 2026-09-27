"""Receipt-based reservation arithmetic. See README_RESERVATION_BUDGET_V1.md."""
from datetime import datetime, timedelta, timezone
import math
from pathlib import Path
import shutil

from common import bind, load, verify
from metric_process import exact_process
from scoring_bank_v3 import verify_bindings

GIB = 1024**3
DEADLINE = datetime(2026, 9, 28, 14, 48, 19, tzinfo=timezone.utc)
RETAINED_PENDING = 2*GIB
CONTINGENCY = GIB//2
KINDS = {'ASR': (1920, 'PASS_ASR_FULL_BANK_COMPONENTS_ONLY', 'final_result', 'cells'),
         'D1': (960, 'PASS_D1_FULL_BANK_COMPONENTS_ONLY', 'terminal', 'rows')}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def natural(value):
    return type(value) is int and value >= 0


def owner_key(owner):
    require(set(owner) == {'pid', 'create_time'} and natural(owner['pid'])
            and owner['pid'] > 0 and type(owner['create_time']) in (int, float)
            and math.isfinite(owner['create_time']) and owner['create_time'] > 0,
            'Malformed exact process identity')
    return owner['pid'], owner['create_time']


def validate_closed(kind, review, admission, terminal, admission_binding,
                    terminal_binding, manifest_binding, lookup=exact_process):
    """Validate closed component facts after the caller verifies their bytes."""
    require(kind in KINDS, 'Only the audited ASR and D1 reservations can expire')
    count, status, terminal_key, rows_key = KINDS[kind]
    require(review.get('status') == status and review.get('full_bank_component_coverage') is True
            and type(review.get('component_cells')) is int and review['component_cells'] == count,
            'Complete accepted component review required')
    rows = review[rows_key]
    require(len(rows) == count and len({r['result']['path'] for r in rows}) == count,
            'Missing or duplicate reviewed component result')
    require(review['admission'] == terminal['admission'] == admission_binding
            and review[terminal_key] == terminal_binding,
            'Review, terminal and admission must join exactly')
    require(admission['manifest'] == manifest_binding and type(admission['total']) is int
            and admission['total'] == count and type(admission['allocation_bytes']) is int
            and admission['allocation_bytes'] == 2*GIB, 'Component scope or original allocation differs')
    require(terminal['status'] == 'FULL_BANK_COLLECTED_REQUIRES_REVIEW'
            and type(terminal['completed']) is int and type(terminal['total']) is int
            and terminal['completed'] == terminal['total'] == count
            and terminal['child'] is None and terminal.get('failed', 0) == 0
            and terminal.get('not_tested', 0) == 0, 'Component terminal is incomplete or has a child')
    owner_key(terminal['owner'])
    require(lookup(terminal['owner']) is None, 'Exact component owner is still alive')
    return dict(kind=kind, expired_reservation_bytes=2*GIB, owner=terminal['owner'],
                completed=count, exact_owner_exited=True)


def read_closed_components(plan_binding, lookup=exact_process):
    """Verify every reviewed result; retain all physical evidence in inventory."""
    verify(plan_binding); plan = load(plan_binding['path']); context = plan['context']
    require(plan['scope'] == 'main' and plan['required'] == 7680, 'Original full main plan required')
    proofs = []
    for kind, (_, _, terminal_key, rows_key) in KINDS.items():
        rb = context['reviews'][kind]; verify(rb); review = load(rb['path'])
        ab, tb = review['admission'], review[terminal_key]
        verify(ab); verify(tb); admission, terminal = load(ab['path']), load(tb['path'])
        root = Path(admission['output']).resolve()
        require(Path(ab['path']).resolve() == root/'ADMISSION.json'
                and Path(tb['path']).resolve() == root/'RESULT.json', 'Foreign component location')
        for row in review[rows_key]:
            require(Path(row['result']['path']).resolve().is_relative_to(root), 'Foreign component result')
        verify_bindings(review)
        proof = validate_closed(kind, review, admission, terminal, ab, tb, context['manifest'], lookup)
        proofs.append(dict(proof, review=rb, admission=ab, terminal=tb))
        for binding in (rb, ab, tb): verify(binding)
        require(lookup(terminal['owner']) is None, 'Component owner changed during review')
    verify(plan_binding)
    return proofs


def live_allocation(admission_binding, root, local, *, lookup=exact_process, inventory=None):
    """Observe remaining allocation before the campaign inventory is sampled."""
    if inventory is None:
        from asr_full_bank import payload_inventory
        inventory = payload_inventory
    verify(admission_binding); admission = load(admission_binding['path'])
    root, local = Path(root).resolve(strict=True), Path(local).resolve(strict=True)
    require(root.is_relative_to(local/'n4') and root != local/'n4'
            and Path(admission_binding['path']).resolve() == root/'ADMISSION.json',
            'Allocation must have its own private N4 output root')
    fields = [k for k in ('allocation_bytes', 'maximum_output_bytes') if k in admission]
    require(len(fields) == 1, 'Exactly one explicit output limit is required')
    cap = admission[fields[0]]
    require(natural(cap) and 0 < cap <= 8*GIB, 'Invalid or oversized allocation')
    owner = admission['owner']; owner_key(owner)
    require(lookup(owner) is not None, 'Supply only currently live allocations')
    used = inventory(root)
    require(not used['errors'] and natural(used['total_logical_bytes'])
            and used['total_logical_bytes'] <= cap and not used['reparse_not_traversed'],
            'Allocation census failed, escaped, or exceeded its own bound')
    verify(admission_binding)
    require(lookup(owner) is not None, 'Allocation owner exited during observation; resample')
    return dict(admission=admission_binding, root=str(root), owner=owner,
                allocation_bytes=cap, observed_used_bytes=used['total_logical_bytes'],
                remaining_bytes=cap-used['total_logical_bytes'])


def calculate(inventory, closed, active, requested_bytes, policy, free_bytes, now,
              *, peak_bytes=0, lookup=exact_process):
    """Pure checked arithmetic. This calculation never authorizes a worker."""
    require(now.tzinfo is not None, 'Timezone-aware observation required')
    configured_deadline = datetime.fromisoformat(policy['target_utc'])
    require(configured_deadline.tzinfo is not None, 'Timezone-aware configured deadline required')
    cutoff = min(DEADLINE, configured_deadline)-timedelta(hours=12)
    require(now < cutoff, 'Packaging reserve reached; do not extend it')
    resources = policy['resource_policy']; allowance = resources['new_payload_allowance_gib']
    require(type(allowance) in (int, float) and math.isfinite(allowance) and 0 < allowance <= 50,
            'Campaign allowance changed beyond the admitted 50 GiB')
    require(natural(requested_bytes) and 0 < requested_bytes <= 8*GIB
            and natural(peak_bytes) and peak_bytes <= requested_bytes, 'Invalid requested output or peak')
    require(not inventory['errors'] and natural(inventory['total_logical_bytes']), 'Inventory failed')
    require(len(closed) == 2 and {p['kind'] for p in closed} == set(KINDS),
            'Both independently verified closed component reservations are required')
    for proof in closed:
        require(type(proof['expired_reservation_bytes']) is int
                and proof['expired_reservation_bytes'] == 2*GIB and proof['exact_owner_exited'] is True
                and proof['completed'] == KINDS[proof['kind']][0], 'Closed reservation proof differs')
        owner_key(proof['owner'])
        require(lookup(proof['owner']) is None, 'Closed component became active')
    roots = []; owners = set(); remaining = 0; observed = 0
    for item in active:
        root = Path(item['root']).resolve(); key = owner_key(item['owner'])
        require(key not in owners and all(not root.is_relative_to(p) and not p.is_relative_to(root)
                                        for p in roots), 'Duplicate owner or overlapping output allocation')
        owners.add(key); roots.append(root)
        require(lookup(item['owner']) is not None, 'Active allocation changed; resample')
        cap, used = item['allocation_bytes'], item['observed_used_bytes']
        require(natural(cap) and 0 < cap <= 8*GIB and natural(used) and used <= cap
                and type(item['remaining_bytes']) is int and item['remaining_bytes'] == cap-used,
                'Remaining allocation cannot be invented or negative')
        remaining += cap-used; observed += used
    # Callers must read active usage BEFORE the whole inventory. New output
    # growth is then counted conservatively in both inventory and remainder.
    require(inventory['total_logical_bytes'] >= observed, 'Inventory predates admitted active usage')
    for drive, floor in (('C:', 50), ('G:', 75)):
        configured = resources['minimum_free_gib'][drive]
        require(type(configured) in (int, float) and math.isfinite(configured) and configured >= 0,
                'Invalid configured drive floor')
        require(natural(free_bytes[drive]) and free_bytes[drive] >= max(floor, configured)*GIB+peak_bytes,
                'Drive floor or peak headroom unavailable')
    projected = inventory['total_logical_bytes']+remaining+requested_bytes+RETAINED_PENDING+CONTINGENCY
    require(projected <= allowance*GIB, 'Shared allowance exceeded after all physical bytes and reservations')
    return dict(schema='n4-reservation-calculation-v1', existing_bytes=inventory['total_logical_bytes'],
                active_remaining_bytes=remaining, requested_bytes=requested_bytes,
                retained_pending_bytes=RETAINED_PENDING, contingency_bytes=CONTINGENCY,
                expired_closed_reservations_bytes=4*GIB, projected_bytes=projected,
                allowance_bytes=int(allowance*GIB), packaging_cutoff_utc=cutoff.isoformat(),
                physical_bytes_removed_or_credited=0, worker_execution_authorized=False)


def snapshot(local, plan_binding, admission_bindings, requested_bytes, *, peak_bytes=0):
    """Read-only diagnostic; explicit active set is not a complete process census."""
    from asr_full_bank import payload_inventory
    local = Path(local).resolve(strict=True)
    closed = read_closed_components(plan_binding)
    active = [live_allocation(b, Path(b['path']).parent, local) for b in admission_bindings]
    inventory = payload_inventory(local)
    policy_binding = bind(local/'supervision/campaign.json'); policy = load(policy_binding['path'])
    free = {d: shutil.disk_usage(d+'/').free for d in ('C:', 'G:')}
    calculation = calculate(inventory, closed, active, requested_bytes, policy, free,
                            datetime.now(timezone.utc), peak_bytes=peak_bytes)
    for item in active:
        verify(item['admission'])
        require(exact_process(item['owner']) is not None, 'Active owner changed during inventory')
    for proof in closed:
        for key in ('review', 'admission', 'terminal'): verify(proof[key])
        require(exact_process(proof['owner']) is None, 'Closed owner changed during inventory')
    verify(plan_binding); verify(policy_binding)
    return dict(plan=plan_binding, closed_components=closed, active_allocations=active,
                inventory=inventory, policy=policy_binding, free_bytes=free, calculation=calculation,
                active_allocation_set_is_caller_supplied=True, production_guard_integration_complete=False,
                resource_measurement_accepted=False, N4_accepted=False)
