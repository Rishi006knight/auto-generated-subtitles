/**
 * Subtitle AI - Content Overlay Engine
 * 
 * Production Features:
 * - Fullscreen Trap Solution: Reparents into document.fullscreenElement on fullscreenchange
 * - Chunk-ID in-place update: Seamlessly replaces partial text with final text without reflow flicker
 * - Anti-Flicker Partial Buffering: 150ms debounce for high-frequency partial updates
 * - Dynamic Styles & Presets: Real-time synchronization with user customization
 */

interface SubtitlePayload {
  id: string;
  start: number;
  end: number;
  text: string;
  type: "partial" | "final";
  final?: boolean;
  language?: string;
  confidence?: number;
  estimated_rtt_ms?: number;
}

class SubtitleOverlayManager {
  private container: HTMLDivElement | null = null;
  private cueBox: HTMLDivElement | null = null;
  private currentSettings: any = null;
  private targetVideo: HTMLVideoElement | null = null;
  private hideTimeout: any = null;
  private activeChunkId: string | null = null;

  // Anti-Flicker Buffer
  private pendingPartialText: string | null = null;
  private partialDebounceTimer: any = null;

  constructor() {
    this.init();
  }

  async init() {
    this.currentSettings = await this.loadSettings();
    this.createElements();
    this.applySettings(this.currentSettings);

    // Fullscreen listeners
    document.addEventListener("fullscreenchange", () => this.handleFullscreenChange());
    document.addEventListener("webkitfullscreenchange", () => this.handleFullscreenChange());

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
  }

  private createElements() {
    if (this.container) return;

    this.container = document.createElement("div");
    this.container.id = "subtitle-ai-overlay-container";

    this.cueBox = document.createElement("div");
    this.cueBox.className = "subtitle-ai-cue-box";

    this.container.appendChild(this.cueBox);
    document.body.appendChild(this.container);
  }

  public attachToVideo(videoElement: HTMLVideoElement) {
    if (!videoElement || this.targetVideo === videoElement) return;
    this.targetVideo = videoElement;
    this.reposition();
  }

  public handleFullscreenChange() {
    if (!this.container || !this.targetVideo) return;

    const fullscreenEl = document.fullscreenElement || (document as any).webkitFullscreenElement;
    if (fullscreenEl) {
      // Reparent overlay directly inside the fullscreen container
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
      // Exit fullscreen: return to document.body
      if (this.container.parentElement !== document.body) {
        document.body.appendChild(this.container);
      }
      this.reposition();
    }
  }

  public reposition() {
    if (!this.container || !this.targetVideo) return;

    const fullscreenEl = document.fullscreenElement || (document as any).webkitFullscreenElement;
    if (fullscreenEl) return;

    const rect = this.targetVideo.getBoundingClientRect();
    const scrollX = window.scrollX || window.pageXOffset;
    const scrollY = window.scrollY || window.pageYOffset;

    this.container.style.position = "absolute";
    this.container.style.top = `${rect.top + scrollY}px`;
    this.container.style.left = `${rect.left + scrollX}px`;
    this.container.style.width = `${rect.width}px`;
    this.container.style.height = `${rect.height}px`;
    this.container.style.zIndex = "2147483647";
  }

  public handleIncomingCue(cue: SubtitlePayload) {
    if (!this.cueBox || !cue.text) return;

    const isFinal = cue.type === "final" || cue.final === true;
    const chunkId = cue.id || "default";

    if (isFinal) {
      // Cancel pending partial debounce
      if (this.partialDebounceTimer) {
        clearTimeout(this.partialDebounceTimer);
        this.partialDebounceTimer = null;
      }
      this.activeChunkId = chunkId;
      this.renderText(cue.text, false);

      // Auto clear after end timestamp
      if (this.hideTimeout) clearTimeout(this.hideTimeout);
      const displayDurationSec = Math.max(1.5, (cue.end - cue.start) || 3.5);
      this.hideTimeout = setTimeout(() => {
        if (this.activeChunkId === chunkId) {
          this.clear();
        }
      }, displayDurationSec * 1000);
    } else {
      // Partial update: Anti-flicker 120ms debounce
      this.activeChunkId = chunkId;
      this.pendingPartialText = cue.text;

      if (!this.partialDebounceTimer) {
        this.partialDebounceTimer = setTimeout(() => {
          if (this.pendingPartialText) {
            this.renderText(this.pendingPartialText, true);
          }
          this.partialDebounceTimer = null;
        }, 120);
      }
    }
  }

  private renderText(text: string, isPartial: boolean) {
    if (!this.cueBox) return;

    this.cueBox.innerText = text;
    this.cueBox.classList.add("visible");

    if (isPartial) {
      this.cueBox.classList.add("partial");
    } else {
      this.cueBox.classList.remove("partial");
    }
  }

  public clear() {
    if (this.cueBox) {
      this.cueBox.classList.remove("visible");
      this.cueBox.classList.remove("partial");
    }
    if (this.hideTimeout) {
      clearTimeout(this.hideTimeout);
      this.hideTimeout = null;
    }
    if (this.partialDebounceTimer) {
      clearTimeout(this.partialDebounceTimer);
      this.partialDebounceTimer = null;
    }
    this.activeChunkId = null;
  }

  public applySettings(settings: any) {
    if (!settings || !this.cueBox || !this.container) return;
    this.currentSettings = settings;

    // 1. Position
    this.container.className = `position-${settings.position || "bottom"}`;

    // 2. Typography & Colors
    const fontSize = settings.fontSize || 22;
    this.cueBox.style.fontSize = `${fontSize}px`;
    this.cueBox.style.color = settings.textColor || "#ffffff";
    this.cueBox.style.fontFamily = settings.fontFamily || "sans-serif";
    this.cueBox.style.fontWeight = "600";

    // 3. Background & Opacity
    const hexBg = settings.backgroundColor || "#000000";
    const opacity = settings.backgroundOpacity !== undefined ? settings.backgroundOpacity : 0.75;
    this.cueBox.style.backgroundColor = this.hexToRgba(hexBg, opacity);
    this.cueBox.style.padding = `${settings.padding || 8}px ${(settings.padding || 8) * 1.5}px`;
    this.cueBox.style.borderRadius = `${settings.borderRadius || 6}px`;
    this.cueBox.style.maxWidth = `${settings.maxWidth || 80}%`;

    // 4. Text Outline
    const outlineType = settings.textOutline || "none";
    this.cueBox.className = `subtitle-ai-cue-box ${this.cueBox.classList.contains("visible") ? "visible" : ""} outline-${outlineType}`;
    this.cueBox.style.setProperty("--sub-outline-color", settings.outlineColor || "#000000");
  }

  private hexToRgba(hex: string, opacity: number): string {
    let c = hex.replace("#", "");
    if (c.length === 3) c = c[0] + c[0] + c[1] + c[1] + c[2] + c[2];
    const r = parseInt(c.substring(0, 2), 16) || 0;
    const g = parseInt(c.substring(2, 4), 16) || 0;
    const b = parseInt(c.substring(4, 6), 16) || 0;
    return `rgba(${r}, ${g}, ${b}, ${opacity})`;
  }

  private loadSettings(): Promise<any> {
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

// Global instance
(window as any).subtitleOverlay = new SubtitleOverlayManager();
