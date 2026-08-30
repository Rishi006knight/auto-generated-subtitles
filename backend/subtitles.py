"""
Subtitle Engine
Formats raw ASR transcription and word timestamps into human-readable,
properly segmented subtitle cues with line wrapping, duration bounds, CPS pacing,
and unique chunk identifiers.
"""
from dataclasses import dataclass, field
from typing import List, Optional
import re
import uuid


@dataclass
class WordTimestamp:
    word: str
    start: float
    end: float
    probability: float = 1.0


@dataclass
class SubtitleCue:
    id: str
    start: float
    end: float
    text: str
    type: str = "final"  # 'partial' | 'final'
    final: bool = True
    confidence: float = 1.0


class SubtitleEngine:
    def __init__(
        self,
        max_lines: int = 2,
        max_line_length: int = 42,
        min_duration: float = 1.0,
        max_duration: float = 6.0,
        max_cps: float = 21.0,
        pause_split_threshold: float = 0.8,
    ):
        self.max_lines = max_lines
        self.max_line_length = max_line_length
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.max_cps = max_cps
        self.pause_split_threshold = pause_split_threshold

    def format_lines(self, text: str) -> str:
        text = text.strip()
        if not text or len(text) <= self.max_line_length:
            return text

        words = text.split()
        lines: List[str] = []
        current_line = []
        current_len = 0

        for word in words:
            word_len = len(word)
            new_len = current_len + (1 if current_len > 0 else 0) + word_len

            if new_len > self.max_line_length and current_line:
                lines.append(" ".join(current_line))
                current_line = [word]
                current_len = word_len
                if len(lines) >= self.max_lines:
                    break
            else:
                current_line.append(word)
                current_len = new_len

        if current_line and len(lines) < self.max_lines:
            lines.append(" ".join(current_line))
        elif current_line:
            lines[-1] = lines[-1] + " " + " ".join(current_line)

        return "\n".join(lines[: self.max_lines])

    def words_to_cues(
        self,
        words: List[WordTimestamp],
        base_video_time: float = 0.0,
        chunk_id: Optional[str] = None,
        is_final: bool = True,
    ) -> List[SubtitleCue]:
        if not words:
            return []

        cues: List[SubtitleCue] = []
        current_words: List[WordTimestamp] = []
        assigned_id = chunk_id or f"chunk_{uuid.uuid4().hex[:8]}"

        def flush_cue(word_list: List[WordTimestamp], final_flag: bool):
            if not word_list:
                return
            cue_text = " ".join(w.word.strip() for w in word_list if w.word.strip())
            if not cue_text:
                return
            formatted_text = self.format_lines(cue_text)

            cue_start = base_video_time + word_list[0].start
            cue_end = base_video_time + word_list[-1].end

            duration = max(self.min_duration, cue_end - cue_start)
            duration = min(self.max_duration, duration)
            min_reading_duration = len(formatted_text) / self.max_cps
            duration = max(duration, min_reading_duration)

            cues.append(
                SubtitleCue(
                    id=assigned_id,
                    start=round(cue_start, 2),
                    end=round(cue_start + duration, 2),
                    text=formatted_text,
                    type="final" if final_flag else "partial",
                    final=final_flag,
                    confidence=sum(w.probability for w in word_list) / len(word_list),
                )
            )

        for i, word in enumerate(words):
            current_words.append(word)
            text_so_far = " ".join(w.word for w in current_words)

            pause = 0.0
            if i < len(words) - 1:
                pause = words[i + 1].start - word.end

            cue_duration = word.end - current_words[0].start
            has_sentence_end = bool(re.search(r"[\.!?]$", word.word.strip()))

            if (
                pause >= self.pause_split_threshold
                or cue_duration >= self.max_duration
                or (has_sentence_end and len(text_so_far) >= 28)
                or len(text_so_far) >= (self.max_line_length * self.max_lines)
            ):
                flush_cue(current_words, final_flag=is_final)
                current_words = []

        if current_words:
            flush_cue(current_words, final_flag=is_final)

        return cues
