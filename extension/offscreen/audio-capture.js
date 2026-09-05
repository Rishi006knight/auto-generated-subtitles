/**
 * Subtitle AI - Offscreen Audio Capture & Streaming Engine
 * 
 * Capabilities:
 * - Tab audio capture via chrome.tabCapture streamId
 * - Loopback audio routing to preserve speaker output for the user
 * - High-speed downsampling to 16kHz mono 16-bit PCM
 * - Client-side VAD energy gating to prevent sending silent audio
 * - Ping/Pong heartbeat for dynamic RTT latency calculation
 * - Smart Auto-Pause Control message routing (lag_warning, lag_clear)
 * - Chunk-ID aware subtitle message dispatching to active tab
 */

let audioContext = null;
let mediaStream = null;
let scriptProcessor = null;
let socket = null;
let targetTabId = null;
let activeSessionId = null;

// Client-Side VAD State
let isSpeechActive = false;
let silenceFramesCount = 0;
let lastSilencePingTime = 0;
let lastPingTime = 0;
let currentEstimatedRttMs = 50;

// Pre-roll hangover buffer (keeps ~200ms audio prior to speech onset)
const prerollChunks = [];
const MAX_PREROLL_CHUNKS = 3;

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.target !== "offscreen") return;

  switch (message.type) {
    case "START_AUDIO_STREAM":
      startCapture(message.payload)
        .then(() => sendResponse({ status: "started" }))
        .catch((err) => sendResponse({ status: "error", error: err.message }));
      return true;

    case "STOP_AUDIO_STREAM":
      stopCapture();
      sendResponse({ status: "stopped" });
      break;

    case "UPDATE_CONFIG":
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({
          type: "config",
          language: message.payload.language,
          model: message.payload.model,
          offset: message.payload.offset,
        }));
      }
      break;

    case "SYNC_TIME":
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({
          type: "sync",
          video_time: message.payload.videoTime,
          offset: message.payload.offset || 0.0,
          client_time: performance.now(),
        }));
      }
      break;
  }
});

async function startCapture(payload) {
  const { streamId, tabId, sessionId, wsUrl, language, model, offset } = payload;
  targetTabId = tabId;
  activeSessionId = sessionId;

  // 1. Capture tab media stream
  mediaStream = await navigator.mediaDevices.getUserMedia({
    audio: {
      mandatory: {
        chromeMediaSource: "tab",
        chromeMediaSourceId: streamId,
      },
    },
    video: false,
  });

  // 2. Setup Web Audio API Context
  audioContext = new (window.AudioContext || window.webkitAudioContext)();
  const source = audioContext.createMediaStreamSource(mediaStream);

  // Loopback to speaker output so video audio isn't muted
  source.connect(audioContext.destination);

  // 3. Connect WebSocket to ASR Backend
  const fullWsUrl = `${wsUrl.replace(/\/+$/, "")}/${sessionId}`;
  socket = new WebSocket(fullWsUrl);
  socket.binaryType = "arraybuffer";

  socket.onopen = () => {
    console.log("[Offscreen] Connected to WebSocket ASR Backend:", fullWsUrl);
    socket?.send(JSON.stringify({
      type: "config",
      language: language || "auto",
      model: model || "base",
      offset: offset || 0.0,
    }));
    notifyStatus("connected");
    startHeartbeatPing();
  };

  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);

      // Handle Smart Auto-Pause Control Messages from Backend
      if (data.type === "control") {
        chrome.runtime.sendMessage({
          target: "content",
          tabId: targetTabId,
          type: "CONTROL_ACTION",
          action: data.action, // 'lag_warning' or 'lag_clear'
          queue_size: data.queue_size,
        });
        return;
      }

      if (data.type === "pong") {
        const now = performance.now();
        currentEstimatedRttMs = Math.max(10, Math.round(now - data.client_time));
      } else if (data.type === "subtitle" || data.type === "partial" || data.type === "final") {
        chrome.runtime.sendMessage({
          target: "content",
          tabId: targetTabId,
          type: "SUBTITLE_CUE",
          payload: {
            ...data,
            estimated_rtt_ms: currentEstimatedRttMs,
          },
        });
      }
    } catch (e) {
      console.error("[Offscreen] Error parsing WebSocket packet:", e);
    }
  };

  socket.onerror = (err) => {
    console.error("[Offscreen] WebSocket error:", err);
    notifyStatus("error");
  };

  socket.onclose = () => {
    console.log("[Offscreen] WebSocket connection closed");
    notifyStatus("idle");
  };

  // 4. Setup Audio Downsampling & Client-side VAD
  const bufferSize = 4096;
  scriptProcessor = audioContext.createScriptProcessor(bufferSize, 1, 1);
  const nativeSampleRate = audioContext.sampleRate;
  const targetSampleRate = 16000;

  scriptProcessor.onaudioprocess = (audioProcessingEvent) => {
    if (!socket || socket.readyState !== WebSocket.OPEN) return;

    const inputData = audioProcessingEvent.inputBuffer.getChannelData(0);
    const resampledData = resampleTo16k(inputData, nativeSampleRate, targetSampleRate);

    // Client-side RMS Energy calculation
    let sumSquares = 0;
    for (let i = 0; i < resampledData.length; i++) {
      sumSquares += resampledData[i] * resampledData[i];
    }
    const rmsEnergy = Math.sqrt(sumSquares / resampledData.length);
    const speechThreshold = 0.008;

    const pcm16Data = convertFloat32ToInt16(resampledData);

    if (rmsEnergy >= speechThreshold) {
      if (!isSpeechActive) {
        isSpeechActive = true;
        while (prerollChunks.length > 0) {
          const preChunk = prerollChunks.shift();
          if (preChunk) socket.send(preChunk.buffer);
        }
      }
      silenceFramesCount = 0;
      socket.send(pcm16Data.buffer);
    } else {
      silenceFramesCount++;
      prerollChunks.push(pcm16Data);
      if (prerollChunks.length > MAX_PREROLL_CHUNKS) {
        prerollChunks.shift();
      }

      if (isSpeechActive && silenceFramesCount < 5) {
        socket.send(pcm16Data.buffer);
      } else if (isSpeechActive && silenceFramesCount >= 5) {
        isSpeechActive = false;
      } else {
        const now = performance.now();
        if (now - lastSilencePingTime > 2500) {
          lastSilencePingTime = now;
          socket.send(JSON.stringify({ type: "silence_ping", client_time: now }));
        }
      }
    }
  };

  source.connect(scriptProcessor);
  scriptProcessor.connect(audioContext.destination);
}

