/**
 * Subtitle AI - WebSocket Protocol Specification
 * Types & message contracts between Extension and FastAPI ASR Backend.
 */

export type SubtitleCueType = "partial" | "final";

export interface SubtitlePayload {
  id: string;                 // Persistent chunk_id shared across partial and final updates
  start: number;              // Subtitle start timestamp in seconds (synchronized with video.currentTime)
  end: number;                // Subtitle end timestamp in seconds
  text: string;               // Segmented subtitle text (max 2 lines, formatted)
  type: SubtitleCueType;      // 'partial' or 'final'
  language: string;           // Detected or configured language code
  confidence: number;         // Model confidence score (0.0 - 1.0)
  server_timestamp: number;   // Server emission timestamp for latency calibration
  client_video_time: number;  // Original client video reference time
}

export interface ClientConfigMessage {
  type: "config";
  language?: string;
  model?: string;
  offset?: number;
}

export interface ClientSyncMessage {
  type: "sync";
  video_time: number;
  offset?: number;
  client_time: number;
}

export interface ClientPingMessage {
  type: "ping";
  client_time: number;
}

export interface ClientSilenceMessage {
  type: "silence_ping";
  video_time: number;
}

export interface ClientFlushMessage {
  type: "flush";
}

export type ClientWebSocketMessage =
  | ClientConfigMessage
  | ClientSyncMessage
  | ClientPingMessage
  | ClientSilenceMessage
  | ClientFlushMessage;

export interface ServerConnectedMessage {
  type: "connected";
  session_id: string;
  status: "ready";
  model: string;
  device: string;
}

export interface ServerPongMessage {
  type: "pong";
  client_time: number;
  server_time: number;
  rtt_ms: number;
}

export interface ServerConfigAckMessage {
  type: "config_ack";
  language: string;
  model: string;
  offset: number;
}

export type ServerWebSocketMessage =
  | ServerConnectedMessage
  | SubtitlePayload
  | ServerPongMessage
  | ServerConfigAckMessage;
