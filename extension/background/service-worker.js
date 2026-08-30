/**
 * Subtitle AI - Service Worker
 * Coordinates tab audio capture permissions, offscreen lifecycle, and cross-context messaging.
 */

let state = {
  isCapturing: false,
  activeTabId: null,
  sessionId: null,
  status: "idle", // 'idle' | 'connecting' | 'connected' | 'error'
};

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  // Handle messages from Popup
  if (message.target === "background") {
    switch (message.type) {
      case "GET_STATE":
        sendResponse(state);
        break;

      case "START_CAPTURE":
        handleStartCapture(message.payload)
          .then((res) => sendResponse(res))
          .catch((err) => sendResponse({ success: false, error: err.message }));
        return true;

      case "STOP_CAPTURE":
        handleStopCapture()
          .then(() => sendResponse({ success: true }))
          .catch((err) => sendResponse({ success: false, error: err.message }));
        return true;

      case "STATUS_UPDATE":
        state.status = message.payload.status;
        if (state.status === "idle") {
          state.isCapturing = false;
          state.activeTabId = null;
        }
        break;
    }
  }

  // Handle messages from Offscreen audio capture
  if (message.target === "content" && message.type === "SUBTITLE_CUE") {
    if (message.tabId) {
      chrome.tabs.sendMessage(message.tabId, message).catch(() => {});
    } else if (state.activeTabId) {
      chrome.tabs.sendMessage(state.activeTabId, message).catch(() => {});
    }
  }

  // Handle messages from Content Script (Video Detector Sync)
  if (message.target === "offscreen_sync") {
    chrome.runtime.sendMessage({
      target: "offscreen",
      type: message.type,
      payload: message.payload,
    }).catch(() => {});
  }
});

async function handleStartCapture(options) {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.id) {
    throw new Error("No active tab found");
  }

  const tabId = tab.id;
  const sessionId = "sess_" + Math.random().toString(36).substring(2, 9);

  // 1. Ensure Offscreen Document exists
  await createOffscreenDocument();

  // 2. Obtain Media Stream ID for target tab
  const streamId = await chrome.tabCapture.getMediaStreamId({ targetTabId: tabId });

  // 3. Command Offscreen Document to start capturing & streaming
  state.isCapturing = true;
  state.activeTabId = tabId;
  state.sessionId = sessionId;
  state.status = "connecting";

  chrome.runtime.sendMessage({
    target: "offscreen",
    type: "START_AUDIO_STREAM",
    payload: {
      streamId,
      tabId,
      sessionId,
      wsUrl: options.wsUrl || "ws://127.0.0.1:8000/ws/transcribe",
      language: options.language || "auto",
      model: options.model || "base",
      offset: options.offset || 0.0,
    },
  });

  return { success: true, sessionId, tabId };
}

async function handleStopCapture() {
  state.isCapturing = false;
  state.status = "idle";
  const tabId = state.activeTabId;
  state.activeTabId = null;

  chrome.runtime.sendMessage({
    target: "offscreen",
    type: "STOP_AUDIO_STREAM",
  }).catch(() => {});

  if (tabId) {
    chrome.tabs.sendMessage(tabId, {
      target: "content",
      type: "CLEAR_SUBTITLES",
    }).catch(() => {});
  }

  await closeOffscreenDocument();
}

async function createOffscreenDocument() {
  const offscreenUrl = chrome.runtime.getURL("offscreen/audio-capture.html");
  const existingContexts = await chrome.runtime.getContexts({
    contextTypes: ["OFFSCREEN_DOCUMENT"],
    documentUrls: [offscreenUrl],
  });

  if (existingContexts.length > 0) {
    return;
  }

  await chrome.offscreen.createDocument({
    url: "offscreen/audio-capture.html",
    reasons: ["USER_MEDIA"],
    justification: "Capturing tab audio to process streaming speech-to-text subtitles in real-time.",
  });
}

async function closeOffscreenDocument() {
  const offscreenUrl = chrome.runtime.getURL("offscreen/audio-capture.html");
  const existingContexts = await chrome.runtime.getContexts({
    contextTypes: ["OFFSCREEN_DOCUMENT"],
    documentUrls: [offscreenUrl],
  });

  if (existingContexts.length > 0) {
    await chrome.offscreen.closeDocument();
  }
}

// Clean up if the captured tab is closed
chrome.tabs.onRemoved.addListener((closedTabId) => {
  if (state.activeTabId === closedTabId) {
    handleStopCapture();
  }
});
