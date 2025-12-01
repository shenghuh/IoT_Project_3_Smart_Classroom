"""
mic_processor.py

Measures volume from the laptop microphone using a short blocking recording.
Returns approximate volume in decibels (dB, negative values).
"""

import numpy as np
import sounddevice as sd


class MicrophoneProcessor:
    def __init__(
        self,
        samplerate: int = 16_000,
        block_duration: float = 0.5,
        channels: int = 1,
    ):
        """
        :param samplerate: Audio sample rate in Hz.
        :param block_duration: Length of each measurement window in seconds.
        :param channels: Number of audio channels (1 = mono).
        """
        self.samplerate = samplerate
        self.block_duration = block_duration
        self.channels = channels

    def measure_volume_db(self) -> float:
        """
        Record a short block of audio and compute its RMS volume in dB.

        :return: volume in dB (negative number; closer to 0 = louder)
        """
        n_samples = int(self.samplerate * self.block_duration)

        # sounddevice returns float32 samples in [-1, 1]
        recording = sd.rec(
            n_samples,
            samplerate=self.samplerate,
            channels=self.channels,
            dtype="float32",
        )
        sd.wait()

        # Mono: average channels, then compute RMS
        data = recording.mean(axis=1)
        rms = float(np.sqrt(np.mean(data**2)) + 1e-12)  # avoid log(0)

        volume_db = 20 * np.log10(rms)
        return volume_db
