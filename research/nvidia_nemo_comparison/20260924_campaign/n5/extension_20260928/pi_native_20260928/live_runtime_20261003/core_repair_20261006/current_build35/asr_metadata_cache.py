"""Private SQL metadata cache; see README_ASR_METADATA_CACHE.md."""
from collections import OrderedDict
import sys


CACHE_BYTES = 8 * 1024**2
CACHE_ENTRIES = 4096
FIXED_OVERHEAD = 4096
MISS = object()


class MetadataCache:
    """Immutable SQL strings only; the owning SegmentLedger supplies its RLock.

    Limits affect eviction/admission only. A miss always uses the original SQL.
    The cache never retains raw recognition text, audio, or decoded caller rows.
    """
    def __init__(self):
        self._rows = OrderedDict()
        self._entry_bytes = 0
        self.stamp = None
        self.fenced = False

    @property
    def resident_bytes(self):
        # Charge the real container allocation, keys/strings/tuples/cost integers,
        # and conservative fixed room for this instance, its scalar fields and
        # at most four seven-integer filesystem observation tuples.
        return sys.getsizeof(self._rows) + self._entry_bytes + FIXED_OVERHEAD

    def clear(self):
        self._rows.clear()
        self._entry_bytes = 0

    def fault(self):
        # No uncertain mutation may leave old cached metadata observable. Keep
        # the contents fenced until a subsequent successful owned commit clears
        # them; SQL remains authoritative in the meantime.
        self.fenced = True

    def observe(self, stamp):
        if self.stamp is not None and stamp != self.stamp:
            self.clear()  # Unexpected filesystem drift, not our tracked commit.
        self.stamp = stamp

    def _remove(self, parent):
        prior = self._rows.pop(parent, None)
        if prior is not None:
            self._entry_bytes -= prior[3]

    def committed(self, stamp, *, parent=None, group=None):
        if self.fenced:
            self.clear()
            self.fenced = False
        elif ((parent is not None and type(parent) is not str)
                or (group is not None and type(group) is not str)):
            # Preserve SQLite's original binding/affinity behavior for callers
            # outside the strict native ID shape; never guess its text coercion.
            self.clear()
        else:
            if parent is not None:
                self._remove(parent)
            if group is not None:
                # At most CACHE_ENTRIES keys, independent of recording length.
                affected = [key for key, row in self._rows.items() if row[1] == group]
                for key in affected:
                    self._remove(key)
        # Our unrelated successful writes change file times but must not evict
        # unchanged parents. Only unexpected changes observed between operations
        # clear the cache, under the existing single owned ledger contract.
        self.stamp = stamp

    def get(self, parent):
        if self.fenced or type(parent) is not str:
            return MISS
        row = self._rows.get(parent)
        if row is None:
            return MISS
        self._rows.move_to_end(parent)
        return row

    def put(self, parent, raw, group, ready):
        if (self.fenced or type(parent) is not str or type(raw) is not str
                or type(group) is not str or type(ready) is not bool
                or len(parent) > 4096 or len(group) > 4096):
            return False
        try:
            item = (raw, group, ready, 0)
            cost = sum(sys.getsizeof(value) for value in (parent, raw, group, item, 0))
            # Leave 512 KiB for possible OrderedDict table growth before insertion.
            # The actual post-insertion allocation is checked as well.
            if cost + 512 * 1024 + FIXED_OVERHEAD > CACHE_BYTES:
                return False
            self._remove(parent)
            while self._rows and (len(self._rows) >= CACHE_ENTRIES
                    or self.resident_bytes + cost + 512 * 1024 > CACHE_BYTES):
                key = next(iter(self._rows))
                self._remove(key)
            self._rows[parent] = (raw, group, ready, cost)
            self._entry_bytes += cost
            if self.resident_bytes > CACHE_BYTES:
                self._remove(parent)
                return False
        except MemoryError:
            # An optional cache allocation cannot make a valid SQL read fail.
            self.clear()
            self.fault()
            return False
        return True
