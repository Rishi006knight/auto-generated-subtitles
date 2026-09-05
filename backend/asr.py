"""
Production ASR Engine with High-Speed Real-Time CPU Optimization
Optimizations:
- beam_size=1 for 3x faster real-time streaming inference on CPU
- cpu_threads scaled to available CPU cores
- Persistent model caching in VRAM/RAM
- Whisper Hallucination Defense
"""
import os
import numpy as np
import logging
import asyncio
import re
from typing import List, Optional, Tuple, Dict, Any
from subtitles import WordTimestamp

logger = logging.getLogger(__name__)

HALLUCINATION_PATTERNS = [
    re.compile(r"thank\s+you\s+for\s+watching", re.IGNORECASE),
    re.compile(r"please\s+subscribe", re.IGNORECASE),
    re.compile(r"subtitles\s+by", re.IGNORECASE),
    re.compile(r"transcribed\s+by", re.IGNORECASE),
    re.compile(r"like\s+and\s+subscribe", re.IGNORECASE),
    re.compile(r"watch\s+more\s+videos", re.IGNORECASE),
    re.compile(r"(\b\w+\b)(?:\s+\1){3,}", re.IGNORECASE),
]


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
        self.num_threads = min(8, max(4, os.cpu_count() or 4))
        self._lock = asyncio.Lock()
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
            except (ImportError, Exception):
                self.device = "cpu"
                self.compute_type = "int8"
        logger.info(f"ASR Hardware: Device={self.device}, ComputeType={self.compute_type}, CPU Threads={self.num_threads}")

    def load_model(self, model_size: str):
        if self.model is not None and self.current_model_size == model_size:
            return

        try:
            from faster_whisper import WhisperModel

            logger.info(f"Loading faster-whisper model '{model_size}' on {self.device} ({self.compute_type})...")
            self.model = WhisperModel(
                model_size,
                device=self.device,
                compute_type=self.compute_type,
                cpu_threads=self.num_threads,
            )
            self.current_model_size = model_size
            logger.info(f"Model '{model_size}' loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load model on {self.device}: {e}. Retrying on CPU int8...")
            self.device = "cpu"
            self.compute_type = "int8"
            from faster_whisper import WhisperModel
            self.model = WhisperModel(model_size, device="cpu", compute_type="int8", cpu_threads=self.num_threads)
            self.current_model_size = model_size

    async def transcribe_chunk_async(
        self,
        audio_float32: np.ndarray,
        language: Optional[str] = None,
        task: str = "transcribe",
        initial_prompt: Optional[str] = None,
    ) -> Tuple[List[WordTimestamp], str, str]:
        async with self._lock:
            return await asyncio.to_thread(
                self.transcribe_chunk,
                audio_float32,
                language,
                task,
                initial_prompt,
            )

    def transcribe_chunk(
        self,
        audio_float32: np.ndarray,
        language: Optional[str] = None,
        task: str = "transcribe",
        initial_prompt: Optional[str] = None,
    ) -> Tuple[List[WordTimestamp], str, str]:
        if self.model is None or len(audio_float32) == 0:
            return [], "", language or "en"

        lang_arg = None if (not language or language.lower() in ("auto", "none")) else language

        try:
            # beam_size=1 (greedy search) is 3x faster than beam_size=5 for streaming real-time
            segments, info = self.model.transcribe(
                audio_float32,
                language=lang_arg,
                task=task,
                beam_size=1,
                word_timestamps=True,
                vad_filter=False,
                initial_prompt=initial_prompt,
                condition_on_previous_text=False,
                temperature=0.0,
                no_speech_threshold=0.6,
            )

            detected_lang = info.language
            words: List[WordTimestamp] = []
            valid_text_parts = []

            for segment in segments:
                if getattr(segment, "no_speech_prob", 0.0) > 0.6:
                    continue
                if getattr(segment, "avg_logprob", 0.0) < -1.0:
                    continue
                if getattr(segment, "compression_ratio", 1.0) > 2.4:
                    continue

                clean_seg_text = segment.text.strip()
                if any(pat.search(clean_seg_text) for pat in HALLUCINATION_PATTERNS):
                    continue

                valid_text_parts.append(clean_seg_text)

                if segment.words:
                    for w in segment.words:
                        if w.probability >= 0.2:
                            words.append(
                                WordTimestamp(
                                    word=w.word,
                                    start=w.start,
                                    end=w.end,
                                    probability=w.probability,
                                )
                            )
                else:
                    words.append(
                        WordTimestamp(
                            word=clean_seg_text,
                            start=segment.start,
                            end=segment.end,
                            probability=1.0,
                        )
                    )

            full_text = " ".join(valid_text_parts)
            return words, full_text, detected_lang

        except Exception as e:
            logger.error(f"Error during transcription inference: {e}", exc_info=True)
            return [], "", language or "en"
