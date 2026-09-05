"""
Sliding Window Session Manager
Ultra low-latency audio slicing (~0.6s - 1.3s) for near-instant speech subtitle generation.
"""
import time
import uuid
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class TranscriptionSession:
    session_id: str
    sample_rate: int = 16000
    language: Optional[str] = "auto"
    model_size: str = "tiny"

    # Audio buffer: 16-bit mono 16kHz PCM (32,000 bytes per second)
    audio_buffer: bytearray = field(default_factory=bytearray)
    max_buffer_bytes: int = 16000 * 2 * 2  # Max 2.0 seconds hard ceiling

    # Chunk & Subtitle Tracking
    current_chunk_id: str = field(default_factory=lambda: f"chunk_{uuid.uuid4().hex[:8]}")
    last_transcribed_text: str = ""

    # Timestamp Synchronization
    last_known_video_time: float = 0.0
    last_sync_timestamp: float = field(default_factory=time.time)
    user_time_offset: float = 0.0
    estimated_rtt_ms: float = 30.0

    def renew_chunk_id(self) -> str:
        self.current_chunk_id = f"chunk_{uuid.uuid4().hex[:8]}"
        return self.current_chunk_id

    def update_video_time(self, video_time: float, offset: float = 0.0):
        self.last_known_video_time = video_time
        self.last_sync_timestamp = time.time()
        self.user_time_offset = offset

    def append_raw_pcm(self, pcm_bytes: bytes):
        self.audio_buffer.extend(pcm_bytes)
        if len(self.audio_buffer) > self.max_buffer_bytes:
            excess = len(self.audio_buffer) - self.max_buffer_bytes
            self.audio_buffer = bytearray(self.audio_buffer[excess:])

    def extract_slice_for_asr(
        self,
        max_duration_sec: float = 1.3,
        min_duration_sec: float = 0.6,
        keep_tail_sec: float = 0.2,
    ) -> Optional[np.ndarray]:
        """
        Extracts rapid 0.6s - 1.3s slices for high-speed streaming transcription.
        """
        min_bytes = int(16000 * 2 * min_duration_sec)
        if len(self.audio_buffer) < min_bytes:
            return None

        slice_bytes = min(len(self.audio_buffer), int(16000 * 2 * max_duration_sec))
        raw_slice = bytes(self.audio_buffer[:slice_bytes])

        keep_bytes = int(keep_tail_sec * 16000 * 2)
        if len(self.audio_buffer) > slice_bytes:
            self.audio_buffer = bytearray(self.audio_buffer[slice_bytes - keep_bytes :])
        else:
            self.audio_buffer = bytearray(self.audio_buffer[-keep_bytes:])

        int16_data = np.frombuffer(raw_slice, dtype=np.int16)
        return int16_data.astype(np.float32) / 32768.0

    def clear_buffer(self):
        self.audio_buffer.clear()

    def get_current_video_base_time(self) -> float:
        elapsed = time.time() - self.last_sync_timestamp
        latency_sec = (self.estimated_rtt_ms / 2.0) / 1000.0
        base = self.last_known_video_time + elapsed + self.user_time_offset - latency_sec
        return max(0.0, base)


class SessionManager:
    def __init__(self):
        self._sessions: Dict[str, TranscriptionSession] = {}

    def get_or_create(self, session_id: str) -> TranscriptionSession:
        if session_id not in self._sessions:
            self._sessions[session_id] = TranscriptionSession(session_id=session_id)
        return self._sessions[session_id]

    def remove_session(self, session_id: str):
        if session_id in self._sessions:
            del self._sessions[session_id]

    def count(self) -> int:
        return len(self._sessions)
