/**
 * Subtitle AI - Video Detector & Auto-Pause Synchronizer
 * 
 * Features:
 * - Real-time HTML5 video player detection and bounding
 * - Smart Auto-Pause state machine with user override detection
 * - Time sync and latency offset coordination
 */

class VideoDetector {
  private activeVideo: HTMLVideoElement | null = null;
  private syncInterval: any = null;
  private resizeObserver: ResizeObserver | null = null;

  // Smart Auto-Pause State Machine
  private isAutoPaused: boolean = false;
  private userManuallyPaused: boolean = false;
  private autoPauseEnabled: boolean = true;

  constructor() {
    this.init();
  }

  async init() {
    await this.loadAutoPauseSetting();
    this.detectVideos();

    // Observe DOM mutations to bind dynamically loaded videos (YouTube, Netflix, etc.)
    const observer = new MutationObserver(() => {
      this.detectVideos();
    });
    observer.observe(document.body, { childList: true, subtree: true });

    // Handle window resize and fullscreen events
    window.addEventListener("resize", () => this.onLayoutChange());
    window.addEventListener("scroll", () => this.onLayoutChange());
    document.addEventListener("fullscreenchange", () => this.onLayoutChange());

    // Listen for Smart Auto-Pause Control Messages from offscreen document
    chrome.runtime.onMessage.addListener((message) => {
      if (message.target !== "content") return;

      if (message.type === "CONTROL_ACTION") {
        if (message.action === "lag_warning") {
          this.handleLagWarning();
        } else if (message.action === "lag_clear") {
          this.handleLagClear();
        }
      }
    });

    // Listen for setting changes
    chrome.storage.onChanged.addListener((changes, area) => {
      if (area === "local" && changes.subtitleSettings) {
        this.autoPauseEnabled = changes.subtitleSettings.newValue?.autoPauseEnabled ?? true;
      }
    });
  }

  private async loadAutoPauseSetting() {
    if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
      chrome.storage.local.get(["subtitleSettings"], (res) => {
        this.autoPauseEnabled = res?.subtitleSettings?.autoPauseEnabled ?? true;
      });
    }
  }

  private handleLagWarning() {
    if (!this.autoPauseEnabled || !this.activeVideo) return;

    if (!this.activeVideo.paused) {
      console.log("[Subtitle AI] ASR lag warning received. Auto-pausing video to prevent subtitle desync.");
      this.isAutoPaused = true;
      this.userManuallyPaused = false;
      this.activeVideo.pause();

      if ((window as any).subtitleOverlay) {
        (window as any).subtitleOverlay.showBufferingToast();
      }
    }
  }

  private handleLagClear() {
    if (!this.activeVideo) return;

    if (this.isAutoPaused && this.activeVideo.paused && !this.userManuallyPaused) {
      console.log("[Subtitle AI] ASR queue cleared. Auto-resuming video playback.");
      this.isAutoPaused = false;
      this.activeVideo.play().catch((err) => console.warn("Auto-resume play prevented:", err));

      if ((window as any).subtitleOverlay) {
        (window as any).subtitleOverlay.hideBufferingToast();
      }
    }
  }

  private detectVideos() {
    const videos = Array.from(document.querySelectorAll("video"));
    if (videos.length === 0) return;

    let selectedVideo = videos[0];
    for (const v of videos) {
      if (!v.paused && v.currentTime > 0) {
        selectedVideo = v;
        break;
      }
      const rect = v.getBoundingClientRect();
      const selRect = selectedVideo.getBoundingClientRect();
      if (rect.width * rect.height > selRect.width * selRect.height) {
        selectedVideo = v;
      }
    }

    if (selectedVideo && selectedVideo !== this.activeVideo) {
      this.bindVideo(selectedVideo);
    }
  }

  private bindVideo(video: HTMLVideoElement) {
    if (this.activeVideo) {
      this.unbindVideo(this.activeVideo);
    }

    this.activeVideo = video;
    console.log("[Subtitle AI] Video element bound:", video);

    if ((window as any).subtitleOverlay) {
      (window as any).subtitleOverlay.attachToVideo(video);
    }

    // Attach user interaction listeners
    video.addEventListener("play", this.onPlay);
    video.addEventListener("pause", this.onPause);
    video.addEventListener("seeking", this.onSeeking);
    video.addEventListener("seeked", this.onSeeked);

    if (window.ResizeObserver) {
      this.resizeObserver = new ResizeObserver(() => this.onLayoutChange());
      this.resizeObserver.observe(video);
    }

    this.startSync();
  }

  private unbindVideo(video: HTMLVideoElement) {
    video.removeEventListener("play", this.onPlay);
    video.removeEventListener("pause", this.onPause);
    video.removeEventListener("seeking", this.onSeeking);
    video.removeEventListener("seeked", this.onSeeked);

    if (this.resizeObserver) {
      this.resizeObserver.disconnect();
      this.resizeObserver = null;
    }
    this.stopSync();
  }

  private startSync() {
    this.stopSync();
    this.syncInterval = setInterval(() => {
      this.broadcastTimeSync();
    }, 2000);
  }

  private stopSync() {
    if (this.syncInterval) {
      clearInterval(this.syncInterval);
      this.syncInterval = null;
    }
  }

  private broadcastTimeSync() {
    if (!this.activeVideo) return;
    chrome.runtime.sendMessage({
      target: "offscreen_sync",
      type: "SYNC_TIME",
      payload: {
        videoTime: this.activeVideo.currentTime,
        paused: this.activeVideo.paused,
      },
    }).catch(() => {});
  }

  private onPlay = () => {
    // If user clicked play while auto-paused, respect user intent and cancel auto-pause state
    if (this.isAutoPaused) {
      console.log("[Subtitle AI] User clicked play during auto-pause. Resetting auto-pause state.");
      this.isAutoPaused = false;
      this.userManuallyPaused = false;
      if ((window as any).subtitleOverlay) {
        (window as any).subtitleOverlay.hideBufferingToast();
      }
    }
    this.broadcastTimeSync();
    this.startSync();
  };

  private onPause = () => {
    // If pause event fired and it wasn't triggered by our code, mark user as having manually paused
    if (!this.isAutoPaused) {
      this.userManuallyPaused = true;
    }
    this.broadcastTimeSync();
  };

  private onSeeking = () => {
    if ((window as any).subtitleOverlay) {
      (window as any).subtitleOverlay.clear();
    }
  };

  private onSeeked = () => {
    this.broadcastTimeSync();
  };

  private onLayoutChange() {
    if ((window as any).subtitleOverlay && this.activeVideo) {
      (window as any).subtitleOverlay.reposition();
    }
  }
}

(window as any).videoDetector = new VideoDetector();
