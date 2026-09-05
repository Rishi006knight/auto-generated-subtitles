"""
High-Speed Streaming ASR Engine
Optimized for ultra-fast, low-latency CPU inference with instant startup.
"""
import os
import numpy as np
import logging
import asyncio
import re
from typing import List, Optional, Tuple
from subtitles import WordTimestamp

logger = logging.getLogger(__name__)

# Known phantom phrases generated during silence or background music
HALLUCINATION_PATTERNS = [
    re.compile(r"thank\s+you\s+for\s+watching", re.IGNORECASE),
    re.compile(r"thanks\s+for\s+watching", re.IGNORECASE),
    re.compile(r"please\s+subscribe", re.IGNORECASE),
    re.compile(r"subtitles\s+by", re.IGNORECASE),
    re.compile(r"transcribed\s+by", re.IGNORECASE),
    re.compile(r"like\s+and\s+subscribe", re.IGNORECASE),
    re.compile(r"watch\s+more\s+videos", re.IGNORECASE),
    re.compile(r"see\s+you\s+in\s+the\s+next\s+video", re.IGNORECASE),
    re.compile(r"(\b\w+\b)(?:\s+\1){2,}", re.IGNORECASE),  # 3+ consecutive identical words (looping)
]


class ASREngine:
    def __init__(
        self,
        default_model_size: str = "auto",
        device: str = "auto",
        compute_type: str = "default",
    ):
        self.device = device
        self.compute_type = compute_type
        self.num_threads = min(8, max(4, os.cpu_count() or 4))
        self._lock = asyncio.Lock()
        self.model = None

        self._detect_hardware()

        if default_model_size == "auto":
            self.current_model_size = "tiny" if self.device == "cpu" else "base"
        else:
            self.current_model_size = default_model_size

        self.load_model(self.current_model_size)

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

            # Pre-warm model to eliminate initial transcription delay
            dummy_audio = np.zeros(8000, dtype=np.float32)
            try:
                _ = list(self.model.transcribe(dummy_audio, beam_size=1, word_timestamps=False)[0])
            except Exception:
                pass

            logger.info(f"Model '{model_size}' ready and warm for real-time streaming.")
        except Exception as e:
            logger.warning(f"Failed to load '{model_size}' on {self.device}: {e}. Falling back to 'tiny' on CPU int8.")
            self.device = "cpu"
            self.compute_type = "int8"
            from faster_whisper import WhisperModel
            self.model = WhisperModel("tiny", device="cpu", compute_type="int8", cpu_threads=self.num_threads)
            self.current_model_size = "tiny"

    async def transcribe_chunk_async(
        self,
        audio_float32: np.ndarray,
        language: Optional[str] = None,
        task: str = "transcribe",
    ) -> Tuple[List[WordTimestamp], str, str]:
        async with self._lock:
            return await asyncio.to_thread(
                self.transcribe_chunk,
                audio_float32,
                language,
                task,
            )

    def transcribe_chunk(
        self,
        audio_float32: np.ndarray,
        language: Optional[str] = None,
        task: str = "transcribe",
    ) -> Tuple[List[WordTimestamp], str, str]:
        if self.model is None or len(audio_float32) == 0:
            return [], "", language or "en"

        lang_arg = None if (not language or language.lower() in ("auto", "none")) else language

        if self.current_model_size.endswith(".en"):
            lang_arg = "en"

        try:
            segments, info = self.model.transcribe(
                audio_float32,
                language=lang_arg,
                task=task,
                beam_size=1,                         # 3x faster than beam_size=5
                best_of=1,                           # single candidate for ultra-low latency
                temperature=0.0,                     # deterministic fast decoding
                condition_on_previous_text=False,    # Prevents hallucination feedback loops
                no_speech_threshold=0.5,             # Strictly drops silence
                compression_ratio_threshold=2.2,     # Drops repetitive text loops
                log_prob_threshold=-1.0,             # Drops low-confidence hallucinations
                word_timestamps=True,
                vad_filter=False,                    # Handled upstream
            )

            detected_lang = getattr(info, "language", language or "en")
            words: List[WordTimestamp] = []
            valid_text_parts = []

            for segment in segments:
                if getattr(segment, "no_speech_prob", 0.0) > 0.5:
                    continue

                if getattr(segment, "avg_logprob", 0.0) < -1.0:
                    continue

                if getattr(segment, "compression_ratio", 1.0) > 2.2:
                    continue

                clean_seg_text = segment.text.strip()
                if not clean_seg_text:
                    continue

                if any(pat.search(clean_seg_text) for pat in HALLUCINATION_PATTERNS):
                    continue

                valid_text_parts.append(clean_seg_text)

                if segment.words:
                    for w in segment.words:
                        if getattr(w, "probability", 1.0) >= 0.15:
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
            logger.error(f"Transcription error: {e}")
            return [], "", language or "en"
