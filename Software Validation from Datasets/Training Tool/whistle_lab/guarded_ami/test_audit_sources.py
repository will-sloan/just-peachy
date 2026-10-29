"""Tests for the provenance gate, using synthetic metadata only."""
import unittest

from audit_sources import classify, identities


class ProvenanceGateTests(unittest.TestCase):
    def test_all_exposure_roles_exclude_sessions(self):
        result = classify(["S01", "S02", "S03"], ["S01"], ["S02"], ["S03"])
        self.assertEqual(result["unexposed_local_sessions"], [])

    def test_repeated_views_do_not_create_fresh_sessions(self):
        result = classify(["S01", "S01", "S02"], ["S01"], [], [])
        self.assertEqual(result["available_session_count"], 2)
        self.assertEqual(result["unexposed_local_sessions"], ["S02"])

    def test_absent_and_blank_identities_fail_closed(self):
        for invalid in ([None], [""], ["   "]):
            with self.assertRaises(ValueError):
                identities(invalid)


if __name__ == "__main__":
    unittest.main()