function startHeartbeatPing() {
  const pingInterval = setInterval(() => {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      clearInterval(pingInterval);
      return;
    }
    const now = performance.now();
    lastPingTime = now;
    socket.send(JSON.stringify({ type: "ping", client_time: now }));
  }, 3000);
}

function resampleTo16k(audioBuffer, sourceRate, targetRate) {
  if (sourceRate === targetRate) return audioBuffer;

  const ratio = sourceRate / targetRate;
  const newLength = Math.round(audioBuffer.length / ratio);
  const result = new Float32Array(newLength);
  let offsetResult = 0;
  let offsetBuffer = 0;

  while (offsetResult < result.length) {
    const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
    let accum = 0;
    let count = 0;
    for (let i = offsetBuffer; i < nextOffsetBuffer && i < audioBuffer.length; i++) {
      accum += audioBuffer[i];
      count++;
    }
    result[offsetResult] = count > 0 ? accum / count : 0;
    offsetResult++;
    offsetBuffer = nextOffsetBuffer;
  }
  return result;
}

function convertFloat32ToInt16(float32Array) {
  const int16Array = new Int16Array(float32Array.length);
  for (let i = 0; i < float32Array.length; i++) {
    const s = Math.max(-1, Math.min(1, float32Array[i]));
    int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return int16Array;
}

function stopCapture() {
  if (scriptProcessor) {
    scriptProcessor.disconnect();
    scriptProcessor = null;
  }
  if (audioContext) {
    audioContext.close();
    audioContext = null;
  }
  if (mediaStream) {
    mediaStream.getTracks().forEach((track) => track.stop());
    mediaStream = null;
  }
  if (socket) {
    try {
      socket.send(JSON.stringify({ type: "flush" }));
      socket.close();
    } catch (e) {}
    socket = null;
  }
  isSpeechActive = false;
  prerollChunks.length = 0;
  notifyStatus("idle");
}

function notifyStatus(status) {
  chrome.runtime.sendMessage({
    target: "background",
    type: "STATUS_UPDATE",
    payload: { status, sessionId: activeSessionId },
  });
}
