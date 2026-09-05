/**
 * Subtitle AI - Content Overlay Engine
 * 
 * Features:
 * - Direct, rock-solid bottom positioning over any video player
 * - Fullscreen reparenting for YouTube, Netflix, Twitch, etc.
 * - Dynamic live style & placement updates from popup
 * - Natural subtitle pacing
 */

class SubtitleOverlayManager {
  constructor() {
    this.container = null;
    this.cueBox = null;
    this.bufferToast = null;
    this.currentSettings = null;
    this.targetVideo = null;
    this.hideTimeout = null;
    this.activeChunkId = null;

    this.init();
  }

  async init() {
    this.currentSettings = await this.loadSettings();
    this.createElements();
    this.applySettings(this.currentSettings);

    // Fullscreen listeners
    document.addEventListener("fullscreenchange", () => this.handleFullscreenChange());
    document.addEventListener("webkitfullscreenchange", () => this.handleFullscreenChange());

    // Scroll & Layout tracking
    window.addEventListener("scroll", () => this.reposition(), { passive: true });
    window.addEventListener("resize", () => this.reposition(), { passive: true });

    // Message listeners
    chrome.runtime.onMessage.addListener((message) => {
      if (message.target !== "content") return;

      switch (message.type) {
        case "SUBTITLE_CUE":
          this.handleIncomingCue(message.payload);
          break;
        case "CLEAR_SUBTITLES":
          this.clear();
          break;
        case "UPDATE_SETTINGS":
          this.applySettings(message.payload);
          break;
      }
    });

    // Real-time storage sync
    chrome.storage.onChanged.addListener((changes, area) => {
      if (area === "local" && changes.subtitleSettings) {
        this.applySettings(changes.subtitleSettings.newValue);
      }
    });

    // Continuous soft position tracking
    setInterval(() => {
      if (this.targetVideo && !document.fullscreenElement) {
        this.reposition();
      }
    }, 800);
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

  handleFullscreenChange() {
    if (!this.container || !this.targetVideo) return;

    const fullscreenEl = document.fullscreenElement || document.webkitFullscreenElement;
    if (fullscreenEl) {
      if (this.container.parentElement !== fullscreenEl) {
        fullscreenEl.appendChild(this.container);
      }
      this.container.style.position = "absolute";
      this.container.style.top = "0px";
      this.container.style.left = "0px";
      this.container.style.width = "100%";
      this.container.style.height = "100%";
      this.container.style.zIndex = "2147483647";
    } else {
      if (this.container.parentElement !== document.body) {
        document.body.appendChild(this.container);
      }
      this.reposition();
    }
  }

  reposition() {
    if (!this.container || !this.targetVideo) return;

    const fullscreenEl = document.fullscreenElement || document.webkitFullscreenElement;
    if (fullscreenEl) return;

    const rect = this.targetVideo.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return;

    const scrollX = window.scrollX || window.pageXOffset || 0;
    const scrollY = window.scrollY || window.pageYOffset || 0;

    this.container.style.position = "absolute";
    this.container.style.top = `${Math.round(rect.top + scrollY)}px`;
    this.container.style.left = `${Math.round(rect.left + scrollX)}px`;
    this.container.style.width = `${Math.round(rect.width)}px`;
    this.container.style.height = `${Math.round(rect.height)}px`;
    this.container.style.zIndex = "2147483647";
  }

  handleIncomingCue(cue) {
    if (!this.cueBox || !cue.text) return;

    const chunkId = cue.id || "default";
    this.activeChunkId = chunkId;

    this.renderText(cue.text, false);

    if (this.hideTimeout) clearTimeout(this.hideTimeout);
    const calculatedDuration = Math.max(3.8, (cue.end - cue.start) || 4.0);

    this.hideTimeout = setTimeout(() => {
      if (this.activeChunkId === chunkId) {
        this.clear();
      }
    }, calculatedDuration * 1000);
  }

  renderText(text, isPartial) {
    if (!this.cueBox) return;

    this.cueBox.innerText = text;
    this.cueBox.classList.add("visible");

    if (isPartial) {
      this.cueBox.classList.add("partial");
    } else {
      this.cueBox.classList.remove("partial");
    }
  }

  showBufferingToast() {
    if (!this.bufferToast) {
      this.bufferToast = document.createElement("div");
      this.bufferToast.id = "subtitle-ai-buffering-toast";
      this.bufferToast.innerHTML = `<span class="toast-spinner"></span> Syncing subtitles...`;
      if (this.container) {
        this.container.appendChild(this.bufferToast);
      } else {
        document.body.appendChild(this.bufferToast);
      }
    }
    this.bufferToast.classList.add("visible");
  }

  hideBufferingToast() {
    if (this.bufferToast) {
      this.bufferToast.classList.remove("visible");
    }
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
    this.activeChunkId = null;
  }

  applySettings(settings) {
    if (!settings || !this.cueBox || !this.container) return;
    this.currentSettings = settings;

    const pos = settings.position || "bottom";
    this.container.className = `position-${pos}`;

    // Directly set flex alignment based on position
    if (pos === "bottom") {
      this.container.style.setProperty("justify-content", "flex-end", "important");
      this.container.style.setProperty("padding-bottom", "32px", "important");
      this.container.style.setProperty("padding-top", "0px", "important");
    } else if (pos === "above-bottom") {
      this.container.style.setProperty("justify-content", "flex-end", "important");
      this.container.style.setProperty("padding-bottom", "76px", "important");
      this.container.style.setProperty("padding-top", "0px", "important");
    } else if (pos === "center") {
      this.container.style.setProperty("justify-content", "center", "important");
      this.container.style.setProperty("padding-bottom", "0px", "important");
      this.container.style.setProperty("padding-top", "0px", "important");
    } else if (pos === "top") {
      this.container.style.setProperty("justify-content", "flex-start", "important");
      this.container.style.setProperty("padding-top", "32px", "important");
      this.container.style.setProperty("padding-bottom", "0px", "important");
    }

    const fontSize = settings.fontSize || 22;
    this.cueBox.style.fontSize = `${fontSize}px`;
    this.cueBox.style.color = settings.textColor || "#ffffff";
    this.cueBox.style.fontFamily = settings.fontFamily || "sans-serif";
    this.cueBox.style.fontWeight = "600";

    const hexBg = settings.backgroundColor || "#000000";
    const opacity = settings.backgroundOpacity !== undefined ? settings.backgroundOpacity : 0.75;
    this.cueBox.style.backgroundColor = this.hexToRgba(hexBg, opacity);
    this.cueBox.style.padding = `${settings.padding || 8}px ${(settings.padding || 8) * 1.5}px`;
    this.cueBox.style.borderRadius = `${settings.borderRadius || 6}px`;
    this.cueBox.style.maxWidth = `${settings.maxWidth || 80}%`;

    const outlineType = settings.textOutline || "none";
    this.cueBox.className = `subtitle-ai-cue-box ${this.cueBox.classList.contains("visible") ? "visible" : ""} outline-${outlineType}`;
    this.cueBox.style.setProperty("--sub-outline-color", settings.outlineColor || "#000000");
  }

  hexToRgba(hex, opacity) {
    let c = hex.replace("#", "");
    if (c.length === 3) c = c[0] + c[0] + c[1] + c[1] + c[2] + c[2];
    const r = parseInt(c.substring(0, 2), 16) || 0;
    const g = parseInt(c.substring(2, 4), 16) || 0;
    const b = parseInt(c.substring(4, 6), 16) || 0;
    return `rgba(${r}, ${g}, ${b}, ${opacity})`;
  }

  loadSettings() {
    return new Promise((resolve) => {
      if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
        chrome.storage.local.get(["subtitleSettings"], (res) => {
          resolve(res?.subtitleSettings || {});
        });
      } else {
        resolve({});
      }
    });
  }
}

// Instantiate globally on content script load
if (typeof window !== "undefined") {
  window.subtitleOverlay = new SubtitleOverlayManager();
}
