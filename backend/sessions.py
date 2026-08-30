"""
Session Manager
Maintains client session state, rolling audio buffer, video timestamp sync,
and subtitle generation history for each connected browser tab.
"""
import time
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
    
    # Audio buffer
    audio_buffer: bytearray = field(default_factory=bytearray)
    processed_samples: int = 0
    
    # Timestamp synchronization
    last_known_video_time: float = 0.0
    last_sync_timestamp: float = field(default_factory=time.time)
    user_time_offset: float = 0.0  # fallback offset from extension slider
    
    # Transcription tracking
    active_cues: List[SubtitleCue] = field(default_factory=list)
    last_transcribed_text: str = ""
    is_speaking: bool = False
    
    def update_video_time(self, video_time: float, offset: float = 0.0):
        """Updates synchronization checkpoint sent from content script."""
        self.last_known_video_time = video_time
        self.last_sync_timestamp = time.time()
        self.user_time_offset = offset

    def append_raw_pcm(self, pcm_bytes: bytes):
        """Appends raw PCM audio bytes (16-bit signed integer or 32-bit float)."""
        self.audio_buffer.extend(pcm_bytes)

    def get_audio_float32(self, dtype_str: str = "int16") -> np.ndarray:
        """Converts accumulated buffer into float32 normalized [-1.0, 1.0] ndarray."""
        if not self.audio_buffer:
            return np.array([], dtype=np.float32)

        if dtype_str == "int16":
            int16_data = np.frombuffer(self.audio_buffer, dtype=np.int16)
            return int16_data.astype(np.float32) / 32768.0
        elif dtype_str == "float32":
            return np.frombuffer(self.audio_buffer, dtype=np.float32)
        else:
            raise ValueError(f"Unsupported PCM dtype: {dtype_str}")

    def clear_buffer(self, keep_last_seconds: float = 0.5):
        """Discards processed audio while keeping a small rolling tail for context/boundary continuity."""
        keep_bytes = int(keep_last_seconds * self.sample_rate * 2) # for 16-bit PCM
        if len(self.audio_buffer) > keep_bytes:
            self.processed_samples += (len(self.audio_buffer) - keep_bytes) // 2
            self.audio_buffer = bytearray(self.audio_buffer[-keep_bytes:])

    def get_current_video_base_time(self) -> float:
        """
        Calculates the estimated real video timestamp for the current audio frame
        accounting for elapsed playback time and user offset adjustments.
        """
        elapsed = time.time() - self.last_sync_timestamp
        base = self.last_known_video_time + elapsed + self.user_time_offset
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
