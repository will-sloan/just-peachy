"""Display-only casing fixtures. Run commands: ../docs/UI_ITERATION.md."""
import unittest
from prototype.app.casing import provisional_case


class CasingTests(unittest.TestCase):
    def test_expansion_and_retraction_are_stateless(self):
        revisions = ["", "PLEASE", "PLEASE SIT WITH", "PLEASE SIT", "PLEASE SIT WITH ME."]
        self.assertEqual([provisional_case(x) for x in revisions], ["", "Please", "Please sit with", "Please sit", "Please sit with me."])
        self.assertEqual(revisions[2], "PLEASE SIT WITH")

    def test_sentences_and_standalone_i(self):
        self.assertEqual(provisional_case("i think i'm ready. I'LL GO! are you? i’ve finished"),
                         "I think I'm ready. I'll go! Are you? I’ve finished")

    def test_known_names_and_explicit_acronyms(self):
        self.assertEqual(provisional_case("HELLO AMIRI AND MARY JANE. NASA USES ASR", ["Amiri", "Mary Jane"], ["NASA"]),
                         "Hello Amiri and Mary Jane. NASA uses ASR")

    def test_mixed_case_numbers_and_spacing_preserved(self):
        raw = "iPhone costs 3.5 at 10:30; eBay has 2 USB cables.\n  i agree"
        self.assertEqual(provisional_case(raw), "iPhone costs 3.5 at 10:30; eBay has 2 USB cables.\n  I agree")

    def test_name_boundaries_and_canonical_spelling(self):
        self.assertEqual(provisional_case("ANN ANSWERS ANNIE. EBAY", ["Ann", "eBay"]), "Ann answers annie. eBay")
        self.assertEqual(provisional_case("WE MET O’NEIL", ["O’Neil"]), "We met O’Neil")

    def test_never_invents_words_or_punctuation(self):
        self.assertEqual(provisional_case("UM I I THINK THE"), "Um I I think the")
        self.assertEqual(provisional_case("  ...  "), "  ...  ")
        with self.assertRaises(TypeError): provisional_case(None)


if __name__ == "__main__": unittest.main()
