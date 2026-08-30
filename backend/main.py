"""
FastAPI Main Application
Entry point for Real-Time Streaming Subtitle Generator Backend.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from asr import ASREngine
from vad import SileroVADWrapper
from subtitles import SubtitleEngine
from sessions import SessionManager
from websocket import StreamingASRHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("subtitle-backend")

# Global instances
asr_engine: ASREngine = None
vad_wrapper: SileroVADWrapper = None
subtitle_engine: SubtitleEngine = None
session_manager: SessionManager = None
stream_handler: StreamingASRHandler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global asr_engine, vad_wrapper, subtitle_engine, session_manager, stream_handler
    logger.info("Initializing Subtitle AI Backend Services...")
    
    subtitle_engine = SubtitleEngine(
        max_lines=2,
        max_line_length=42,
        min_duration=1.0,
        max_duration=6.0,
        max_cps=21.0,
    )
    vad_wrapper = SileroVADWrapper(sample_rate=16000)
    asr_engine = ASREngine(default_model_size="base", device="auto")
    session_manager = SessionManager()
    stream_handler = StreamingASRHandler(
        session_manager=session_manager,
        asr_engine=asr_engine,
        vad_wrapper=vad_wrapper,
        subtitle_engine=subtitle_engine,
    )
    logger.info("Subtitle AI Backend Services initialized successfully.")
    yield
    logger.info("Shutting down Subtitle AI Backend...")


app = FastAPI(
    title="Subtitle AI Streaming ASR Backend",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return JSONResponse({
        "status": "healthy",
        "model": asr_engine.current_model_size if asr_engine else "uninitialized",
        "device": asr_engine.device if asr_engine else "unknown",
        "active_sessions": session_manager.count() if session_manager else 0,
    })


@app.websocket("/ws/transcribe/{session_id}")
async def websocket_transcribe(websocket: WebSocket, session_id: str):
    await stream_handler.handle_connection(websocket, session_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
