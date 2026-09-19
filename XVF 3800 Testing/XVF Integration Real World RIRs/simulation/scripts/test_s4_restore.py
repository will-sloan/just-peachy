"""Offline restoration regressions; see README_S4_RESTORE.md. No device imports."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import re
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parents[1]
# Use the established recorder numerical dependency without importing PortAudio,
# the Control class, recovery entry point, or any device enumeration code.
sys.path.insert(0, str(ROOT / "tools/xvf321/python_deps"))
import numpy as np


def production_function(path, name, namespace):
    """Compile precisely one production function, excluding module side effects."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    module = ast.Module(body=[node], type_ignores=[])
    exec(compile(module, str(path), "exec"), namespace)
    return namespace[name]


namespace = {"np": np, "re": re}
values = production_function(SCRIPTS / "s3_hardware.py", "values", namespace)
restore_exposed = production_function(SCRIPTS / "s4_restore.py", "restore_exposed", namespace)


class FakeControl:
    """Getter/setter text transport driven entirely by test data."""

    def __init__(self, initial, setter_readbacks=(), supported=None):
        self.state = {k: list(v) for k, v in initial.items()}
        self.setter_readbacks = list(setter_readbacks)
        self.supported = set(initial) if supported is None else set(supported)
        self.calls = []

    @property
    def writes(self):
        return [(name, args) for name, args in self.calls if args]

    def query(self, name, *args):
        self.calls.append((name, args))
        if name not in self.supported:
            raise RuntimeError("Unsupported control command " + name)
        if args:
            if not self.setter_readbacks:
                raise AssertionError("Unexpected setter call beyond bounded fixture")
            self.state[name] = list(self.setter_readbacks.pop(0))
        return name + " " + " ".join(str(v) for v in self.state[name]) + "\n"


class RestoreRegression(unittest.TestCase):
    target = 84.72903
    adjacent_decimal = 84.72902

    def test_one_ulp_up_restores_exact_original_getter(self):
        c = FakeControl({"PP_AGCGAIN": [60.]}, [[self.adjacent_decimal], [self.target]])
        result = restore_exposed(c, {"PP_AGCGAIN": [self.target]})
        expected = float(np.nextafter(np.float32(self.target), np.float32(np.inf)))
        self.assertEqual(expected, 84.72903442382812)
        self.assertEqual(c.writes, [("PP_AGCGAIN", (self.target,)), ("PP_AGCGAIN", (expected,))])
        self.assertTrue(result["exact_match"])
        self.assertEqual(result["observed"], {"PP_AGCGAIN": [self.target]})
        self.assertEqual(len(result["float32_roundtrip_recovery"]), 1)
        self.assertEqual(result["float32_roundtrip_recovery"][0]["maximum_adjustment_float32_ulp"], 1)

    def test_downward_adjacent_input_can_be_second_and_last_attempt(self):
        c = FakeControl({"PP_AGCGAIN": [60.]}, [[self.adjacent_decimal], [self.adjacent_decimal], [self.target]])
        result = restore_exposed(c, {"PP_AGCGAIN": [self.target]})
        x = np.float32(self.target)
        self.assertEqual([a[0] for _, a in c.writes[1:]], [float(np.nextafter(x, np.float32(np.inf))), float(np.nextafter(x, np.float32(-np.inf)))])
        self.assertEqual(len(result["float32_roundtrip_recovery"]), 2)
        self.assertEqual(len(c.writes), 3)
        self.assertTrue(result["exact_match"])

    def test_close_readback_is_never_accepted_by_tolerance(self):
        c = FakeControl({"PP_AGCGAIN": [60.]}, [[self.adjacent_decimal]] * 3)
        with self.assertRaisesRegex(RuntimeError, "no tolerance-based acceptance"):
            restore_exposed(c, {"PP_AGCGAIN": [self.target]})
        self.assertEqual(len(c.writes), 3, "One requested setter plus at most two adjacent inputs")
        self.assertEqual(c.state["PP_AGCGAIN"], [self.adjacent_decimal])

    def test_large_mismatch_stops_without_adjacent_inputs(self):
        c = FakeControl({"PP_AGCGAIN": [60.]}, [[self.target + .1]])
        with self.assertRaisesRegex(RuntimeError, "exact readback"):
            restore_exposed(c, {"PP_AGCGAIN": [self.target]})
        self.assertEqual(c.writes, [("PP_AGCGAIN", (self.target,))])

    def test_roundtrip_recovery_is_unsupported_for_other_commands(self):
        c = FakeControl({"PP_AGCMAXGAIN": [60.]}, [[self.adjacent_decimal]])
        with self.assertRaisesRegex(RuntimeError, "PP_AGCMAXGAIN exact readback"):
            restore_exposed(c, {"PP_AGCMAXGAIN": [self.target]})
        self.assertEqual(len(c.writes), 1)

    def test_already_equal_read_only_setting_is_not_written(self):
        c = FakeControl({"GPI_INDEX": [0], "PP_AGCGAIN": [self.target]})
        result = restore_exposed(c, {"GPI_INDEX": [0], "PP_AGCGAIN": [self.target]})
        self.assertEqual(c.writes, [])
        self.assertEqual(c.calls, [("GPI_INDEX", ()), ("PP_AGCGAIN", ())])
        self.assertEqual(result["set_commands"], [])
        self.assertEqual(result["float32_roundtrip_recovery"], [])
        self.assertTrue(result["exact_match"])

    def test_unknown_control_error_propagates_without_writes(self):
        c = FakeControl({})
        with self.assertRaisesRegex(RuntimeError, "Unsupported control command"):
            restore_exposed(c, {"UNSUPPORTED_COMMAND": [1]})
        self.assertEqual(c.writes, [])

    def test_direct_exact_setter_needs_no_roundtrip_recovery(self):
        c = FakeControl({"PP_AGCGAIN": [60.]}, [[self.target]])
        result = restore_exposed(c, {"PP_AGCGAIN": [self.target]})
        self.assertEqual(len(c.writes), 1)
        self.assertEqual(result["float32_roundtrip_recovery"], [])
        self.assertTrue(result["exact_match"])

    def test_getter_nonfinite_value_is_rejected_before_writes(self):
        c = FakeControl({"PP_AGCGAIN": [float("nan")]})
        with self.assertRaisesRegex(RuntimeError, "Nonfinite configuration"):
            restore_exposed(c, {"PP_AGCGAIN": [self.target]})
        self.assertEqual(c.writes, [])


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(RestoreRegression)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({"status": "PASS" if result.wasSuccessful() else "FAIL", "tests_run": result.testsRun,
        "hardware_access": False, "production_function": "s4_restore.restore_exposed",
        "production_module_sha256": hashlib.sha256((SCRIPTS / "s4_restore.py").read_bytes()).hexdigest(),
        "method": "Production restoration function and actual getter parser compiled from AST; no hardware module imports"}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
