"""
Voice Activity Detection (VAD)
Filters silence and extracts active speech segments to reduce latency,
prevent hallucinations, and optimize ASR compute.
"""
import numpy as np
from typing import List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class SileroVADWrapper:
    def __init__(self, sample_rate: int = 16000, threshold: float = 0.5):
        self.sample_rate = sample_rate
        self.threshold = threshold
        self.model = None
        self.utils = None
        self._init_silero()

    def _init_silero(self):
        try:
            import torch
            torch.set_num_threads(1)
            model, utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                onnx=False,
                trust_repo=True,
            )
            self.model = model
            self.utils = utils
            logger.info("Silero VAD model initialized successfully.")
        except Exception as e:
            logger.warning(f"Could not load Silero VAD ({e}). Falling back to adaptive Energy VAD.")
            self.model = None

    def is_speech_chunk(self, audio_chunk_float32: np.ndarray) -> bool:
        """
        Determines whether a single audio chunk (e.g. 512 samples at 16kHz) contains speech.
        """
        if self.model is not None:
            try:
                import torch
                tensor_chunk = torch.from_numpy(audio_chunk_float32)
                confidence = self.model(tensor_chunk, self.sample_rate).item()
                return confidence >= self.threshold
            except Exception as e:
                logger.error(f"Silero VAD inference error: {e}")

        # Fallback: Root Mean Square (RMS) energy threshold
        rms = np.sqrt(np.mean(audio_chunk_float32 ** 2))
        return rms > 0.01

    def get_speech_timestamps(
        self, audio_float32: np.ndarray, min_speech_duration_ms: int = 250, min_silence_duration_ms: int = 300
    ) -> List[Tuple[float, float]]:
        """
        Returns list of (start_sec, end_sec) intervals of detected speech.
        """
        if self.model is not None and self.utils is not None:
            try:
                import torch
                get_speech_ts = self.utils[0]
                wav_tensor = torch.from_numpy(audio_float32)
                timestamps = get_speech_ts(
                    wav_tensor,
                    self.model,
                    sampling_rate=self.sample_rate,
                    threshold=self.threshold,
                    min_speech_duration_ms=min_speech_duration_ms,
                    min_silence_duration_ms=min_silence_duration_ms,
                )
                return [
                    (ts["start"] / self.sample_rate, ts["end"] / self.sample_rate)
                    for ts in timestamps
                ]
            except Exception as e:
                logger.error(f"Silero timestamp extraction error: {e}")

        # Fallback energy-based windowed segmentation
        frame_size = int(self.sample_rate * 0.03)  # 30ms frames
        if len(audio_float32) < frame_size:
            return [(0.0, len(audio_float32) / self.sample_rate)]

        num_frames = len(audio_float32) // frame_size
        energies = [
            np.sqrt(np.mean(audio_float32[i * frame_size : (i + 1) * frame_size] ** 2))
            for i in range(num_frames)
        ]
        threshold = max(0.008, np.mean(energies) * 0.5)

        speech_segments = []
        in_speech = False
        start_frame = 0

        for i, energy in enumerate(energies):
            if energy >= threshold and not in_speech:
                in_speech = True
                start_frame = i
            elif energy < threshold and in_speech:
                in_speech = False
                start_sec = (start_frame * frame_size) / self.sample_rate
                end_sec = (i * frame_size) / self.sample_rate
                if (end_sec - start_sec) >= (min_speech_duration_ms / 1000.0):
                    speech_segments.append((start_sec, end_sec))

        if in_speech:
            start_sec = (start_frame * frame_size) / self.sample_rate
            end_sec = len(audio_float32) / self.sample_rate
            speech_segments.append((start_sec, end_sec))

        return speech_segments
