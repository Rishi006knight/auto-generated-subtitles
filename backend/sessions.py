"""
Production Real-Time Sliding Window Session Manager
Eliminates hallucination loops and buffer growth by capping audio windows to 2.0s max.
"""
import time
import uuid
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from subtitles import SubtitleCue


@dataclass
class TranscriptionSession:
    session_id: str
    sample_rate: int = 16000
    language: Optional[str] = "auto"
    model_size: str = "base"

    # Strict sliding window buffer (capped at 2.5 seconds = 80,000 bytes for 16-bit 16kHz PCM)
    audio_buffer: bytearray = field(default_factory=bytearray)
    max_buffer_bytes: int = 16000 * 2 * 2.5  # 2.5s max window

    # Chunk Tracking
    current_chunk_id: str = field(default_factory=lambda: f"chunk_{uuid.uuid4().hex[:8]}")
    last_transcribed_text: str = ""

    # Timestamp Synchronization
    last_known_video_time: float = 0.0
    last_sync_timestamp: float = field(default_factory=time.time)
    user_time_offset: float = 0.0
    estimated_rtt_ms: float = 50.0

    def renew_chunk_id(self) -> str:
        self.current_chunk_id = f"chunk_{uuid.uuid4().hex[:8]}"
        return self.current_chunk_id

    def update_video_time(self, video_time: float, offset: float = 0.0):
        self.last_known_video_time = video_time
        self.last_sync_timestamp = time.time()
        self.user_time_offset = offset

    def append_raw_pcm(self, pcm_bytes: bytes):
        self.audio_buffer.extend(pcm_bytes)
        # Prevent buffer growth: retain only the latest 2.5 seconds
        if len(self.audio_buffer) > self.max_buffer_bytes:
            excess = len(self.audio_buffer) - self.max_buffer_bytes
            self.audio_buffer = bytearray(self.audio_buffer[excess:])

    def get_audio_float32(self) -> np.ndarray:
        """Converts accumulated buffer into normalized float32 ndarray."""
        if not self.audio_buffer:
            return np.array([], dtype=np.float32)

        int16_data = np.frombuffer(self.audio_buffer, dtype=np.int16)
        return int16_data.astype(np.float32) / 32768.0

    def clear_buffer(self, keep_tail_seconds: float = 0.3):
        """Discards processed audio while keeping a tiny 300ms tail for boundary smoothness."""
        keep_bytes = int(keep_tail_seconds * self.sample_rate * 2)
        if len(self.audio_buffer) > keep_bytes:
            self.audio_buffer = bytearray(self.audio_buffer[-keep_bytes:])
        else:
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
