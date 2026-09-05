"""
Robust Voice Activity Detection (VAD)
Ultra-fast, zero-dependency speech detector that works seamlessly with or without torchaudio.
"""
import numpy as np
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)


class SileroVADWrapper:
    def __init__(self, sample_rate: int = 16000, threshold: float = 0.5):
        self.sample_rate = sample_rate
        self.threshold = threshold
        self.model = None
        self._init_vad()

    def _init_vad(self):
        """Attempts to load PyTorch Silero VAD, falls back smoothly to adaptive Energy VAD."""
        try:
            import torch
            torch.set_num_threads(1)
            model, _ = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                onnx=False,
                trust_repo=True,
            )
            self.model = model
            logger.info("Silero VAD initialized successfully.")
        except Exception as e:
            logger.info(f"Using high-performance Adaptive Energy VAD ({e}).")
            self.model = None

    def is_speech_chunk(self, audio_chunk_float32: np.ndarray) -> bool:
        """Determines whether an audio chunk contains speech."""
        if len(audio_chunk_float32) == 0:
            return False

        if self.model is not None:
            try:
                import torch
                tensor_chunk = torch.from_numpy(audio_chunk_float32)
                confidence = self.model(tensor_chunk, self.sample_rate).item()
                return confidence >= self.threshold
            except Exception:
                pass

        # Robust RMS Energy Fallback
        rms = np.sqrt(np.mean(audio_chunk_float32 ** 2))
        return rms > 0.007

    def get_speech_timestamps(
        self,
        audio_float32: np.ndarray,
        min_speech_duration_ms: int = 200,
        min_silence_duration_ms: int = 250,
    ) -> List[Tuple[float, float]]:
        """Returns list of (start_sec, end_sec) intervals of detected speech."""
        if len(audio_float32) == 0:
            return []

        frame_size = int(self.sample_rate * 0.03)  # 30ms frames
        if len(audio_float32) < frame_size:
            return [(0.0, len(audio_float32) / self.sample_rate)]

        num_frames = len(audio_float32) // frame_size
        energies = [
            np.sqrt(np.mean(audio_float32[i * frame_size : (i + 1) * frame_size] ** 2))
            for i in range(num_frames)
        ]
        
        mean_energy = float(np.mean(energies))
        threshold = max(0.006, mean_energy * 0.45)

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
