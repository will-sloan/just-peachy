"""Focused host cases without models; README_DISK_CAPACITY_POLICY.md."""
import ast
import ctypes
from dataclasses import dataclass, make_dataclass, replace
import importlib.util
import math
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
BASE = Path(os.environ["JP_CAPACITY_TEST_BASE"])
INSTALLED = Path(os.environ["JP_CAPACITY_TEST_INSTALLED"])
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
sys.path.append(str(BASE))
import numpy as np
import profiles
import telemetry
import nemotron_binding as binding
import capacity_drain_profile as drain


def function(path, name, namespace):
    tree = ast.parse(path.read_bytes())
    nodes = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(nodes) != 1:
        raise ValueError("One exact fixture function required: "+name)
    node = nodes[0]
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), str(path), "exec"), namespace)
    return namespace[name]


class API:
    def __init__(self, count, base, values=None):
        self.count, self.base = count, base
        self.values = np.full((count-base, 8), .25, dtype=np.float32) if values is None else values
        self.calls = 0
    def nemo_speech_diar_frame_count(self, stream):
        return self.count
    def nemo_speech_diar_frame_probs_start(self, stream):
        return self.base
    def nemo_speech_diar_frame_probs(self, stream, pointer, size):
        if size != self.values.size:
            raise AssertionError("The real full-retained ABI size was not preserved")
        np.ctypeslib.as_array(pointer, shape=(size,))[:] = self.values.reshape(-1)
        self.calls += 1
        return 0


