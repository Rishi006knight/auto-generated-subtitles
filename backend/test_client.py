"""
Test Client for Subtitle AI Streaming WebSocket
Simulates audio streaming from browser to backend to test connection,
VAD, ASR, subtitle packaging, and latency.
"""
import asyncio
import websockets
import json
import numpy as np
import sys


async def test_streaming_client(server_url: str = "ws://127.0.0.1:8000/ws/transcribe/test-session-123"):
    print(f"Connecting to {server_url}...")
    async with websockets.connect(server_url) as ws:
        # Wait for handshake
        res = await ws.recv()
        print(f"Connected response: {res}")

        # Send initial config & sync
        config_payload = {
            "type": "config",
            "language": "en",
            "model": "base",
            "offset": 0.0,
        }
        await ws.send(json.dumps(config_payload))
        print("Sent config payload.")

        sync_payload = {
            "type": "sync",
            "video_time": 10.0,
            "offset": 0.0,
        }
        await ws.send(json.dumps(sync_payload))
        print("Sent sync payload.")

        # Simulate generating 3 seconds of audio (sine wave pulse to trigger VAD, or silence)
        sample_rate = 16000
        duration_sec = 3.0
        t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), endpoint=False)
        # 440 Hz tone modulated as mock audio signal
        audio_float = 0.5 * np.sin(2 * np.pi * 440 * t) * (np.sin(2 * np.pi * 2 * t) > 0)
        audio_int16 = (audio_float * 32767).astype(np.int16).tobytes()

        chunk_size = 1600 * 2  # 100ms chunks of 16-bit PCM
        print(f"Streaming {duration_sec}s of audio chunks...")

        for i in range(0, len(audio_int16), chunk_size):
            chunk = audio_int16[i : i + chunk_size]
            await ws.send(chunk)
            await asyncio.sleep(0.1)

        # Send flush command
        await ws.send(json.dumps({"type": "flush"}))

        # Listen for subtitle responses with timeout
        print("Listening for subtitles...")
        try:
            while True:
                response = await asyncio.wait_for(ws.recv(), timeout=3.0)
                print(f"Received from server: {response}")
        except asyncio.TimeoutError:
            print("Finished listening (timed out after 3s of silence). Test complete.")


if __name__ == "__main__":
    asyncio.run(test_streaming_client())
