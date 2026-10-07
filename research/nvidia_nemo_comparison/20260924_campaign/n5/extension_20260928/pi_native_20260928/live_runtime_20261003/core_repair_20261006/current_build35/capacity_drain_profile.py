"""Exact installed profile drain derivative; README_DISK_CAPACITY_POLICY.md."""
import ast
from copy import deepcopy
from dataclasses import fields
import hashlib
import inspect
import math
from pathlib import Path
import stat
import textwrap

RELATIVE = "vendor/edge_speech_pipeline/research_profiles_v3.py"
SOURCE_SHA256 = "9f27f2c4ff1132a18e011c7e068594c1cb01eefe86350303d1806e8f46400b38"


def _same(left, right):
    return ast.dump(left, include_attributes=False) == ast.dump(right, include_attributes=False)


def derive_validator(raw):
    """Change one upper bound and prove reversing that change restores every AST node."""
    tree = ast.parse(raw)
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ResearchProfileV3"]
    methods = [node for node in classes[0].body if isinstance(node, ast.FunctionDef)
               and node.name == "validate"] if len(classes) == 1 else []
    if len(methods) != 1 or methods[0].decorator_list:
        raise ValueError("One exact installed profile validator required")
    original = methods[0]
    changed = deepcopy(original)
    expected = ast.parse('_range(self.runtime.lane_drain_timeout_sec, .01, 3600., "native lane drain timeout")',
                         mode="eval").body
    found = 0
    class Deadline(ast.NodeTransformer):
        def visit_Call(self, node):
            nonlocal found
            if _same(node, expected):
                found += 1
                node.args[2] = ast.Name(id="_capacity_lane_drain_seconds", ctx=ast.Load())
            return self.generic_visit(node)
    changed = Deadline().visit(changed)
    if found != 1:
        raise ValueError("Installed drain bound differs")
    restored = deepcopy(changed)
    restored_count = 0
    class Restore(ast.NodeTransformer):
        def visit_Name(self, node):
            nonlocal restored_count
            if node.id == "_capacity_lane_drain_seconds":
                restored_count += 1
                return ast.Constant(value=3600.0)
            return node
    restored = Restore().visit(restored)
    if restored_count != 1 or not _same(original, restored):
        raise ValueError("Drain derivative changed another profile condition")
    return original, changed


def capacity_drain_profile(profile, policy, installed_root, manifest):
    """Use only the finite reviewed manual capacity deadline; do not patch installed classes."""
    policy.validate()
    if not policy.manual_stop:
        profile.validate()
        return profile
    parent = type(profile)
    method = parent.validate
    source = Path(installed_root)/RELATIVE
    info = source.lstat()
    if (parent.__name__ != "ResearchProfileV3" or method.__qualname__ != "ResearchProfileV3.validate"
            or source.is_symlink() or getattr(info, "st_file_attributes", 0)&0x400
            or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 65536
            or Path(inspect.getsourcefile(method)).resolve() != source.resolve()
            or manifest[RELATIVE]["sha256"] != SOURCE_SHA256):
        raise ValueError("Exact installed profile class/source/origin required")
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError("Installed profile source changed")
    original, changed = derive_validator(raw)
    if not _same(original, ast.parse(textwrap.dedent(inspect.getsource(method))).body[0]):
        raise ValueError("Loaded profile validator differs from pinned source")
    namespace = dict(method.__globals__, _capacity_lane_drain_seconds=policy.max_drain_seconds)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[changed], type_ignores=[])),
                 str(source)+"#capacity-drain", "exec"), namespace)
    derived = namespace["validate"]

    class CapacityDrainProfile(parent):
        def validate(self):
            duration = self.runtime.lane_drain_timeout_sec
            if (type(duration) not in (int, float) or not math.isfinite(duration)
                    or duration != policy.max_drain_seconds):
                raise ValueError("Profile drain differs from exact finite capacity policy")
            return derived(self)

    result = CapacityDrainProfile(**{field.name: getattr(profile, field.name) for field in fields(profile)})
    result.validate()
    return result
