/**
 * Subtitle AI - Overlay Manager
 * Injects and manages the non-intrusive subtitle text overlay relative to the active video player.
 */

class SubtitleOverlay {
  constructor() {
    this.container = null;
    this.cueBox = null;
    this.currentSettings = null;
    this.hideTimeout = null;
    this.targetVideo = null;
    this.init();
  }

  async init() {
    this.currentSettings = await getStoredSettings();
    this.createElements();
    this.applySettings(this.currentSettings);

    // Listen for incoming messages from background/offscreen
    chrome.runtime.onMessage.addListener((message) => {
      if (message.target !== "content") return;

      switch (message.type) {
        case "SUBTITLE_CUE":
          this.displayCue(message.payload);
          break;
        case "CLEAR_SUBTITLES":
          this.clear();
          break;
        case "UPDATE_SETTINGS":
          this.applySettings(message.payload);
          break;
      }
    });

    // Listen for storage changes in real-time
    chrome.storage.onChanged.addListener((changes, area) => {
      if (area === "local" && changes.subtitleSettings) {
        this.applySettings(changes.subtitleSettings.newValue);
      }
    });
  }

  createElements() {
    if (this.container) return;

    this.container = document.createElement("div");
    this.container.id = "subtitle-ai-overlay-container";

    this.cueBox = document.createElement("div");
    this.cueBox.className = "subtitle-ai-cue-box";

    this.container.appendChild(this.cueBox);
    document.body.appendChild(this.container);
  }

  attachToVideo(videoElement) {
    if (!videoElement || this.targetVideo === videoElement) return;
    this.targetVideo = videoElement;
    this.reposition();
  }

  reposition() {
    if (!this.container || !this.targetVideo) return;

    // Check if video is in fullscreen
    const fullscreenEl = document.fullscreenElement || document.webkitFullscreenElement;
    if (fullscreenEl && (fullscreenEl.contains(this.targetVideo) || fullscreenEl === this.targetVideo)) {
      if (this.container.parentElement !== fullscreenEl) {
        fullscreenEl.appendChild(this.container);
      }
    } else {
      if (this.container.parentElement !== document.body) {
        document.body.appendChild(this.container);
      }
    }

    const rect = this.targetVideo.getBoundingClientRect();
    const scrollX = window.scrollX || window.pageXOffset;
    const scrollY = window.scrollY || window.pageYOffset;

    if (!fullscreenEl) {
      this.container.style.position = "absolute";
      this.container.style.top = `${rect.top + scrollY}px`;
      this.container.style.left = `${rect.left + scrollX}px`;
      this.container.style.width = `${rect.width}px`;
      this.container.style.height = `${rect.height}px`;
    } else {
      this.container.style.position = "absolute";
      this.container.style.top = "0px";
      this.container.style.left = "0px";
      this.container.style.width = "100%";
      this.container.style.height = "100%";
    }
  }

  displayCue(cue) {
    if (!this.cueBox || !cue.text) return;

    if (this.hideTimeout) {
      clearTimeout(this.hideTimeout);
      this.hideTimeout = null;
    }

    this.cueBox.innerText = cue.text;
    this.cueBox.classList.add("visible");
    if (!cue.final) {
      this.cueBox.classList.add("partial");
    } else {
      this.cueBox.classList.remove("partial");
    }

    // Auto fade after duration
    const displayDurationSec = Math.max(1.5, (cue.end - cue.start) || 3.0);
    this.hideTimeout = setTimeout(() => {
      this.clear();
    }, displayDurationSec * 1000);
  }

  clear() {
    if (this.cueBox) {
      this.cueBox.classList.remove("visible");
      this.cueBox.classList.remove("partial");
    }
    if (this.hideTimeout) {
      clearTimeout(this.hideTimeout);
      this.hideTimeout = null;
    }
  }

  applySettings(settings) {
    if (!settings || !this.cueBox || !this.container) return;
    this.currentSettings = settings;

    // 1. Position
    this.container.className = `position-${settings.position || "bottom"}`;

    // 2. Typography & Colors
    const fontSize = settings.fontSize || 22;
    this.cueBox.style.fontSize = `${fontSize}px`;
    this.cueBox.style.color = settings.textColor || "#ffffff";
    this.cueBox.style.fontFamily = settings.fontFamily || "sans-serif";
    this.cueBox.style.fontWeight = settings.fontWeight || "600";

    // 3. Background box & Opacity
    const hexBg = settings.backgroundColor || "#000000";
    const opacity = settings.backgroundOpacity !== undefined ? settings.backgroundOpacity : 0.75;
    const rgbaBg = hexToRgba(hexBg, opacity);

    this.cueBox.style.backgroundColor = rgbaBg;
    this.cueBox.style.padding = `${settings.padding || 8}px ${((settings.padding || 8) * 1.5)}px`;
    this.cueBox.style.borderRadius = `${settings.borderRadius || 6}px`;
    this.cueBox.style.maxWidth = `${settings.maxWidth || 80}%`;

    // 4. Text Outline
    const outlineType = settings.textOutline || "none";
    this.cueBox.className = `subtitle-ai-cue-box ${this.cueBox.classList.contains("visible") ? "visible" : ""} outline-${outlineType}`;
    this.cueBox.style.setProperty("--sub-outline-color", settings.outlineColor || "#000000");
  }
}

function hexToRgba(hex, opacity) {
  let c = hex.replace("#", "");
  if (c.length === 3) {
    c = c[0] + c[0] + c[1] + c[1] + c[2] + c[2];
  }
  const r = parseInt(c.substring(0, 2), 16) || 0;
  const g = parseInt(c.substring(2, 4), 16) || 0;
  const b = parseInt(c.substring(4, 6), 16) || 0;
  return `rgba(${r}, ${g}, ${b}, ${opacity})`;
}

// Global singleton
window.subtitleOverlay = new SubtitleOverlay();
