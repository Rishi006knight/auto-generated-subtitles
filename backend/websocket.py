"""
WebSocket Endpoint Handler
Coordinates real-time streaming audio ingestion, VAD, ASR transcription,
subtitle segmentation, and dispatching formatted cues back to the browser extension.
"""
import json
import logging
import asyncio
import numpy as np
from fastapi import WebSocket, WebSocketDisconnect
from sessions import SessionManager, TranscriptionSession
from asr import ASREngine
from vad import SileroVADWrapper
from subtitles import SubtitleEngine

logger = logging.getLogger(__name__)


class StreamingASRHandler:
    def __init__(
        self,
        session_manager: SessionManager,
        asr_engine: ASREngine,
        vad_wrapper: SileroVADWrapper,
        subtitle_engine: SubtitleEngine,
    ):
        self.session_manager = session_manager
        self.asr_engine = asr_engine
        self.vad = vad_wrapper
        self.subtitle_engine = subtitle_engine

    async def handle_connection(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        session = self.session_manager.get_or_create(session_id)
        logger.info(f"WebSocket client connected: session_id={session_id}")

        # Send initial confirmation
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "status": "ready",
            "model": self.asr_engine.current_model_size,
            "device": self.asr_engine.device,
        })

        min_process_bytes = 16000 * 2 * 1.5  # 1.5s of 16kHz 16-bit PCM (48,000 bytes)
        silence_flush_bytes = 16000 * 2 * 0.6 # 0.6s
        last_process_time = asyncio.get_event_loop().time()

        try:
            while True:
                message = await websocket.receive()

                if "bytes" in message and message["bytes"]:
                    raw_bytes = message["bytes"]
                    session.append_raw_pcm(raw_bytes)

                    now = asyncio.get_event_loop().time()
                    time_since_last = now - last_process_time
                    buffer_len = len(session.audio_buffer)

                    # Trigger transcription if buffer has accumulated >= 1.5s or > 0.8s elapsed with speech
                    if buffer_len >= min_process_bytes or (buffer_len >= silence_flush_bytes and time_since_last > 1.2):
                        await self._process_session_audio(websocket, session)
                        last_process_time = now

                elif "text" in message and message["text"]:
                    try:
                        data = json.loads(message["text"])
                        msg_type = data.get("type")

                        if msg_type == "sync":
                            video_time = float(data.get("video_time", 0.0))
                            offset = float(data.get("offset", 0.0))
                            session.update_video_time(video_time, offset)

                        elif msg_type == "config":
                            lang = data.get("language")
                            model_size = data.get("model")
                            offset = data.get("offset")
                            if lang is not None:
                                session.language = lang
                            if model_size and model_size != self.asr_engine.current_model_size:
                                self.asr_engine.load_model(model_size)
                            if offset is not None:
                                session.user_time_offset = float(offset)
                            
                            await websocket.send_json({
                                "type": "config_ack",
                                "language": session.language,
                                "model": self.asr_engine.current_model_size,
                                "offset": session.user_time_offset,
                            })

                        elif msg_type == "flush":
                            if len(session.audio_buffer) > 0:
                                await self._process_session_audio(websocket, session, force_final=True)
                                session.clear_buffer(keep_last_seconds=0.0)

                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON received from session {session_id}")

        except WebSocketDisconnect:
            logger.info(f"WebSocket client disconnected: session_id={session_id}")
        except Exception as e:
            logger.error(f"Error in session {session_id}: {e}", exc_info=True)
        finally:
            self.session_manager.remove_session(session_id)

    async def _process_session_audio(
        self, websocket: WebSocket, session: TranscriptionSession, force_final: bool = False
    ):
        audio_float32 = session.get_audio_float32(dtype_str="int16")
        if len(audio_float32) < 3200:  # Less than 0.2s
            return

        # 1. Voice Activity Detection
        speech_intervals = self.vad.get_speech_timestamps(audio_float32)
        if not speech_intervals:
            # Silence detected - discard silence and prevent Whisper hallucination
            session.clear_buffer(keep_last_seconds=0.2)
            return

        # 2. Run Whisper ASR
        base_video_time = session.get_current_video_base_time()
        words, full_text, detected_lang = await asyncio.to_thread(
            self.asr_engine.transcribe_chunk,
            audio_float32,
            language=session.language,
        )

        if not full_text.strip():
            session.clear_buffer(keep_last_seconds=0.3)
            return

        # 3. Format Subtitles using SubtitleEngine
        cues = self.subtitle_engine.words_to_cues(
            words,
            base_video_time=base_video_time,
            is_final=force_final or len(words) > 5,
        )

        # 4. Dispatch Subtitle packets to Chrome Extension
        for cue in cues:
            await websocket.send_json({
                "type": "subtitle",
                "start": cue.start,
                "end": cue.end,
                "text": cue.text,
                "final": cue.final,
                "language": detected_lang,
                "confidence": round(cue.confidence, 2),
            })

        session.clear_buffer(keep_last_seconds=0.4)
