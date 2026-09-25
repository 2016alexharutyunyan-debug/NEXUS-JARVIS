import math
import sys
import types
import unittest
from unittest.mock import patch

import numpy as np

from jarvis_wake_launcher import detect_clap, listen_once


class WakeClapTests(unittest.TestCase):
    def test_short_impulse_is_detected_as_clap(self):
        sample_rate = 44_100
        samples = np.zeros(sample_rate, dtype=np.float32)
        samples[4000:4012] = np.linspace(0.35, 1.0, 12, dtype=np.float32)
        self.assertTrue(detect_clap(samples, sample_rate))

    def test_steady_loud_tone_is_not_detected_as_clap(self):
        sample_rate = 44_100
        samples = np.array(
            [0.35 * math.sin(2.0 * math.pi * 440.0 * index / sample_rate) for index in range(sample_rate)],
            dtype=np.float32,
        )
        self.assertFalse(detect_clap(samples, sample_rate))

    def test_live_clap_returns_before_speech_recognition(self):
        sample_rate = 44_100

        class FakeStream:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, frames):
                block = np.zeros((frames, 1), dtype=np.float32)
                block[100:112, 0] = np.linspace(0.35, 1.0, 12, dtype=np.float32)
                return block, False

        sounddevice = types.SimpleNamespace(
            query_devices=lambda kind: {"default_samplerate": sample_rate},
            InputStream=lambda **_kwargs: FakeStream(),
        )
        speech_recognition = types.SimpleNamespace(
            Recognizer=lambda: self.fail("Speech recognizer should not run for a clap."),
            AudioData=object,
        )
        with patch.dict(
            sys.modules,
            {"sounddevice": sounddevice, "speech_recognition": speech_recognition},
        ):
            heard, peak, clap = listen_once()

        self.assertEqual(heard, "")
        self.assertGreater(peak, 0.9)
        self.assertTrue(clap)


if __name__ == "__main__":
    unittest.main()
