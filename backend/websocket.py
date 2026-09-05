"""
Production Streaming WebSocket Handler
Zero-lag streaming architecture with rapid bounded windowing and graceful disconnection handling.
"""
import json
import time
import logging
import asyncio
import numpy as np
from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
from sessions import SessionManager, TranscriptionSession
from asr import ASREngine
from vad import SileroVADWrapper
from subtitles import SubtitleEngine

logger = logging.getLogger(__name__)


class SessionQueueState:
    def __init__(self, maxsize: int = 25):
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self.is_connected: bool = True
        self.worker_task: asyncio.Task = None


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
        self.queue_states: dict[str, SessionQueueState] = {}

    async def handle_connection(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        session = self.session_manager.get_or_create(session_id)
        queue_state = SessionQueueState(maxsize=25)
        self.queue_states[session_id] = queue_state

        logger.info(f"Client connected: session_id={session_id}")

        try:
            await websocket.send_json({
                "type": "connected",
                "session_id": session_id,
                "status": "ready",
                "model": self.asr_engine.current_model_size,
                "device": self.asr_engine.device,
            })
        except Exception:
            return

        # Launch ASR worker task
        queue_state.worker_task = asyncio.create_task(
            self._asr_worker_loop(websocket, session, queue_state)
        )

        try:
            while True:
                message = await websocket.receive()

                if "bytes" in message and message["bytes"]:
                    raw_bytes = message["bytes"]
                    if queue_state.queue.full():
                        try:
                            _ = queue_state.queue.get_nowait()
                        except asyncio.QueueEmpty:
                            pass
                    await queue_state.queue.put(raw_bytes)

                elif "text" in message and message["text"]:
                    try:
                        data = json.loads(message["text"])
                        msg_type = data.get("type")

                        if msg_type == "ping":
                            client_time = data.get("client_time", 0)
                            if websocket.client_state == WebSocketState.CONNECTED:
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
                            session.clear_buffer()

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

                            if websocket.client_state == WebSocketState.CONNECTED:
                                await websocket.send_json({
                                    "type": "config_ack",
                                    "language": session.language,
                                    "model": self.asr_engine.current_model_size,
                                    "offset": session.user_time_offset,
                                })

                        elif msg_type == "flush":
                            session.clear_buffer()

                    except json.JSONDecodeError:
                        pass

        except (WebSocketDisconnect, RuntimeError):
            pass
        except Exception as e:
            logger.debug(f"Connection loop terminated: {e}")
        finally:
            queue_state.is_connected = False
            if queue_state.worker_task:
                queue_state.worker_task.cancel()
            if session_id in self.queue_states:
                del self.queue_states[session_id]
            self.session_manager.remove_session(session_id)
            logger.info(f"Client disconnected: session_id={session_id}")

    async def _asr_worker_loop(
        self, websocket: WebSocket, session: TranscriptionSession, queue_state: SessionQueueState
    ):
        """Worker task processing audio chunks in fast, responsive windows."""
        while queue_state.is_connected:
            try:
                chunk = await queue_state.queue.get()
                session.append_raw_pcm(chunk)
                queue_state.queue.task_done()

                # Drain immediate pending packets into buffer
                while not queue_state.queue.empty():
                    extra = queue_state.queue.get_nowait()
                    session.append_raw_pcm(extra)
                    queue_state.queue.task_done()

                # Extract rapid audio slice (0.6s - 1.3s max)
                audio_slice = session.extract_slice_for_asr(max_duration_sec=1.3, min_duration_sec=0.6, keep_tail_sec=0.2)
                if audio_slice is not None and len(audio_slice) >= 9600: # ~0.6s+
                    await self._process_slice(websocket, session, queue_state, audio_slice)

            except asyncio.CancelledError:
                break
            except Exception as e:
                if not queue_state.is_connected:
                    break
                logger.debug(f"Worker iteration exception: {e}")
                await asyncio.sleep(0.02)

    async def _process_slice(
        self,
        websocket: WebSocket,
        session: TranscriptionSession,
        queue_state: SessionQueueState,
        audio_float32: np.ndarray,
    ):
        if not queue_state.is_connected or websocket.client_state != WebSocketState.CONNECTED:
            return

        # 1. VAD Check
        speech_intervals = self.vad.get_speech_timestamps(audio_float32)
        if not speech_intervals:
            return

        # 2. Fast Whisper ASR
        base_video_time = session.get_current_video_base_time()
        words, full_text, detected_lang = await self.asr_engine.transcribe_chunk_async(
            audio_float32,
            language=session.language,
        )

        clean_text = full_text.strip()
        if not clean_text:
            return

        # Deduplication check
        if clean_text == session.last_transcribed_text:
            return
        session.last_transcribed_text = clean_text

        # 3. Format Subtitle Cues
        session.renew_chunk_id()
        cues = self.subtitle_engine.words_to_cues(
            words,
            base_video_time=base_video_time,
            chunk_id=session.current_chunk_id,
            is_final=True,
        )

        if not queue_state.is_connected or websocket.client_state != WebSocketState.CONNECTED:
            return

        for cue in cues:
            try:
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
            except Exception:
                break
