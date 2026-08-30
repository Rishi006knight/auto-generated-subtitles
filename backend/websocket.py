"""
Production Streaming WebSocket Endpoint
Handles real-time binary audio streaming, VAD gating, chunk_id management,
partial/final subtitle emission, and latency compensation.
"""
import json
import time
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
        logger.info(f"Client connected: session_id={session_id}")

        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "status": "ready",
            "model": self.asr_engine.current_model_size,
            "device": self.asr_engine.device,
        })

        min_partial_bytes = 16000 * 2 * 1.5   # 1.5s
        max_chunk_bytes = 16000 * 2 * 5.0     # 5.0s max chunk
        last_partial_time = asyncio.get_event_loop().time()

        try:
            while True:
                message = await websocket.receive()

                if "bytes" in message and message["bytes"]:
                    raw_bytes = message["bytes"]
                    session.append_raw_pcm(raw_bytes)

                    now = asyncio.get_event_loop().time()
                    time_since_partial = now - last_partial_time
                    buf_len = len(session.audio_buffer)

                    # Check for partial vs final emission
                    if buf_len >= max_chunk_bytes:
                        # Finalize chunk
                        await self._process_session_audio(websocket, session, is_final=True)
                        session.roll_buffer(keep_prefix_seconds=1.0)
                        session.renew_chunk_id()
                        last_partial_time = now
                    elif buf_len >= min_partial_bytes and time_since_partial >= 1.2:
                        # Partial update
                        await self._process_session_audio(websocket, session, is_final=False)
                        last_partial_time = now

                elif "text" in message and message["text"]:
                    try:
                        data = json.loads(message["text"])
                        msg_type = data.get("type")

                        if msg_type == "ping":
                            client_time = data.get("client_time", 0)
                            await websocket.send_json({
                                "type": "pong",
                                "client_time": client_time,
                                "server_time": time.time() * 1000,
                            })

                        elif msg_type == "sync":
                            video_time = float(data.get("video_time", 0.0))
                            offset = float(data.get("offset", 0.0))
                            session.update_video_time(video_time, offset)

                        elif msg_type == "silence_ping":
                            # If we have residual audio when silence starts, flush it as final
                            if len(session.audio_buffer) >= (16000 * 2 * 0.8):
                                await self._process_session_audio(websocket, session, is_final=True)
                                session.roll_buffer(keep_prefix_seconds=0.5)
                                session.renew_chunk_id()

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
                                await self._process_session_audio(websocket, session, is_final=True)
                                session.roll_buffer(keep_prefix_seconds=0.0)
                                session.renew_chunk_id()

                    except json.JSONDecodeError:
                        logger.warning(f"Malformed JSON from session {session_id}")

        except WebSocketDisconnect:
            logger.info(f"Client disconnected: session_id={session_id}")
        except Exception as e:
            logger.error(f"WebSocket session error ({session_id}): {e}", exc_info=True)
        finally:
            self.session_manager.remove_session(session_id)

    async def _process_session_audio(
        self, websocket: WebSocket, session: TranscriptionSession, is_final: bool = False
    ):
        audio_float32 = session.get_full_audio_float32(include_prefix=True)
        if len(audio_float32) < 4000:
            return

        # 1. Server-side VAD filtering
        speech_intervals = self.vad.get_speech_timestamps(audio_float32)
        if not speech_intervals:
            return

        # 2. Thread-safe Whisper ASR
        base_video_time = session.get_current_video_base_time()
        words, full_text, detected_lang = await self.asr_engine.transcribe_chunk_async(
            audio_float32,
            language=session.language,
        )

        if not full_text.strip():
            return

        # 3. Format Subtitles
        cues = self.subtitle_engine.words_to_cues(
            words,
            base_video_time=base_video_time,
            chunk_id=session.current_chunk_id,
            is_final=is_final,
        )

        # 4. Dispatch Subtitle packets
        for cue in cues:
            await websocket.send_json({
                "type": "subtitle",
                "id": cue.id,
                "start": cue.start,
                "end": cue.end,
                "text": cue.text,
                "type": cue.type,
                "final": cue.final,
                "language": detected_lang,
                "confidence": round(cue.confidence, 2),
                "server_timestamp": time.time(),
                "client_video_time": base_video_time,
            })
