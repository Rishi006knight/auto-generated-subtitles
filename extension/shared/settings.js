/**
 * Subtitle AI - Shared Settings & Presets
 */

const PRESETS = {
  classic: {
    name: "Classic",
    fontSize: 22,
    textColor: "#ffffff",
    backgroundColor: "#000000",
    backgroundOpacity: 0.0,
    textOutline: "thick",
    outlineColor: "#000000",
    fontFamily: "sans-serif",
    position: "bottom",
    maxWidth: 80,
    padding: 6,
    borderRadius: 4,
  },
  netflix: {
    name: "Netflix-style",
    fontSize: 22,
    textColor: "#ffffff",
    backgroundColor: "#000000",
    backgroundOpacity: 0.75,
    textOutline: "none",
    outlineColor: "#000000",
    fontFamily: "sans-serif",
    position: "bottom",
    maxWidth: 75,
    padding: 10,
    borderRadius: 8,
  },
  highContrast: {
    name: "High Contrast",
    fontSize: 24,
    textColor: "#ffff00", // Yellow
    backgroundColor: "#000000",
    backgroundOpacity: 0.95,
    textOutline: "medium",
    outlineColor: "#000000",
    fontFamily: "sans-serif",
    position: "bottom",
    maxWidth: 85,
    padding: 12,
    borderRadius: 6,
  },
  accessible: {
    name: "Large & Accessible",
    fontSize: 30,
    textColor: "#ffffff",
    backgroundColor: "#000000",
    backgroundOpacity: 0.85,
    textOutline: "thick",
    outlineColor: "#000000",
    fontFamily: "sans-serif",
    position: "above-bottom",
    maxWidth: 90,
    padding: 14,
    borderRadius: 8,
  },
};

const DEFAULT_SETTINGS = {
  preset: "netflix",
  fontSize: 22,
  textColor: "#ffffff",
  backgroundColor: "#000000",
  backgroundOpacity: 0.75,
  textOutline: "none",
  outlineColor: "#000000",
  fontFamily: "sans-serif",
  position: "bottom",
  maxWidth: 80,
  padding: 8,
  borderRadius: 6,
  offset: 0.0,
  language: "auto",
  model: "base",
  wsUrl: "ws://127.0.0.1:8000/ws/transcribe",
};

// Helper to load settings from Chrome Storage with fallback
async function getStoredSettings() {
  return new Promise((resolve) => {
    if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
      chrome.storage.local.get(["subtitleSettings"], (res) => {
        if (res && res.subtitleSettings) {
          resolve({ ...DEFAULT_SETTINGS, ...res.subtitleSettings });
        } else {
          resolve(DEFAULT_SETTINGS);
        }
      });
    } else {
      resolve(DEFAULT_SETTINGS);
    }
  });
}

// Helper to save settings
async function saveStoredSettings(settings) {
  return new Promise((resolve) => {
    if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
      chrome.storage.local.set({ subtitleSettings: settings }, () => resolve(true));
    } else {
      resolve(false);
    }
  });
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { PRESETS, DEFAULT_SETTINGS, getStoredSettings, saveStoredSettings };
}
