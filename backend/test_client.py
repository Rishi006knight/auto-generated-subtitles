"""
Production Synthetic Test Client & WER Benchmark
Simulates real-time browser audio streaming, calculates latency,
and evaluates Word Error Rate (WER) against ground-truth dialogue.
"""
import asyncio
import websockets
import json
import numpy as np
import time
from typing import List, Tuple


def calculate_wer(reference: str, hypothesis: str) -> float:
    """Calculates Word Error Rate (WER) using Levenshtein distance on words."""
    r_words = reference.lower().split()
    h_words = hypothesis.lower().split()

    d = np.zeros((len(r_words) + 1, len(h_words) + 1), dtype=np.uint32)
    for i in range(len(r_words) + 1):
        d[i][0] = i
    for j in range(len(h_words) + 1):
        d[0][j] = j

    for i in range(1, len(r_words) + 1):
        for j in range(1, len(h_words) + 1):
            if r_words[i - 1] == h_words[j - 1]:
                d[i][j] = d[i - 1][j - 1]
            else:
                substitution = d[i - 1][j - 1] + 1
                insertion = d[i][j - 1] + 1
                deletion = d[i - 1][j] + 1
                d[i][j] = min(substitution, insertion, deletion)

    return float(d[len(r_words)][len(h_words)]) / max(1, len(r_words))


def generate_synthetic_audio(duration_sec: float = 3.0, sample_rate: int = 16000) -> bytes:
    """Generates synthetic modulated audio waveform."""
    t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), endpoint=False)
    # 440 Hz fundamental with harmonic envelope
    audio_float = 0.4 * np.sin(2 * np.pi * 320 * t) * (np.sin(2 * np.pi * 1.5 * t) > 0)
    audio_int16 = (audio_float * 32767).astype(np.int16).tobytes()
    return audio_int16


async def run_benchmark(server_url: str = "ws://127.0.0.1:8000/ws/transcribe/benchmark-session"):
    print(f"==================================================")
    print(f"  Subtitle AI - Streaming ASR Benchmark Client    ")
    print(f"==================================================")
    print(f"Connecting to {server_url}...")

    ground_truth = "We need to leave now because it is getting dark outside."
    received_transcripts = []

    async with websockets.connect(server_url) as ws:
        # Handshake
        init_res = await ws.recv()
        print(f"[*] Server Handshake: {init_res}")

        # Send Config
        await ws.send(json.dumps({
            "type": "config",
            "language": "en",
            "model": "base",
            "offset": 0.0,
        }))

        # Send Ping for RTT measurement
        start_ping = time.time() * 1000
        await ws.send(json.dumps({"type": "ping", "client_time": start_ping}))

        # Stream 3.5s of audio in 100ms chunks
        pcm_data = generate_synthetic_audio(duration_sec=3.5)
        chunk_size = 1600 * 2  # 100ms

        print(f"[*] Streaming audio chunks in real time...")
        for i in range(0, len(pcm_data), chunk_size):
            chunk = pcm_data[i : i + chunk_size]
            await ws.send(chunk)
            await asyncio.sleep(0.08)

        # Flush
        await ws.send(json.dumps({"type": "flush"}))

        # Collect Subtitle responses
        print("[*] Collecting subtitle cues...")
        try:
            while True:
                raw_msg = await asyncio.wait_for(ws.recv(), timeout=2.5)
                data = json.loads(raw_msg)
                if data.get("type") == "pong":
                    rtt = (time.time() * 1000) - data.get("client_time", 0)
                    print(f"[*] Ping/Pong RTT Latency: {rtt:.1f}ms")
                elif data.get("type") in ("subtitle", "partial", "final"):
                    text = data.get("text", "")
                    chunk_id = data.get("id", "n/a")
                    status = "FINAL" if data.get("final") else "PARTIAL"
                    print(f"  └─ [{status}] (id={chunk_id}, start={data.get('start')}s, end={data.get('end')}s): '{text}'")
                    if data.get("final"):
                        received_transcripts.append(text)
        except asyncio.TimeoutError:
            print("[*] Streaming evaluation completed.")

        if received_transcripts:
            full_hypothesis = " ".join(received_transcripts)
            wer = calculate_wer(ground_truth, full_hypothesis)
            print(f"\n================ BENCHMARK RESULTS ================")
            print(f"Ground Truth : '{ground_truth}'")
            print(f"Transcribed  : '{full_hypothesis}'")
            print(f"Word Error Rate (WER): {wer:.2%}")
            print(f"===================================================")


if __name__ == "__main__":
    asyncio.run(run_benchmark())
