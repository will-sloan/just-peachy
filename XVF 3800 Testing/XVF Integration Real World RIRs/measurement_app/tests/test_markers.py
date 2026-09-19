"""Offline acoustic marker tests with independent signal/path construction."""
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

from measurement_app.markers import marker_qc


class AcousticMarkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.path = Path(cls.temporary.name) / "played48k.wav"
        # Build the stimulus independently: random 48 kHz bursts with smooth
        # envelopes and FFT band limiting, not the detector's FIR/template code.
        bursts = []
        for seed in (742, 982):
            x = np.random.default_rng(seed).normal(size=960)
            spectrum = np.fft.rfft(x)
            frequency = np.fft.rfftfreq(len(x), 1 / 48000)
            spectrum[(frequency < 150) | (frequency > 6900)] = 0
            x = np.fft.irfft(spectrum, len(x)) * np.hanning(len(x))
            bursts.append(x / np.max(np.abs(x)) * .25)
        cls.played = np.zeros(18 * 48000)
        for t, burst in zip((2, 16, 16.2), (bursts[0], bursts[1], bursts[1])):
            at = round(t * 48000)
            cls.played[at:at + len(burst)] = burst
        sf.write(cls.path, cls.played, 48000, subtype="FLOAT")
        cls.excitation = {"id": "independent_1S_GAP_fixture.wav", "path": str(cls.path)}
        # Independent ideal band-limited rate conversion for the truth signal.
        spectrum = np.fft.rfft(cls.played)
        frequency = np.fft.rfftfreq(len(cls.played), 1 / 48000)
        spectrum[frequency > 7500] = 0
        reduced = np.fft.irfft(spectrum, len(cls.played))[::3]
        cls.bursts = [reduced[round(t * 16000) - 64:round(t * 16000) + 384].copy() for t in (2, 16, 16.2)]

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def capture(self, global_gap=0, end_separation=.2, missing_end=False, second_start=False):
        rng = np.random.default_rng(3502)
        count = 21 * 16000
        microphone = rng.normal(0, .0007, (count, 4))
        # Strong low-frequency contamination is deliberately outside the useful
        # marker band; each microphone also sees an independent noise component.
        time = np.arange(count) / 16000
        microphone += (.02 * np.sin(2 * np.pi * 213 * time))[:, None]
        offset = 1.347
        events = [offset + 2, offset + 16 + global_gap, offset + 16 + global_gap + end_separation]
        if missing_end:
            events = events[:2]
        for channel, delay in enumerate((0, 1, 3, 4)):
            for event, burst in zip(events, self.bursts):
                at = round(event * 16000) - 64 + delay
                # Direct sound plus a short coloration reflection and a much
                # later weaker reflection; signs and levels differ by channel.
                scale = (1, -.85, .9, .8)[channel]
                for reflection, amplitude in ((0, 1), (7, .22), (511, .12)):
                    microphone[at + reflection:at + reflection + len(burst), channel] += burst * scale * amplitude
            if second_start:
                at = round((offset + 2.11) * 16000) - 64 + delay
                microphone[at:at + len(self.bursts[0]), channel] += self.bursts[0] * (1, -.85, .9, .8)[channel]
        return microphone, offset, events

    def test_bandlimited_colored_delayed_four_microphones_return_review_only(self):
        audio, offset, events = self.capture()
        quality = marker_qc(audio, self.excitation, offset - .25)
        self.assertEqual(quality["status"], "REVIEW", quality["reason"])
        self.assertFalse(quality["automatic_alignment_accepted"])
        self.assertFalse(quality["clock_drift_qualified"])
        for candidate, event in zip(quality["markers"], events):
            self.assertLess(abs(candidate["time_s"] - event), .001)
            self.assertEqual(len(candidate["per_microphone_signed_correlation"]), 4)
        self.assertNotEqual(quality["template_sha256"][0], quality["template_sha256"][1])
        self.assertEqual(quality["template_sha256"][1], quality["template_sha256"][2])

    def test_silence_does_not_produce_qualified_candidates(self):
        quality = marker_qc(np.zeros((20 * 16000, 4)), self.excitation, 1)
        self.assertEqual(quality["status"], "RETAKE")
        self.assertEqual(quality["markers"], [None, None, None])

    def test_wrong_end_separation_is_measured_not_forced_to_200ms(self):
        audio, offset, _ = self.capture(end_separation=.26)
        quality = marker_qc(audio, self.excitation, offset)
        self.assertEqual(quality["status"], "RETAKE")
        self.assertAlmostEqual(quality["end_marker_separation_error_s"], .06, delta=.001)
        self.assertFalse(quality["gates"]["end_repeat_interval_within_tolerance"])

    def test_96ms_global_gap_fails_even_when_end_repeat_is_correct(self):
        audio, offset, _ = self.capture(global_gap=.096)
        quality = marker_qc(audio, self.excitation, offset)
        self.assertEqual(quality["status"], "RETAKE")
        self.assertAlmostEqual(quality["start_to_end_interval_error_s"], .096, delta=.001)
        self.assertTrue(quality["gates"]["end_repeat_interval_within_tolerance"])
        self.assertFalse(quality["gates"]["start_to_end_interval_within_tolerance"])
        self.assertIsNone(quality["approx_drift_ppm_if_same_arrival_peak"])

    def test_missing_second_end_is_not_a_duplicate_of_first(self):
        audio, offset, _ = self.capture(missing_end=True)
        quality = marker_qc(audio, self.excitation, offset)
        self.assertEqual(quality["status"], "RETAKE")
        if quality["markers"][1] and quality["markers"][2]:
            self.assertNotEqual(quality["markers"][1]["sample"], quality["markers"][2]["sample"])
        self.assertFalse(quality["gates"]["all_markers_meet_correlation_thresholds"])

    def test_competing_start_arrivals_remain_ambiguous(self):
        audio, offset, _ = self.capture(second_start=True)
        quality = marker_qc(audio, self.excitation, offset)
        self.assertEqual(quality["status"], "RETAKE")
        self.assertFalse(quality["gates"]["start_candidate_is_distinct"])

    def test_source_rate_and_microphone_count_are_enforced(self):
        audio, offset, _ = self.capture()
        with self.assertRaisesRegex(ValueError, "all four"):
            marker_qc(audio[:, :1], self.excitation, offset)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wrong_rate.wav"
            sf.write(path, np.zeros(32000), 16000)
            with self.assertRaisesRegex(ValueError, "48 kHz"):
                marker_qc(audio, {"id": "wrong.wav", "path": str(path)}, offset)

    def test_real_v2_16k_asset_is_not_the_played48k_marker(self):
        assets = Path(__file__).resolve().parents[1] / "assets/excitation_v2"
        source = assets / "JP_XVF_IMPULSE_1S_GAP_PLUS_ESS_80-7500Hz_10s_48k_PCM16.wav"
        isolated = assets / "JP_XVF_BANDLIMITED_IMPULSE_MARKER_16k_PCM16.wav"
        if not source.is_file() or not isolated.is_file():
            self.skipTest("Verified V2 assets unavailable")
        played, source_rate = sf.read(source)
        wrong, wrong_rate = sf.read(isolated)
        self.assertEqual((source_rate, wrong_rate), (48000, 16000))
        start = played[96000:96960:3]
        end = played[768000:768960:3]
        self.assertLess(abs(np.dot(start, wrong)) / (np.linalg.norm(start) * np.linalg.norm(wrong)), .15)
        self.assertFalse(np.array_equal(start, end))
        np.testing.assert_array_equal(end, played[777600:778560:3])
        # An independently sampled ideal capture exercises the exact real file
        # through the detector without expecting artificially perfect correlation.
        microphone = np.zeros(18 * 16000)
        for at, burst in zip((32000, 256000, 259200), (start, end, end)):
            microphone[at:at + 320] = burst
        quality = marker_qc(np.column_stack([microphone] * 4), {"id": source.name, "path": str(source)}, 0)
        self.assertEqual(quality["status"], "REVIEW", quality["reason"])
        self.assertNotEqual(quality["template_sha256"][0], quality["template_sha256"][1])


if __name__ == "__main__":
    unittest.main()
