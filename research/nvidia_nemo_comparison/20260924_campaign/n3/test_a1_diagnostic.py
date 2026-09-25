"""No-model diagnostic guard regressions; see README_A1_DIAGNOSTIC.md."""
import json
import unittest
import numpy as np
from diagnose_a1_parity import fresh_feed, compare_arrays


class Tensor:
    def __init__(self, array): self.array = array
    def detach(self): return self
    def cpu(self): return self
    def numpy(self): return self.array


class DiagnosticTests(unittest.TestCase):
    def test_reference_mutation_cannot_change_ort_input(self):
        array = np.array([1., 2.], dtype=np.float32)
        feed = fresh_feed(['audio_signal'], [Tensor(array)])
        array[:] = 99
        np.testing.assert_array_equal(feed['audio_signal'], [1., 2.])

    def test_incomplete_or_duplicate_graph_inputs_refused(self):
        tensor = Tensor(np.zeros(1))
        for names, tensors in [(['x', 'y'], [tensor]), (['x', 'x'], [tensor, tensor])]:
            with self.assertRaises(ValueError): fresh_feed(names, tensors)

    def test_integer_state_lengths_require_exact_agreement(self):
        rows = compare_arrays([np.array([100000], dtype=np.int64)], [np.array([100001], dtype=np.int64)])
        self.assertFalse(rows[0]['within_tolerance'])

    def test_nonfinite_or_changed_shapes_are_recorded_as_failures(self):
        for actual in [np.array([np.nan]), np.array([1., 2.])]:
            rows = compare_arrays([actual], [np.array([1.])])
            self.assertFalse(rows[0]['within_tolerance'])
            json.dumps(rows, allow_nan=False)


if __name__ == '__main__': unittest.main()
