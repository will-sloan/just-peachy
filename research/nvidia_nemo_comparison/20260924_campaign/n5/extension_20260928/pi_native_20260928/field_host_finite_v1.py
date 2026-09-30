"""Finite decoded JSON preflight derivative. README_FIELD_HOST_BOUNDARY_V1.md."""
import json
import math
from field_host_budget_v1 import HostStore as RetainedHostStore
from field_host_budget_v1 import LIMITS, MIB, digest, encoded, floors, publish_backup


def finite_float(token):
    value = float(token)
    if not math.isfinite(value):
        raise ValueError('Nonfinite decoded JSON number')
    return value


def reject_constant(token):
    raise ValueError('Nonfinite JSON constant: '+token)


class HostStore(RetainedHostStore):
    def preflight(self, name, raw):
        group = super().preflight(name, raw)
        if name.endswith('.json'):
            # Reject while parsing each token, including duplicate-key values
            # which would disappear from a subsequently traversed dictionary.
            json.loads(raw.decode('utf-8'), parse_float=finite_float,
                       parse_constant=reject_constant)
        return group