class WorkspaceCases(unittest.TestCase):
    def copy(self, api, workspace=None, first=0, maximum=10**9, guard=None):
        return binding.copy_new_probabilities(np, api, None,
            np.empty((0, 8), np.float32) if workspace is None else workspace,
            first=first, maximum_frames=maximum, check=lambda status:self.assertEqual(status, 0),
            memory_guard=guard or (lambda amount:None))

    def test_lazy_full_abi_equals_previous_full_reservation(self):
        old = function(BASE/"nemotron_binding.py", "copy_new_probabilities", dict(ctypes=ctypes))
        api = API(12, 4, np.arange(64, dtype=np.float32).reshape(8, 8)/64)
        expected = old(np, api, None, np.empty((100,8),np.float32),
                       first=6, maximum_frames=100, check=lambda value:None)
        count, base, values, workspace = self.copy(api, first=6, maximum=100)
        self.assertEqual((count,base), expected[:2])
        np.testing.assert_array_equal(values, expected[2])
        self.assertEqual(workspace.shape, (8,8))
        self.assertEqual(api.calls, 2)

    def test_large_absolute_clock_does_not_reserve_duration(self):
        api = API(900_000_012, 900_000_004)
        reservations = []
        count, base, values, workspace = self.copy(api, first=900_000_006, guard=reservations.append)
        self.assertEqual(values.shape, (6,8))
        self.assertEqual(workspace.nbytes, 256)
        self.assertEqual(reservations, [256+6*32+6*16])

    def test_reuse_and_immutable_output(self):
        api = API(10,2)
        _,_,output,workspace = self.copy(api, first=4)
        api.values[:] = .75
        _,_,later,same = self.copy(api, workspace, first=4)
        self.assertIs(same,workspace)
        self.assertFalse(output.flags.writeable)
        self.assertTrue(np.all(output == .25))
        self.assertTrue(np.all(later == .75))

    def test_no_new_rows_does_not_call_abi_or_grow(self):
        api = API(900_000_010,900_000_010)
        workspace = np.empty((0,8),np.float32)
        _,_,values,same = self.copy(api, workspace, first=api.count)
        self.assertEqual(values.shape,(0,8))
        self.assertIs(same,workspace)
        self.assertEqual(api.calls,0)

    def test_timeline_and_workspace_rejections(self):
        for count,base,first,maximum in ((9,4,3,10),(9,0,10,10),(11,0,0,10)):
            with self.subTest(count=count,base=base),self.assertRaises(RuntimeError):
                self.copy(API(count,base),first=first,maximum=maximum)
        for bad in (np.empty((10,7),np.float32),np.empty((10,8),np.float64),
                    np.empty((10,16),np.float32)[:,::2]):
            with self.assertRaises(ValueError):
                self.copy(API(9,0),bad,maximum=100)

    def test_invalid_probabilities_and_guard_failure_precede_publication(self):
        for value in (float("nan"),float("inf"),-.01,1.01):
            with self.assertRaises(RuntimeError):
                self.copy(API(8,0,np.full((8,8),value,np.float32)))
        api=API(8,0)
        old=np.empty((2,8),np.float32)
        with self.assertRaises(MemoryError):
            self.copy(api,old,guard=lambda amount:(_ for _ in ()).throw(MemoryError("fixture")))
        self.assertEqual(api.calls,0)
        self.assertEqual(old.shape,(2,8))

    def test_allocation_accounts_old_new_output_masks(self):
        facts=binding.workspace_allocation_bytes(64,10,3,True)
        self.assertEqual(facts["pending_array_bytes"],64+320+96+48)
        self.assertEqual(facts["additional_bytes"],320+96+48)
        self.assertEqual(binding.workspace_allocation_bytes(320,8,2,False)["additional_bytes"],64+32)
        for bad in (True,-1,1.5):
            with self.assertRaises(ValueError):
                binding.workspace_allocation_bytes(bad,8,2,True)

    def test_physical_floor_and_effective_as_use_fresh_current_vm(self):
        snapshot=SimpleNamespace(resource_snapshot=lambda:dict(available_ram=192*1024**2+1000,virtual_bytes=1))
        fake_resource=SimpleNamespace(RLIMIT_AS=9,RLIM_INFINITY=-1,getrlimit=lambda kind:(100_000,200_000))
        fake_path=lambda value:SimpleNamespace(read_text=lambda:"VmSize: 90 kB\n")
        with patch.dict(sys.modules,{"runtime_support":snapshot,"resource":fake_resource}), \
                patch.object(binding,"os",SimpleNamespace(name="posix")),patch.object(binding,"Path",fake_path):
            facts=binding.workspace_memory_guard(1000)
            self.assertEqual(facts["virtual_bytes"],90*1024)
            snapshot.resource_snapshot=lambda:dict(available_ram=192*1024**2+999,virtual_bytes=1)
            with self.assertRaises(MemoryError):binding.workspace_memory_guard(1000)
            snapshot.resource_snapshot=lambda:dict(available_ram=192*1024**2+20_000,virtual_bytes=1)
            with self.assertRaises(MemoryError):binding.workspace_memory_guard(10_000)

    def test_bound_factory_has_no_duration_allocation_and_keeps_endpoint_checks(self):
        source=(HERE/"nemotron_binding.py").read_text()
        tree=ast.parse(source)
        constructor=[node for node in ast.walk(tree) if isinstance(node,ast.FunctionDef) and node.name=="__init__"][0]
        arrays=[node for node in ast.walk(constructor) if isinstance(node,ast.Call)
                and isinstance(node.func,ast.Attribute) and node.func.attr=="empty"]
        self.assertEqual(len(arrays),1)
        self.assertEqual(ast.literal_eval(arrays[0].args[0]),(0,8))
        self.assertIn('count > expected_frames',source)
        self.assertIn('final and count != expected_frames',source)
        self.assertIn('math.isclose(self.seconds_per_frame, .01',source)
        self.assertIn('self._samples_received + len(samples) > maximum_samples',source)


