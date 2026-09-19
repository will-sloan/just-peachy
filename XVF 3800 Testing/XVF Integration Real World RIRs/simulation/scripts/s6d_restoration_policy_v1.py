"""Pure guarded restoration semantics; README_S6D_CAPTURE_V5.md. No I/O."""
from __future__ import annotations
import math

POLICY = 'exact_static_plus_verified_dynamic_agc.v1'
NO_MUTATION_POLICY = 'no_setters_or_playback.v1'
SCHEMA = 'edge-s6d-restoration.v5'
RECOVERY_SCHEMA = 'edge-s6d-restoration-recovery.v1'
GAIN = 'PP_AGCGAIN'


def exact(a, b):
    """Decimal getter equality; booleans cannot masquerade as numeric getters."""
    if isinstance(a, dict) or isinstance(b, dict):
        return isinstance(a, dict) and isinstance(b, dict) and a.keys() == b.keys() and all(exact(a[k], b[k]) for k in a)
    if isinstance(a, list) or isinstance(b, list):
        return isinstance(a, list) and isinstance(b, list) and len(a) == len(b) and all(exact(x, y) for x, y in zip(a, b))
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    return a == b


def gain_value(value):
    if not isinstance(value, list) or len(value) != 1:
        return None
    x = value[0]
    return x if type(x) in (int, float) and math.isfinite(x) and 1 <= x <= 1000 else None


def restoration_decision(initial, after, reapply):
    """Evaluate exact static restoration plus one documented autonomous getter.

    `reapply` must be the bound immediate restore_exposed receipt, not a later
    snapshot. A getter-only recovery may reuse its explicitly bound original
    receipt; this function itself neither issues nor claims a new setter.
    """
    errors = []
    initial = initial if isinstance(initial, dict) else {}
    after = after if isinstance(after, dict) else {}
    reapply = reapply if isinstance(reapply, dict) else {}
    old = initial.get('settings'); new = after.get('settings')
    observed = reapply.get('observed')
    maps = all(isinstance(x, dict) for x in (old, new, observed))
    if not maps:
        errors.append('Full initial/final/immediate settings maps required')
    old = old if isinstance(old, dict) else {}
    new = new if isinstance(new, dict) else {}
    observed = observed if isinstance(observed, dict) else {}
    identity_ok = isinstance(initial.get('identity'), dict) and exact(initial['identity'], after.get('identity'))
    ancillary_ok = isinstance(initial.get('observe_only'), dict) and exact(initial['observe_only'], after.get('observe_only'))
    initial_identity = initial.get('identity') if isinstance(initial.get('identity'), dict) else {}
    final_identity = after.get('identity') if isinstance(after.get('identity'), dict) else {}
    width_ok = initial.get('usb_bits') is not None and exact(initial['usb_bits'], final_identity.get('USB_BIT_DEPTH'))
    static_ok = maps and old.keys() == new.keys() and GAIN in old and exact({k:v for k,v in old.items() if k != GAIN}, {k:v for k,v in new.items() if k != GAIN}) and identity_ok and ancillary_ok and width_ok
    immediate_ok = maps and reapply.get('exact_match') is True and exact(observed, old)
    original_gain, immediate_gain, final_gain = (gain_value(x.get(GAIN)) for x in (old, observed, new))
    values_valid = all(x is not None for x in (original_gain, immediate_gain, final_gain))
    requested_verified = immediate_ok and values_valid and immediate_gain == original_gain
    full_match = static_ok and exact(old, new)
    enabled = exact(old.get('PP_AGCONOFF'), [1]) and exact(new.get('PP_AGCONOFF'), [1]) and exact(observed.get('PP_AGCONOFF'), [1])
    firmware_supported = exact(initial_identity.get('VERSION'), [3, 2, 1]) and exact(final_identity.get('VERSION'), [3, 2, 1])
    drift = values_valid and final_gain != original_gain
    dynamic_allowed = drift and enabled and firmware_supported and static_ok and requested_verified
    if not static_ok:errors.append('Static settings, identity, ancillary or USB-width mismatch')
    if not requested_verified:errors.append('Immediate exact requested-gain restoration proof missing or invalid')
    if not values_valid:errors.append('AGC gain must be one finite numeric value in documented[1,1000], never bool/string')
    if drift and not enabled:errors.append('Autonomous gain exception requires initial/immediate/final AGC enabled')
    if drift and not firmware_supported:errors.append('Autonomous gain exception is qualified only for recorded firmware3.2.1')
    accepted = static_ok and requested_verified and values_valid and (full_match or dynamic_allowed)
    return dict(policy=POLICY, accepted=accepted, exact_static_configuration_match=static_ok,
        requested_gain_set_verified=requested_verified, exact_full_snapshot_match=full_match,
        autonomous_gain_drift_observed=bool(drift), autonomous_gain=dict(initial=old.get(GAIN), immediate_reapply=observed.get(GAIN), final_readback=new.get(GAIN),
            delta=final_gain-original_gain if values_valid else None, documented_range=[1,1000],
            initial_immediate_final_AGC_enabled=enabled, documented_firmware_3_2_1=firmware_supported,
            exception_used=bool(dynamic_allowed), tolerance_applied=False,
            scope='Current adaptive gain may evolve after exact immediate restoration; hidden adaptive history is not restored.'), errors=errors)


def record_policy_valid(initial, receipt):
    """Recompute a V5 receipt; callers must verify all file/owner bindings first."""
    if receipt.get('schema_version') != SCHEMA or receipt.get('policy') != POLICY or receipt.get('status') != 'PASS':
        return False
    decision = restoration_decision(initial, receipt.get('readback'), receipt.get('reapply'))
    return decision['accepted'] and all(exact(receipt.get(k), v) for k, v in decision.items()) and receipt.get('exact_recorded_configuration_match') is decision['exact_full_snapshot_match']
