"""
Session Manager
Maintains client session state, rolling audio context buffer, video timestamp sync,
and subtitle generation history for each connected browser tab.
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

    # Rolling Audio Buffer (16-bit PCM)
    audio_buffer: bytearray = field(default_factory=bytearray)
    processed_samples: int = 0

    # Rolling Audio Prefix Context (1.0s of previous audio for acoustic continuity)
    prefix_context: bytearray = field(default_factory=bytearray)

    # Chunk Tracking
    current_chunk_id: str = field(default_factory=lambda: f"chunk_{uuid.uuid4().hex[:8]}")
    chunk_accumulated_seconds: float = 0.0

    # Timestamp & Latency Synchronization
    last_known_video_time: float = 0.0
    last_sync_timestamp: float = field(default_factory=time.time)
    user_time_offset: float = 0.0
    estimated_rtt_ms: float = 50.0

    def renew_chunk_id(self) -> str:
        self.current_chunk_id = f"chunk_{uuid.uuid4().hex[:8]}"
        self.chunk_accumulated_seconds = 0.0
        return self.current_chunk_id

    def update_video_time(self, video_time: float, offset: float = 0.0):
        self.last_known_video_time = video_time
        self.last_sync_timestamp = time.time()
        self.user_time_offset = offset

    def append_raw_pcm(self, pcm_bytes: bytes):
        self.audio_buffer.extend(pcm_bytes)
        # 16-bit PCM mono = 2 bytes per sample @ 16kHz
        new_seconds = len(pcm_bytes) / (self.sample_rate * 2)
        self.chunk_accumulated_seconds += new_seconds

    def get_full_audio_float32(self, include_prefix: bool = True) -> np.ndarray:
        """
        Combines prefix context with current buffer into normalized float32 ndarray.
        """
        combined = bytearray()
        if include_prefix and self.prefix_context:
            combined.extend(self.prefix_context)
        combined.extend(self.audio_buffer)

        if not combined:
            return np.array([], dtype=np.float32)

        int16_data = np.frombuffer(combined, dtype=np.int16)
        return int16_data.astype(np.float32) / 32768.0

    def roll_buffer(self, keep_prefix_seconds: float = 1.0):
        """
        Stores rolling context prefix for acoustic continuity and clears processed buffer.
        """
        prefix_bytes = int(keep_prefix_seconds * self.sample_rate * 2)
        if len(self.audio_buffer) > prefix_bytes:
            self.prefix_context = bytearray(self.audio_buffer[-prefix_bytes:])
        else:
            self.prefix_context = bytearray(self.audio_buffer)
        self.audio_buffer.clear()

    def get_current_video_base_time(self) -> float:
        elapsed = time.time() - self.last_sync_timestamp
        # Latency compensation: subtract half RTT from calculated time
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
