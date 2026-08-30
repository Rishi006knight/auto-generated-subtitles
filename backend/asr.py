"""
ASR Engine using faster-whisper
Maintains persistent Whisper models in RAM/VRAM for low-latency streaming transcription.
"""
import numpy as np
import logging
from typing import List, Optional, Tuple, Dict, Any
from subtitles import WordTimestamp

logger = logging.getLogger(__name__)


class ASREngine:
    def __init__(
        self,
        default_model_size: str = "base",
        device: str = "auto",
        compute_type: str = "default",
    ):
        self.device = device
        self.compute_type = compute_type
        self.current_model_size = default_model_size
        self.model = None
        self._detect_hardware()
        self.load_model(default_model_size)

    def _detect_hardware(self):
        if self.device == "auto":
            try:
                import torch
                if torch.cuda.is_available():
                    self.device = "cuda"
                    if self.compute_type == "default":
                        self.compute_type = "float16"
                else:
                    self.device = "cpu"
                    if self.compute_type == "default":
                        self.compute_type = "int8"
            except ImportError:
                self.device = "cpu"
                self.compute_type = "int8"
        logger.info(f"ASR Device set to: {self.device}, Compute Type: {self.compute_type}")

    def load_model(self, model_size: str):
        """Loads or switches the active Whisper model without re-creating if already loaded."""
        if self.model is not None and self.current_model_size == model_size:
            return

        try:
            from faster_whisper import WhisperModel

            logger.info(f"Loading faster-whisper model '{model_size}' on {self.device} ({self.compute_type})...")
            self.model = WhisperModel(
                model_size,
                device=self.device,
                compute_type=self.compute_type,
                cpu_threads=4,
            )
            self.current_model_size = model_size
            logger.info(f"Model '{model_size}' loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load faster-whisper model '{model_size}': {e}")
            if self.device == "cuda":
                logger.info("Falling back to CPU int8...")
                self.device = "cpu"
                self.compute_type = "int8"
                self.load_model(model_size)

    def transcribe_chunk(
        self,
        audio_float32: np.ndarray,
        language: Optional[str] = None,
        task: str = "transcribe",
        initial_prompt: Optional[str] = None,
    ) -> Tuple[List[WordTimestamp], str, str]:
        """
        Transcribes 16kHz mono Float32 audio buffer.
        Returns: (List[WordTimestamp], full_text, detected_language)
        """
        if self.model is None:
            raise RuntimeError("ASR Model is not loaded.")

        if len(audio_float32) == 0:
            return [], "", language or "en"

        # If language is 'auto' or empty, pass None for auto-detection
        lang_arg = None if (not language or language.lower() in ("auto", "none")) else language

        segments, info = self.model.transcribe(
            audio_float32,
            language=lang_arg,
            task=task,
            beam_size=5,
            word_timestamps=True,
            vad_filter=False, # We handle external VAD
            initial_prompt=initial_prompt,
        )

        detected_lang = info.language
        words: List[WordTimestamp] = []
        full_text_parts = []

        for segment in segments:
            full_text_parts.append(segment.text.strip())
            if segment.words:
                for w in segment.words:
                    words.append(
                        WordTimestamp(
                            word=w.word,
                            start=w.start,
                            end=w.end,
                            probability=w.probability,
                        )
                    )
            else:
                # Fallback if word timestamps were unavailable
                words.append(
                    WordTimestamp(
                        word=segment.text.strip(),
                        start=segment.start,
                        end=segment.end,
                        probability=1.0,
                    )
                )

        full_text = " ".join(full_text_parts)
        return words, full_text, detected_lang
