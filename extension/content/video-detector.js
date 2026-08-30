/**
 * Subtitle AI - Video Detector & Synchronizer
 * Detects HTML5 video players on the page, observes events, and syncs timestamp clocks.
 */

class VideoDetector {
  constructor() {
    this.activeVideo = null;
    this.syncInterval = null;
    this.resizeObserver = null;
    this.init();
  }

  init() {
    this.detectVideos();

    // Observe DOM mutations to catch dynamically loaded players (e.g. YouTube, Netflix)
    const observer = new MutationObserver(() => {
      this.detectVideos();
    });
    observer.observe(document.body, { childList: true, subtree: true });

    // Handle window resize and fullscreen events
    window.addEventListener("resize", () => this.onLayoutChange());
    window.addEventListener("scroll", () => this.onLayoutChange());
    document.addEventListener("fullscreenchange", () => this.onLayoutChange());
  }

  detectVideos() {
    const videos = Array.from(document.querySelectorAll("video"));
    if (videos.length === 0) return;

    // Pick the most likely playing / largest visible video
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

  bindVideo(video) {
    if (this.activeVideo) {
      this.unbindVideo(this.activeVideo);
    }

    this.activeVideo = video;
    console.log("[Subtitle AI] Video element detected and bound:", video);

    if (window.subtitleOverlay) {
      window.subtitleOverlay.attachToVideo(video);
    }

    // Attach event listeners
    video.addEventListener("play", this.onPlay);
    video.addEventListener("pause", this.onPause);
    video.addEventListener("seeking", this.onSeeking);
    video.addEventListener("seeked", this.onSeeked);
    video.addEventListener("timeupdate", this.onTimeUpdate);

    // Watch video resizing
    if (window.ResizeObserver) {
      this.resizeObserver = new ResizeObserver(() => this.onLayoutChange());
      this.resizeObserver.observe(video);
    }

    // Start periodic timestamp sync (every 2 seconds)
    this.startSync();
  }

  unbindVideo(video) {
    video.removeEventListener("play", this.onPlay);
    video.removeEventListener("pause", this.onPause);
    video.removeEventListener("seeking", this.onSeeking);
    video.removeEventListener("seeked", this.onSeeked);
    video.removeEventListener("timeupdate", this.onTimeUpdate);

    if (this.resizeObserver) {
      this.resizeObserver.disconnect();
      this.resizeObserver = null;
    }
    this.stopSync();
  }

  startSync() {
    this.stopSync();
    this.syncInterval = setInterval(() => {
      this.broadcastTimeSync();
    }, 2000);
  }

  stopSync() {
    if (this.syncInterval) {
      clearInterval(this.syncInterval);
      this.syncInterval = null;
    }
  }

  broadcastTimeSync() {
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

  onPlay = () => {
    this.broadcastTimeSync();
    this.startSync();
  };

  onPause = () => {
    this.broadcastTimeSync();
  };

  onSeeking = () => {
    if (window.subtitleOverlay) {
      window.subtitleOverlay.clear();
    }
  };

  onSeeked = () => {
    this.broadcastTimeSync();
  };

  onTimeUpdate = () => {
    // Regular tracking
  };

  onLayoutChange() {
    if (window.subtitleOverlay && this.activeVideo) {
      window.subtitleOverlay.reposition();
    }
  }
}

// Instantiate video detector
window.videoDetector = new VideoDetector();
