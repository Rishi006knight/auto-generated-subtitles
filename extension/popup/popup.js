/**
 * Subtitle AI - Popup Controller
 */

document.addEventListener("DOMContentLoaded", async () => {
  // DOM Elements - Controls
  const statusDot = document.getElementById("status-dot");
  const statusText = document.getElementById("status-text");
  const toggleBtn = document.getElementById("toggle-capture-btn");
  const btnIcon = toggleBtn.querySelector(".btn-icon");
  const btnText = toggleBtn.querySelector(".btn-text");
  const langSelect = document.getElementById("language-select");
  const modelSelect = document.getElementById("model-select");
  const wsUrlInput = document.getElementById("ws-url-input");

  // Offset Steppers
  const offsetDisplay = document.getElementById("offset-display");
  const offsetMinus = document.getElementById("offset-minus");
  const offsetPlus = document.getElementById("offset-plus");
  const offsetReset = document.getElementById("offset-reset");

  // DOM Elements - Styling & Customization
  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabContents = document.querySelectorAll(".tab-content");
  const presetBtns = document.querySelectorAll(".preset-btn");
  const previewCue = document.getElementById("preview-cue");
  const fontSizeSlider = document.getElementById("font-size-slider");
  const fontSizeVal = document.getElementById("font-size-val");
  const bgOpacitySlider = document.getElementById("bg-opacity-slider");
  const bgOpacityVal = document.getElementById("bg-opacity-val");
  const textColorPicker = document.getElementById("text-color-picker");
  const colorSwatches = document.querySelectorAll(".color-swatch");
  const outlineSelect = document.getElementById("outline-select");
  const positionSelect = document.getElementById("position-select");
  const fontFamilySelect = document.getElementById("font-family-select");

  let currentSettings = await getStoredSettings();
  let appState = { isCapturing: false, status: "idle" };

  // 1. Tab Switching
  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabBtns.forEach((b) => b.classList.remove("active"));
      tabContents.forEach((c) => c.classList.remove("active"));
      btn.classList.add("active");
      const targetId = btn.getAttribute("data-tab");
      document.getElementById(targetId).classList.add("active");
    });
  });

  // 2. Load & Sync State from Background
  chrome.runtime.sendMessage({ target: "background", type: "GET_STATE" }, (res) => {
    if (res) {
      appState = res;
      updateStatusUI(appState.status, appState.isCapturing);
    }
  });

  // Populate UI with loaded settings
  applySettingsToInputs(currentSettings);
  updateLivePreview(currentSettings);

  // 3. Toggle Start / Stop Capture
  toggleBtn.addEventListener("click", async () => {
    if (appState.isCapturing) {
      // Stop Capture
      chrome.runtime.sendMessage({ target: "background", type: "STOP_CAPTURE" }, () => {
        appState.isCapturing = false;
        updateStatusUI("idle", false);
      });
    } else {
      // Start Capture
      updateStatusUI("connecting", false);
      chrome.runtime.sendMessage(
        {
          target: "background",
          type: "START_CAPTURE",
          payload: {
            wsUrl: wsUrlInput.value,
            language: langSelect.value,
            model: modelSelect.value,
            offset: currentSettings.offset || 0.0,
          },
        },
        (res) => {
          if (res && res.success) {
            appState.isCapturing = true;
            updateStatusUI("connected", true);
          } else {
            updateStatusUI("error", false);
          }
        }
      );
    }
  });

  // 4. Input Change Listeners
  langSelect.addEventListener("change", () => {
    currentSettings.language = langSelect.value;
    saveAndNotify();
  });

  modelSelect.addEventListener("change", () => {
    currentSettings.model = modelSelect.value;
    saveAndNotify();
  });

  wsUrlInput.addEventListener("change", () => {
    currentSettings.wsUrl = wsUrlInput.value;
    saveAndNotify();
  });

  // 5. Offset Steppers
  offsetMinus.addEventListener("click", () => {
    currentSettings.offset = parseFloat((currentSettings.offset - 0.5).toFixed(1));
    updateOffsetDisplay();
    saveAndNotify();
  });

  offsetPlus.addEventListener("click", () => {
    currentSettings.offset = parseFloat((currentSettings.offset + 0.5).toFixed(1));
    updateOffsetDisplay();
    saveAndNotify();
  });

  offsetReset.addEventListener("click", () => {
    currentSettings.offset = 0.0;
    updateOffsetDisplay();
    saveAndNotify();
  });

  function updateOffsetDisplay() {
    const val = currentSettings.offset || 0.0;
    offsetDisplay.textContent = (val > 0 ? `+${val}s` : `${val}s`);
  }

  // 6. Style Presets Selection
  presetBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const presetKey = btn.getAttribute("data-preset");
      presetBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");

      if (PRESETS[presetKey]) {
        currentSettings = { ...currentSettings, ...PRESETS[presetKey], preset: presetKey };
        applySettingsToInputs(currentSettings);
        updateLivePreview(currentSettings);
        saveAndNotify();
      }
    });
  });

  // 7. Custom Styling Sliders & Selects
  fontSizeSlider.addEventListener("input", () => {
    const size = parseInt(fontSizeSlider.value);
    fontSizeVal.textContent = `${size}px`;
    currentSettings.fontSize = size;
    currentSettings.preset = "custom";
    highlightCustomPreset();
    updateLivePreview(currentSettings);
    saveAndNotify();
  });

  bgOpacitySlider.addEventListener("input", () => {
    const pct = parseInt(bgOpacitySlider.value);
    bgOpacityVal.textContent = `${pct}%`;
    currentSettings.backgroundOpacity = pct / 100.0;
    currentSettings.preset = "custom";
    highlightCustomPreset();
    updateLivePreview(currentSettings);
    saveAndNotify();
  });

  textColorPicker.addEventListener("input", () => {
    currentSettings.textColor = textColorPicker.value;
    currentSettings.preset = "custom";
    highlightCustomPreset();
    updateLivePreview(currentSettings);
    saveAndNotify();
  });

  colorSwatches.forEach((swatch) => {
    swatch.addEventListener("click", () => {
      colorSwatches.forEach((s) => s.classList.remove("active"));
      swatch.classList.add("active");
      const color = swatch.getAttribute("data-color");
      textColorPicker.value = color;
      currentSettings.textColor = color;
      currentSettings.preset = "custom";
      highlightCustomPreset();
      updateLivePreview(currentSettings);
      saveAndNotify();
    });
  });

  outlineSelect.addEventListener("change", () => {
    currentSettings.textOutline = outlineSelect.value;
    currentSettings.preset = "custom";
    highlightCustomPreset();
    updateLivePreview(currentSettings);
    saveAndNotify();
  });

  positionSelect.addEventListener("change", () => {
    currentSettings.position = positionSelect.value;
    saveAndNotify();
  });

  fontFamilySelect.addEventListener("change", () => {
    currentSettings.fontFamily = fontFamilySelect.value;
    currentSettings.preset = "custom";
    highlightCustomPreset();
    updateLivePreview(currentSettings);
    saveAndNotify();
  });

  // Helpers
  function highlightCustomPreset() {
    presetBtns.forEach((b) => b.classList.remove("active"));
  }

  function applySettingsToInputs(settings) {
    langSelect.value = settings.language || "auto";
    modelSelect.value = settings.model || "base";
    wsUrlInput.value = settings.wsUrl || "ws://127.0.0.1:8000/ws/transcribe";
    updateOffsetDisplay();

    fontSizeSlider.value = settings.fontSize || 22;
    fontSizeVal.textContent = `${settings.fontSize || 22}px`;

    const opacityPct = Math.round((settings.backgroundOpacity !== undefined ? settings.backgroundOpacity : 0.75) * 100);
    bgOpacitySlider.value = opacityPct;
    bgOpacityVal.textContent = `${opacityPct}%`;

    textColorPicker.value = settings.textColor || "#ffffff";
    outlineSelect.value = settings.textOutline || "none";
    positionSelect.value = settings.position || "bottom";
    fontFamilySelect.value = settings.fontFamily || "sans-serif";

    // Set preset button active
    presetBtns.forEach((b) => {
      if (b.getAttribute("data-preset") === settings.preset) {
        b.classList.add("active");
      } else {
        b.classList.remove("active");
      }
    });
  }

  function updateLivePreview(settings) {
    if (!previewCue) return;
    previewCue.style.fontSize = `${settings.fontSize * 0.75}px`;
    previewCue.style.color = settings.textColor || "#ffffff";
    previewCue.style.fontFamily = settings.fontFamily || "sans-serif";

    const opacity = settings.backgroundOpacity !== undefined ? settings.backgroundOpacity : 0.75;
    const hexBg = settings.backgroundColor || "#000000";
    previewCue.style.backgroundColor = hexToRgba(hexBg, opacity);
    previewCue.style.padding = `${(settings.padding || 8) * 0.7}px ${(settings.padding || 8) * 1.2}px`;
    previewCue.style.borderRadius = `${settings.borderRadius || 6}px`;

    // Outline
    const outline = settings.textOutline || "none";
    if (outline === "none") {
      previewCue.style.textShadow = "none";
    } else if (outline === "thin") {
      previewCue.style.textShadow = "-1px -1px 0 #000, 1px -1px 0 #000, -1px 1px 0 #000, 1px 1px 0 #000";
    } else if (outline === "medium") {
      previewCue.style.textShadow = "-2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000, 2px 2px 0 #000";
    } else if (outline === "thick") {
      previewCue.style.textShadow = "-2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000, 2px 2px 0 #000, 0px 2px 4px #000";
    }
  }

  function updateStatusUI(status, isCapturing) {
    statusDot.className = `status-dot ${status}`;
    if (status === "connected" || isCapturing) {
      statusText.textContent = "Connected & Active";
      toggleBtn.classList.add("capturing");
      btnIcon.textContent = "⏹";
      btnText.textContent = "Stop Subtitles";
    } else if (status === "connecting") {
      statusText.textContent = "Connecting to ASR...";
      toggleBtn.classList.remove("capturing");
      btnIcon.textContent = "⌛";
      btnText.textContent = "Connecting...";
    } else if (status === "error") {
      statusText.textContent = "Connection Error";
      toggleBtn.classList.remove("capturing");
      btnIcon.textContent = "▶";
      btnText.textContent = "Retry Generation";
    } else {
      statusText.textContent = "Ready";
      toggleBtn.classList.remove("capturing");
      btnIcon.textContent = "▶";
      btnText.textContent = "Generate Subtitles";
    }
  }

  async function saveAndNotify() {
    await saveStoredSettings(currentSettings);

    // Notify offscreen document of runtime updates (language, offset, model)
    chrome.runtime.sendMessage({
      target: "offscreen",
      type: "UPDATE_CONFIG",
      payload: {
        language: currentSettings.language,
        model: currentSettings.model,
        offset: currentSettings.offset,
      },
    }).catch(() => {});
  }
});