class PolicyCases(unittest.TestCase):
    def test_defaults_remain_finite(self):
        value=profiles.SessionPolicy().validate()
        self.assertEqual((value["maximum_session_seconds"],value["max_backlog_seconds"],value["max_drain_seconds"]),(300,120,120))
        with self.assertRaises(ValueError):profiles.SessionPolicy(maximum_session_seconds=301).validate()
        with self.assertRaises(ValueError):profiles.SessionPolicy(max_drain_seconds=121).validate()

    def test_manual_capacity_policy_matches_finite_drain_deadline(self):
        policy=profiles.SessionPolicy(maximum_session_seconds=200_000,manual_stop=True,
            max_drain_seconds=200_000,max_backlog_seconds=None)
        self.assertIsNone(policy.validate()["max_backlog_seconds"])
        self.assertEqual(policy.total_deadline_seconds,400_180)
        self.assertEqual(policy.maximum_samples(),3_200_000_000)
        with self.assertRaises(ValueError):
            profiles.SessionPolicy(maximum_session_seconds=200_000,manual_stop=True,max_drain_seconds=200_001).validate()

    def test_optional_backlog_rejects_bool_nonfinite_fraction_and_zero(self):
        for value in (True,False,float("nan"),float("inf"),1.5,0,-1):
            with self.subTest(value=value),self.assertRaises(ValueError):
                profiles.SessionPolicy(max_backlog_seconds=value).validate()
        self.assertIsNone(profiles.SessionPolicy(developer_soak=True,maximum_session_seconds=3600,
            max_backlog_seconds=None).validate()["max_backlog_seconds"])

    def test_telemetry_no_capture_stop_keeps_refinement_latency_guard(self):
        value=telemetry.RollingTelemetry(backlog_limit_seconds=None)
        value.observe(now=1,audio_seconds=1,compute_seconds=2,backlog_seconds=900)
        facts=value.snapshot(1)
        self.assertEqual(facts["backlog_seconds"],900)
        self.assertFalse(facts["stop_required"])
        self.assertFalse(facts["refinement_admissible"])
        self.assertFalse(facts["realtime_qualified"])
        old=telemetry.RollingTelemetry()
        old.observe(now=1,audio_seconds=1,compute_seconds=1,backlog_seconds=120)
        self.assertEqual(old.snapshot(1)["stop_reason"],"FAILED_BACKLOG_LIMIT")
        for value in (True,float("inf"),float("nan"),0):
            with self.assertRaises(ValueError):telemetry.RollingTelemetry(backlog_limit_seconds=value)

    def test_actual_controller_policy_passes_capacity_and_optional_keeps_parent(self):
        fake_disk=SimpleNamespace(free=100_000,total=200_000)
        manager=SimpleNamespace(data_root="fixture",binding={},store=SimpleNamespace(policy=SimpleNamespace(reserve=lambda total:100)))
        capacity_calls=[]
        method=function(HERE/"application_controller.py","_policy",
            dict(capacity_seconds=lambda free,reserve,**kwargs:capacity_calls.append((free,reserve,kwargs)) or 200_000))
        normal=SimpleNamespace(selection=SimpleNamespace(optional_d1_refiner=False,input_source="live"),manager=manager)
        with patch("shutil.disk_usage",return_value=fake_disk):
            policy=method(normal)
        self.assertEqual((policy.max_backlog_seconds,policy.max_drain_seconds,policy.maximum_session_seconds),(None,200_000,200_000))
        self.assertEqual(capacity_calls,[(100_000,100,dict(raw_bytes_per_second=0))])
        tree=ast.parse((HERE/"application_controller.py").read_bytes())
        node=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=="_policy"][0]
        self.assertTrue(isinstance(node.body[1],ast.If))
        self.assertIn("super()._policy()",ast.unparse(node.body[1]))

    def test_production_none_only_reviewed_normal_manual_capacity(self):
        chosen=dict(selection="fixture")
        selection=SimpleNamespace(validate=lambda:chosen,optional_d1_refiner=False)
        receipt=dict(allowed_selections=[chosen],limits=dict(maximum_session_seconds=300,
            maximum_developer_seconds=3600,max_drain_seconds=600,max_backlog_seconds=600,manual_stop_storage_policy=True))
        method=function(HERE/"release_authorization.py","authorize_session",
            dict(authorization=lambda binding:("production",receipt),selection_key=lambda value:value,
                 _verify_assets=lambda *args:0))
        policy=profiles.SessionPolicy(maximum_session_seconds=200_000,manual_stop=True,
            max_drain_seconds=200_000,max_backlog_seconds=None)
        self.assertIsNone(method(dict(candidate_content_sha256="fixture"),selection,policy)["policy"]["max_backlog_seconds"])
        selection.optional_d1_refiner=True
        with self.assertRaises(PermissionError):method(dict(candidate_content_sha256="fixture"),selection,policy)
        selection.optional_d1_refiner=False
        with self.assertRaises(PermissionError):
            method(dict(candidate_content_sha256="fixture"),selection,profiles.SessionPolicy(max_backlog_seconds=None))

    def test_summary_and_installed_gate_preserve_numeric_and_none(self):
        summary=function(HERE/"launcher.py","gui_policy_summary",{})
        self.assertIn("backlog 120 s",summary(profiles.SessionPolicy()))
        self.assertIn("storage guarded, no lag cutoff",summary(profiles.SessionPolicy(max_backlog_seconds=None)))
        tree=ast.parse((HERE/"installed_engine.py").read_bytes())
        gates=[n for n in ast.walk(tree) if isinstance(n,ast.If)
               and "backlog >= self.policy.max_backlog_seconds" in ast.unparse(n.test)]
        self.assertEqual(len(gates),1)
        condition=compile(ast.Expression(gates[0].test),"fixture-gate","eval")
        for limit,backlog,result in ((None,900,False),(120,120,True),(120,119,False)):
            self.assertIs(eval(condition,dict(backlog=backlog,self=SimpleNamespace(policy=SimpleNamespace(max_backlog_seconds=limit)))),result)


