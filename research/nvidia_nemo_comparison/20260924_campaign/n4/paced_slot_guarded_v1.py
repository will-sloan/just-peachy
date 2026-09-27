"""Application cell inside an admitted run allocation; README_PACED_SLOT_GUARDED_V1.md."""
from contextlib import ExitStack
from pathlib import Path

import psutil
from common import load, verify
from reservation_budget_v1 import require
from scoring_bank import writer_lock
from paced_slot import ExclusiveApplicationSlot as PreviousSlot, MAX_CELL_BYTES


def validate_parent(proof, admission_binding, admission, owner, parent, cell, reservation):
    """The cell consumes its run's reserved bytes, never another allocation."""
    parent, cell = Path(parent).resolve(), Path(cell).resolve()
    require(cell.is_relative_to(parent/'cells') and cell.parent == parent/'cells',
            'Application cell must be a direct child of its admitted run')
    require(Path(admission_binding['path']) == parent/'ADMISSION.json'
        and admission.get('owner') == owner, 'Exact run allocation owner required')
    require(type(reservation) is int and 0 < reservation <= MAX_CELL_BYTES
        and type(admission.get('allocation_bytes')) is int
        and admission['allocation_bytes'] >= reservation + 1024**2, 'Insufficient parent allocation')
    projection = proof['projection']
    require(projection['own_admission'] == admission_binding
        and projection['own_allocation_bytes'] == admission['allocation_bytes']
        and projection['production_scope_checked'] is True
        and projection['own_allocation_counted_once'] is True
        and projection['other_allocation_count'] == 0, 'Parent resource admission differs')
    census = proof['observed']
    require(census.get('complete_recorded_N4_admission_census') is True
        and census.get('active_set_supplied_by_caller') is False
        and len(census['active_allocations']) == 1
        and census['active_allocations'][0]['admission'] == admission_binding
        and census['supervisor']['state'] == 'RUNNING'
        and census['supervisor']['driver'] == owner,
        'Complete sole supervised allocation required')


class ExclusiveApplicationSlot(PreviousSlot):
    """Retain exact runtime/desktop ownership gates; replace fixed 6-GiB estimate.

    The coordinator holds the complete run's reservation guard for its lifetime.
    Initial/periodic/final full census occurs only between closed children.
    During a child, the inherited runtime census checks the exact CPU4 child,
    CPU14 coordinator/supervisor, every possible competitor and access errors.
    This slot cannot launch, terminate a process or mutate a shared ledger.
    """
    def __init__(self, state, output, *, allocation_guard, allocation_receipt,
                 reservation_bytes=MAX_CELL_BYTES):
        super().__init__(state, output, reservation_bytes=reservation_bytes)
        self.allocation_guard = allocation_guard
        self.allocation_receipt = allocation_receipt

    def _parent(self):
        g = self.allocation_guard
        require(g.held is True and g.production is True and g.owner == self.coordinator,
                'Exact coordinator must hold the production allocation lock')
        verify(g.admission); verify(self.allocation_receipt)
        require(Path(self.allocation_receipt['path']).parent == g.output,
                'Allocation proof escaped admitted run')
        validate_parent(load(self.allocation_receipt['path']), g.admission, load(g.admission['path']),
            self.coordinator, g.output, self.output, self.reservation)

    def _resources(self, force_scan=False):
        super()._resources(force_scan=force_scan)
        # The complete run cap includes this cell. Reserve only its unwritten
        # remainder, plus the guard's terminal headroom, against current bytes.
        self.allocation_guard.fast_check(peak=max(0, self.reservation-self.output_size))

    def acquire(self):
        require(self.locks is None, 'Application slot already acquired')
        require(psutil.Process().cpu_affinity() == [14], 'Coordinator must already be pinned to CPU14')
        self._parent()
        stack = ExitStack()
        try:
            stack.enter_context(writer_lock(self.local/'n4/paced-application.owner.lock'))
            stack.enter_context(writer_lock(self.local/'n4/metric-scoring.owner.lock'))
            record, census = self._ownership()
            self._resources(force_scan=True)
            self.run_id = record['run_id']; self.locks = stack
            return dict(coordinator=self.coordinator, supervised_run=self.run_id, census=census,
                allocation_admission=self.allocation_guard.admission, allocation_receipt=self.allocation_receipt,
                reservation_bytes=self.reservation, reservation_scope='WITHIN_ALREADY_COUNTED_RUN_CAP',
                cpu_affinity=[4], gpu=False, source_execution_authorized=False,
                remaining_gate='Qualified fixed private-desktop launcher and renewable child permit required')
        except BaseException:
            stack.close(); raise

    def check(self):
        require(self.allocation_guard.held is True and self.allocation_guard.owner == self.coordinator,
                'Run allocation lock or coordinator changed during cell')
        return super().check()
