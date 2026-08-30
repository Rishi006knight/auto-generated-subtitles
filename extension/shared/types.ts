/**
 * Subtitle AI - Shared Types & Settings Interfaces
 */

export type SubtitlePreset = "netflix" | "classic" | "highContrast" | "accessible" | "custom";
export type TextOutlineType = "none" | "thin" | "medium" | "thick";
export type SubtitlePosition = "bottom" | "above-bottom" | "center" | "top";
export type FontFamilyType = "sans-serif" | "serif" | "monospace";

export interface SubtitleStyleSettings {
  preset: SubtitlePreset;
  fontSize: number;          // 14 - 40 px
  textColor: string;         // hex / rgba
  backgroundColor: string;   // hex
  backgroundOpacity: number; // 0.0 - 1.0
  textOutline: TextOutlineType;
  outlineColor: string;
  fontFamily: FontFamilyType;
  position: SubtitlePosition;
  maxWidth: number;          // percentage (50% - 95%)
  padding: number;           // px
  borderRadius: number;      // px
  offset: number;            // seconds calibration (-5.0 to +5.0)
  language: string;          // 'auto', 'en', 'es', etc.
  model: string;             // 'tiny', 'base', 'small'
  wsUrl: string;
}

export interface ExtensionState {
  isCapturing: boolean;
  activeTabId: number | null;
  sessionId: string | null;
  status: "idle" | "connecting" | "connected" | "error";
  latencyMs: number;
}