class DrainCases(unittest.TestCase):
    def test_actual_pinned_validator_binding_retains_other_math_and_parser_gates(self):
        source=INSTALLED/drain.RELATIVE
        raw=source.read_bytes()
        original,_=drain.derive_validator(raw)
        def section(kind,value):
            if value.get("bad_shape"):raise ValueError("fixture record shape")
        def interval(value,lo,hi,name):
            if type(value) not in (int,float) or not math.isfinite(value) or not lo<=value<=hi:
                raise ValueError(name)
        namespace=dict(_section=section,_range=interval,asdict=lambda value:vars(value))
        for name in ("RuntimeSettingsV3","InputSettingsV3","EvidenceSettingsV3","IdentitySettingsV3","XVFSettingsV2","SchedulerSettingsV2"):
            namespace[name]=object()
        exec(compile(ast.fix_missing_locations(ast.Module(body=[original],type_ignores=[])),str(source),"exec"),namespace)
        method=namespace["validate"]
        method.__qualname__="ResearchProfileV3.validate"
        names=("runtime","tracker","input","embedding","identity","xvf","scheduler","schema_version")
        parent=make_dataclass("ResearchProfileV3",[(name,object) for name in names],frozen=True,
            namespace=dict(validate=method,_base=lambda self:SimpleNamespace(validate=lambda:None),
                field_usage=lambda self:dict(nondefault_inactive_fields=[])))
        profile=parent(
            SimpleNamespace(lane_drain_timeout_sec=200_000),
            SimpleNamespace(validated=lambda:None,field_usage=lambda:dict(nondefault_inactive_fields=[]),cues_enabled=False),
            SimpleNamespace(asr_tap="O0",identity_tap="O0",gain=1.,already_gained=True,
                            common_origin="paired_capture_sample_zero",source_block_ms=100),
            SimpleNamespace(evidence_policy="dual",rms_policy="dispatch",purity_policy="gate_only",
                short_window_sec=1.,window_sec=2.,hop_sec=.5,short_hop_sec=.5,mature_hop_sec=.5,
                sparse_hop_sec=1.,voice_observation_floor_sec=1.,minimum_clean_fraction=.8,
                minimum_contiguous_clean_sec=.45,clipping_fraction_max=1.,debt_target_unique_sec=2.,
                debt_target_disjoint_count=2,uncertainty_cosine=.5,cadence_direction_deg=35.,
                cadence_policy="fixed",cadence_cues_enabled=False),
            SimpleNamespace(mode="none",query_policy="mature",score_threshold=.5,prototype_update_cosine=.45,
                severe_query_cosine=.2,margin_threshold=.03,minimum_unique_sec=2.,name_memory_sec=30.,
                minimum_disjoint_count=2,max_gallery_profiles=256,max_track_states=256,max_intervals=256,max_prototypes=8),
            SimpleNamespace(mode="none",direction_change_deg=35.,direction_match_deg=35.,minimum_reliability=.8,
                direction_persistence_sec=.5,advisory_silence_sec=.5,advisory_min_utterance_sec=1.,
                endpoint_min_interval_sec=1.,endpoint_max_per_minute=2,endpoint_circuit_breaker_sec=2.),
            SimpleNamespace(mode="causal_watermark",revision_horizon_sec=2.,evidence_expiry_sec=2.,
                max_pending_events=512,max_events=1000,max_utterances=512,max_revisions_per_utterance=8),
            "edge-research-profile.v3")
        policy=profiles.SessionPolicy(maximum_session_seconds=200_000,manual_stop=True,max_drain_seconds=200_000)
        manifest={drain.RELATIVE:dict(sha256=drain.SOURCE_SHA256)}
        with self.assertRaises(ValueError):profile.validate()
        result=drain.capacity_drain_profile(profile,policy,INSTALLED,manifest)
        self.assertEqual(result.runtime.lane_drain_timeout_sec,200_000)
        self.assertIs(parent.validate,method)
        for bad in (True,float("inf"),200_001):
            with self.assertRaises(ValueError):
                drain.capacity_drain_profile(replace(profile,runtime=SimpleNamespace(lane_drain_timeout_sec=bad)),
                                             policy,INSTALLED,manifest)
        with self.assertRaises(ValueError):
            bad=replace(profile,identity=SimpleNamespace(**dict(vars(profile.identity),margin_threshold=3.)))
            drain.capacity_drain_profile(bad,policy,INSTALLED,manifest)
        with self.assertRaises(ValueError):
            bad=replace(profile,runtime=SimpleNamespace(lane_drain_timeout_sec=200_000,bad_shape=True))
            drain.capacity_drain_profile(bad,policy,INSTALLED,manifest)

    def test_pinned_profile_derivative_has_exact_reverse_and_original_nonmanual_limit(self):
        raw=(INSTALLED/drain.RELATIVE).read_bytes()
        original,changed=drain.derive_validator(raw)
        namespace=dict(_range=lambda value,lo,hi,name:
            None if type(value) in (int,float) and math.isfinite(value) and lo<=value<=hi
            else (_ for _ in ()).throw(ValueError(name)))
        target=[node for node in ast.walk(original) if isinstance(node,ast.Call)
                and isinstance(node.func,ast.Name) and node.func.id=="_range"
                and len(node.args)==4 and isinstance(node.args[3],ast.Constant)
                and node.args[3].value=="native lane drain timeout"][0]
        old_call=compile(ast.Expression(target),"original-drain","eval")
        new_call=[node for node in ast.walk(changed) if isinstance(node,ast.Call)
            and isinstance(node.func,ast.Name) and node.func.id=="_range"
            and len(node.args)==4 and isinstance(node.args[3],ast.Constant)
            and node.args[3].value=="native lane drain timeout"][0]
        new_call=compile(ast.fix_missing_locations(ast.Expression(new_call)),"capacity-drain","eval")
        namespace.update(self=SimpleNamespace(runtime=SimpleNamespace(lane_drain_timeout_sec=200_000)),
                         _capacity_lane_drain_seconds=200_000)
        with self.assertRaises(ValueError):eval(old_call,namespace)
        eval(new_call,namespace)
        for value in (True,float("inf"),200_001):
            namespace["self"].runtime.lane_drain_timeout_sec=value
            with self.assertRaises(ValueError):eval(new_call,namespace)
        bad=raw.replace(b"3600.",b"3601.",1)
        with self.assertRaises(ValueError):drain.derive_validator(bad)

    def test_foreign_profile_rejects_before_any_constructor_or_model(self):
        @dataclass(frozen=True)
        class Foreign:
            runtime:object
            def validate(self):pass
        policy=profiles.SessionPolicy(maximum_session_seconds=200_000,manual_stop=True,max_drain_seconds=200_000)
        with self.assertRaises(ValueError):
            drain.capacity_drain_profile(Foreign(SimpleNamespace(lane_drain_timeout_sec=200_000)),policy,INSTALLED,
                {drain.RELATIVE:dict(sha256=drain.SOURCE_SHA256)})


if __name__ == "__main__":
    raise SystemExit("Use the registered runner documented in README_DISK_CAPACITY_POLICY.md")
