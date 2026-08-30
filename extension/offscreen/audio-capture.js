/**
 * Subtitle AI - Offscreen Audio Capture & WebSocket Streamer
 * Captures tab audio, loops to output speakers, resamples to 16kHz mono PCM,
 * streams binary frames over WebSocket, and routes subtitle responses to content script.
 */

let audioContext = null;
let mediaStream = null;
let scriptProcessor = null;
let socket = null;
let targetTabId = null;
let activeSessionId = null;

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
        }));
      }
      break;
  }
});

async function startCapture(payload) {
  const { streamId, tabId, sessionId, wsUrl, language, model, offset } = payload;
  targetTabId = tabId;
  activeSessionId = sessionId;

  // 1. Obtain Tab Media Stream
  mediaStream = await navigator.mediaDevices.getUserMedia({
    audio: {
      mandatory: {
        chromeMediaSource: "tab",
        chromeMediaSourceId: streamId,
      },
    },
    video: false,
  });

  // 2. Initialize AudioContext
  audioContext = new (window.AudioContext || window.webkitAudioContext)();
  const source = audioContext.createMediaStreamSource(mediaStream);

  // Loop back audio to default destination so user still hears audio
  source.connect(audioContext.destination);

  // 3. Connect WebSocket to ASR Backend
  const fullWsUrl = `${wsUrl.replace(/\/+$/, "")}/${sessionId}`;
  socket = new WebSocket(fullWsUrl);
  socket.binaryType = "arraybuffer";

  socket.onopen = () => {
    console.log("[Offscreen] Connected to ASR WebSocket server:", fullWsUrl);
    // Send initial configuration
    socket.send(JSON.stringify({
      type: "config",
      language: language || "auto",
      model: model || "base",
      offset: offset || 0.0,
    }));
    notifyStatus("connected");
  };

  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === "subtitle") {
        // Forward subtitle to active tab content script
        chrome.runtime.sendMessage({
          target: "content",
          tabId: targetTabId,
          type: "SUBTITLE_CUE",
          payload: data,
        });
      }
    } catch (e) {
      console.error("[Offscreen] Error parsing WebSocket message:", e);
    }
  };

  socket.onerror = (err) => {
    console.error("[Offscreen] WebSocket error:", err);
    notifyStatus("error");
  };

  socket.onclose = () => {
    console.log("[Offscreen] WebSocket closed");
    notifyStatus("disconnected");
  };

  // 4. Setup Audio Downsampler (SampleRate -> 16000Hz mono PCM)
  const bufferSize = 4096;
  scriptProcessor = audioContext.createScriptProcessor(bufferSize, 1, 1);

  const nativeSampleRate = audioContext.sampleRate;
  const targetSampleRate = 16000;

  scriptProcessor.onaudioprocess = (audioProcessingEvent) => {
    if (!socket || socket.readyState !== WebSocket.OPEN) return;

    const inputData = audioProcessingEvent.inputBuffer.getChannelData(0);
    const resampledData = resampleTo16k(inputData, nativeSampleRate, targetSampleRate);
    const pcm16Data = convertFloat32ToInt16(resampledData);

    socket.send(pcm16Data.buffer);
  };

  source.connect(scriptProcessor);
  scriptProcessor.connect(audioContext.destination);
}

function resampleTo16k(audioBuffer, sourceRate, targetRate) {
  if (sourceRate === targetRate) {
    return audioBuffer;
  }
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
  notifyStatus("idle");
}

function notifyStatus(status) {
  chrome.runtime.sendMessage({
    target: "background",
    type: "STATUS_UPDATE",
    payload: { status, sessionId: activeSessionId },
  });
}
