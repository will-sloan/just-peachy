"""Measured combined-worker gate. See README_OPTIONAL_REFINER.md."""
import hashlib
import json
import math
import re

MIB = 1024**2
RATE = 16000
SCHEMA = "just-peachy.pyannote-delayed-d1-admission.v2"


def validate_admission(raw, sha256, selection, policy, expected_pins, available_ram_bytes, *, physical_ram_bytes, phase="pre_primary"):
    """No receipt generator or synthetic/native bypass is provided.

    The trusted caller supplies independently reviewed receipt and inventory
    pins, not hashes computed from a request. Missing combined evidence is a
    launch rejection. Component-only measurements cannot satisfy this schema.
    """
    def pin(value):
        if type(value) is not str or re.fullmatch("[0-9a-f]{64}", value) is None:
            raise ValueError("Explicit reviewed SHA256 required")
        return value
    if type(raw) is not bytes or not 0 < len(raw) <= 65536 or hashlib.sha256(raw).hexdigest() != pin(sha256):
        raise ValueError("Exact bounded measured admission required")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate admission key")
            result[key] = value
        return result
    receipt = json.loads(raw, object_pairs_hook=pairs,
                         parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite receipt")))
    selected, reserved = selection.validate(), policy.validate()
    if (selected.get("optional_d1_refiner") is not True or selected["diarizer"] != "pyannote"
            or selected["allow_experimental"] is not True or selected["provisional_correction"]
            or selected["speaker_attribution"] != "retained" or selected['refinement_profile']!='current_delayed'):
        raise ValueError("Explicit separate experimental Pyannote/D1 selection required")
    keys = {"candidate_content_sha256", "installed_manifest_sha256", "operational_binding_sha256",
            "selected_asset_inventory_sha256"}
    if set(expected_pins) != keys:
        raise ValueError("Exact complete candidate/installed/binding/asset inventory pins required")
    for value in expected_pins.values():
        pin(value)
    expected = dict(schema=SCHEMA, status="MEASURED_COMBINED_CM5_2GB_EXPERIMENTAL", synthetic=False,
                    experimental_only=True,sustained_realtime_qualified=False,timing_reviewed=True,fallback_reviewed=True,
                    selection=selected, policy=reserved, pins=expected_pins,
                    refinement_profile="current_delayed", refinement_embedding="anonymous",
                    cpus=[2,3], cpu_quota_percent=200, maximum_tasks=64,
                    measurement_scope="whole_owned_unit", quality_qualified=False)
    if any(type(receipt.get(key)) is not type(value) or receipt.get(key) != value for key,value in expected.items()):
        raise ValueError("Measured receipt does not cover this exact combined selection/policy/assets")
    for name in ("measurement_receipt_sha256", "closure_receipt_sha256", "measurement_source_sha256", "qualified_binding_sha256", "qualified_package_manifest_sha256"):
        pin(receipt.get(name))
    closure = receipt.get("closure", {})
    if any(closure.get(key) is not True for key in ("primary_models_closed", "all_owners_dead", "cgroup_empty", "leases_released", "full_mirror_verified")):
        raise ValueError("Exact measured worker/unit closure required")
    if type(closure.get("refiner_model_closed")) is not bool:
        raise ValueError("Explicit refiner model-close versus exact killed-owner closure required")
    owners = closure.get("owners")
    if type(owners) is not list or not 2 <= len(owners) <= 64:
        raise ValueError("Measured primary and child owner identities required")
    for owner in owners:
        if (set(owner) != {"pid", "start_ticks", "boot_id"} or
                any(type(owner[k]) is not int or owner[k] <= 0 for k in ("pid", "start_ticks")) or
                type(owner["boot_id"]) is not str or not re.fullmatch("[0-9a-f-]{36}", owner["boot_id"])):
            raise ValueError("Exact measured owner identity required")
    if len({(o['pid'],o['start_ticks'],o['boot_id']) for o in owners})!=len(owners):
        raise ValueError('Distinct measured primary/child owners required')
    if len({o['boot_id'] for o in owners})!=1:
        raise ValueError('Combined measured owners must share one boot')
    measured, limits = receipt.get("measured", {}), receipt.get("limits", {})
    if (type(physical_ram_bytes) is not int or not 1536*MIB <= physical_ram_bytes <= 2048*MIB or
            measured.get('total_ram_bytes') != physical_ram_bytes):
        raise ValueError('Exact measured/current 2 GB MemTotal pin required')
    for name in ("audio_seconds", "peak_combined_rss_bytes", "peak_combined_pss_bytes", "peak_child_virtual_bytes", "peak_child_rss_bytes",
                 "minimum_available_ram_bytes", "primary_source_phase_seconds", "primary_matched_baseline_seconds",
                 "whole_unit_cpu_seconds", "whole_unit_elapsed_seconds"):
        value = measured.get(name)
        if type(value) not in (int,float) or not math.isfinite(value) or value <= 0:
            raise ValueError("Finite positive actual whole-unit measurement required: "+name)
    for name in ("maximum_primary_backlog_seconds","maximum_label_lag_seconds"):
        if type(measured.get(name)) not in (int,float) or not math.isfinite(measured[name]) or measured[name]<0:
            raise ValueError("Finite nonnegative actual backlog required")
    for name in ("child_as_bytes", "child_physical_reserve_bytes", "whole_unit_rss_soft_stop_bytes", "available_ram_floor_bytes", "maximum_lag_seconds"):
        value = limits.get(name)
        if type(value) is not int or value <= 0:
            raise ValueError("Explicit finite resource reserve required")
    if (not measured['peak_combined_pss_bytes']<=measured['peak_combined_rss_bytes']<=physical_ram_bytes or
            measured['minimum_available_ram_bytes']>physical_ram_bytes or available_ram_bytes>physical_ram_bytes):
        raise ValueError('Measured aggregate memory exceeds actual physical RAM')
    if (not 256*MIB <= limits["child_as_bytes"] <= 768*MIB or
            limits["child_physical_reserve_bytes"] < measured["peak_child_rss_bytes"]+64*MIB or
            not 768*MIB <= limits["whole_unit_rss_soft_stop_bytes"] <= 1024*MIB or
            measured["peak_combined_rss_bytes"] >= limits["whole_unit_rss_soft_stop_bytes"] or
            limits["available_ram_floor_bytes"] < 192*MIB or
            measured["minimum_available_ram_bytes"] < limits["available_ram_floor_bytes"] or
            measured["peak_child_virtual_bytes"] >= limits["child_as_bytes"] or
            limits["maximum_lag_seconds"] > selected["revision_window_seconds"] or
            measured["audio_seconds"] > reserved["maximum_session_seconds"] or
            measured["maximum_primary_backlog_seconds"] >= reserved["max_backlog_seconds"] or
            (reserved["developer_soak"] and measured["audio_seconds"] < reserved["maximum_session_seconds"]) or
            type(measured.get("dropped_samples")) is not int or measured["dropped_samples"] != 0 or
            measured.get("complete_eof") is not True or measured.get("continuous_source_clock") is not True):
        raise ValueError("Measured combined work does not fit the selected bounded policy")
    count=measured.get('source_samples');child=measured.get('refiner_source_samples');frames=measured.get('refiner_output_frames')
    if (type(count) is not int or count<=0 or count/RATE!=measured['audio_seconds'] or
            measured.get('primary_source_samples')!=count or type(child) is not int or not 0<=child<=count or
            type(frames) is not int or not 0<=frames<=child//160+1 or
            measured.get('refiner_uncovered_samples')!=count-min(child,frames*160) or
            type(measured.get('refiner_disabled')) is not bool or type(measured.get('refiner_complete_eof')) is not bool or
            measured.get('refiner_restart_count')!=0 or measured.get('refiner_pause_count')!=0 or
            measured.get('cpu_measurement_scope')!='whole_owned_cgroup' or
            measured.get('timing_definition')!='paced source-origin to EOF; includes waits; CPU seconds separate'):
        raise ValueError('Exact shared source/prefix/frame and explicitly scoped timing evidence required')
    if measured['refiner_complete_eof']:
        if child!=count or frames!=count//160+1 or not closure['refiner_model_closed']:
            raise ValueError('Complete refiner EOF requires every source sample/frame and model close')
    else:
        reason=measured.get('refiner_fallback_reason')
        if not measured['refiner_disabled'] or type(reason) is not str or not 0<len(reason)<=512:
            raise ValueError('Incomplete optional work requires reviewed visible bounded fallback')
    if 'maximum_combined_rolling_rtf' in measured:
        raise ValueError('Undefined combined rolling RTF is not an admission scalar')
    if phase not in ('pre_primary','pre_child','historical_evidence'):raise ValueError('Explicit physical admission phase required')
    physical_reserve=(measured['peak_combined_rss_bytes']+64*MIB if phase=='pre_primary' else limits['child_physical_reserve_bytes'])
    if phase!='historical_evidence' and (type(available_ram_bytes) is not int or available_ram_bytes < limits['available_ram_floor_bytes']+physical_reserve):
        raise ValueError('Current available RAM cannot cover measured physical reserve plus stop floor')
    return receipt


AUTHORIZATION_KEYS={'native_launch_enabled','authorization_kind','production_acceptance_sha256','admission_sha256'}


def operational_binding_sha256(binding):
    """Hash unchanged runtime/model/source/gallery settings, excluding only authorization."""
    raw=json.dumps({key:value for key,value in binding.items() if key not in AUTHORIZATION_KEYS},
                   sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def validate_requested_admission(raw,sha,selection,policy,pins,available_ram_bytes,*,physical_ram_bytes,phase='pre_primary'):
    # Qualification permits are accepted only in an independently initialized,
    # exact-owned qualification worker. The normal GUI has no path to initialize it.
    value=json.loads(raw)
    if value.get('schema')=='just-peachy.optional-first-combined-qualification.v2':
        from optional_refiner_qualification import validate_claimed
        return validate_claimed(raw,sha,selection,policy,pins,phase)
    return validate_admission(raw,sha,selection,policy,pins,available_ram_bytes,
                              physical_ram_bytes=physical_ram_bytes,phase=phase)
