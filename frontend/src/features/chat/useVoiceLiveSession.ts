import * as React from "react"

import { getAccessToken } from "@/lib/api/authTokenStore"
import type { ChatLanguage } from "./chatApi"
import type { ConversationTurn, WidgetEntry } from "./useChatSession"

// MIC_SAMPLE_RATE is fixed — Gemini Live always expects 16kHz mono PCM16 mic input.
// PLAYBACK_SAMPLE_RATE is dynamic — the model advertises its output rate via an
// 'audio_config' control frame before the first audio chunk. We default to 24000
// (Gemini Live's documented output rate) but override it from the server message
// so a future model change doesn't silently break playback.
const MIC_SAMPLE_RATE = 16000
const DEFAULT_PLAYBACK_SAMPLE_RATE = 24000

interface VoiceLiveEvent {
  type: "token" | "tool_call" | "tool_result" | "widget" | "error" | "done" | "speaking" | "audio_config" | "interrupted"
  content?: string
  tool?: string
  status?: string
  widget_type?: string
  data?: unknown
  error?: string
  message?: string
  active?: boolean
  sample_rate?: number
}

function createTurnId(): string {
  return crypto.randomUUID()
}

function encodePcm16(float32: Float32Array): ArrayBuffer {
  const buffer = new ArrayBuffer(float32.length * 2)
  const view = new DataView(buffer)
  for (let i = 0; i < float32.length; i++) {
    const clamped = Math.max(-1, Math.min(1, float32[i]))
    view.setInt16(i * 2, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true)
  }
  return buffer
}

/**
 * Real-time duplex voice conversation against the backend's Gemini Live relay
 * (POST /chat/voice/live, a WebSocket). Voice turns are written into the same
 * `setTurns` state text chat uses (ConversationTurn/WidgetEntry), so a voice
 * exchange renders identically to a typed one — same ChatWidgetRenderer, no
 * separate display path.
 */
export function useVoiceLiveSession(
  setTurns: React.Dispatch<React.SetStateAction<ConversationTurn[]>>,
  language: ChatLanguage,
) {
  const [isSessionActive, setIsSessionActive] = React.useState(false)
  const [isConnecting, setIsConnecting] = React.useState(false)
  const [isSpeaking, setIsSpeaking] = React.useState(false)
  const wsRef = React.useRef<WebSocket | null>(null)
  const micContextRef = React.useRef<AudioContext | null>(null)
  const micProcessorRef = React.useRef<ScriptProcessorNode | null>(null)
  const micStreamRef = React.useRef<MediaStream | null>(null)
  const playbackContextRef = React.useRef<AudioContext | null>(null)
  const playbackSampleRateRef = React.useRef<number>(DEFAULT_PLAYBACK_SAMPLE_RATE)
  const playbackCursorRef = React.useRef(0)
  const assistantTurnIdRef = React.useRef<string | null>(null)

  function updateAssistantTurn(turnId: string, updater: (turn: ConversationTurn) => ConversationTurn) {
    setTurns((previous) => previous.map((turn) => (turn.id === turnId ? updater(turn) : turn)))
  }

  function ensureAssistantTurn(): string {
    if (assistantTurnIdRef.current) return assistantTurnIdRef.current
    const turnId = createTurnId()
    assistantTurnIdRef.current = turnId
    setTurns((previous) => [
      ...previous,
      {
        id: turnId,
        role: "assistant",
        content: "",
        toolActivity: [],
        widgets: [],
        suggestions: [],
        isAiUnavailable: false,
        isStreaming: true,
      },
    ])
    return turnId
  }

  function playPcmChunk(bytes: ArrayBuffer) {
    const context = playbackContextRef.current
    if (!context) return
    // Resume the context if the browser suspended it (e.g. tab was backgrounded).
    // This is a no-op when already running and safe to call on every chunk.
    if (context.state === "suspended") {
      void context.resume()
    }
    const int16 = new Int16Array(bytes)
    const float32 = new Float32Array(int16.length)
    for (let i = 0; i < int16.length; i++) float32[i] = int16[i] / 0x8000
    const sampleRate = playbackSampleRateRef.current
    const audioBuffer = context.createBuffer(1, float32.length, sampleRate)
    audioBuffer.copyToChannel(float32, 0)
    const source = context.createBufferSource()
    source.buffer = audioBuffer
    source.connect(context.destination)
    // Queue chunks back-to-back off a running cursor rather than starting each
    // at currentTime — starting at "now" for every chunk would overlap/garble
    // audio the moment network jitter causes chunks to arrive close together.
    const startAt = Math.max(context.currentTime, playbackCursorRef.current)
    source.start(startAt)
    playbackCursorRef.current = startAt + audioBuffer.duration
  }

  function handleServerEvent(parsed: VoiceLiveEvent) {
    if (parsed.type === "done") {
      if (assistantTurnIdRef.current) {
        updateAssistantTurn(assistantTurnIdRef.current, (turn) => ({ ...turn, isStreaming: false }))
      }
      assistantTurnIdRef.current = null
      setIsSpeaking(false)
      return
    }

    if (parsed.type === "speaking") {
      const active = parsed.active ?? false
      setIsSpeaking(active)
      // In audio-only mode the model may never emit text tokens, so we must
      // create the assistant turn here (on first "speaking:true") to ensure
      // the conversation UI advances for every Gemini response.
      if (active) ensureAssistantTurn()
      return
    }

    // Server advertises the PCM sample rate once, before the first audio chunk.
    // On the FIRST audio_config: create the AudioContext at the correct rate.
    // On subsequent audio_config (should not happen — backend no longer resets):
    // do NOT close/recreate — browsers suspend AudioContext created outside a
    // user gesture, which silently drops all audio from turn 2 onwards.
    if (parsed.type === "audio_config" && parsed.sample_rate) {
      const rate = parsed.sample_rate as number
      playbackSampleRateRef.current = rate
      if (!playbackContextRef.current) {
        // First time only — safe because this fires right after first audio
        // arrives, still within the same user-gesture task chain as mic click.
        playbackContextRef.current = new AudioContext({ sampleRate: rate })
      }
      // Always reset the cursor so the new turn's audio starts from "now".
      playbackCursorRef.current = playbackContextRef.current.currentTime
      return
    }

    // Model was interrupted — flush the playback queue so stale audio
    // doesn't play as static after the model resumes.
    if (parsed.type === "interrupted") {
      if (playbackContextRef.current) {
        playbackCursorRef.current = playbackContextRef.current.currentTime
      }
      return
    }

    const turnId = ensureAssistantTurn()
    if (parsed.type === "token" && parsed.content) {
      updateAssistantTurn(turnId, (turn) => ({ ...turn, content: turn.content + parsed.content }))
    } else if (parsed.type === "tool_call" && parsed.tool && parsed.status) {
      updateAssistantTurn(turnId, (turn) => ({
        ...turn,
        toolActivity: [...turn.toolActivity, { tool: parsed.tool!, status: parsed.status! }],
      }))
    } else if (parsed.type === "widget" && parsed.widget_type) {
      const widget: WidgetEntry = { widgetType: parsed.widget_type, data: parsed.data }
      updateAssistantTurn(turnId, (turn) => ({ ...turn, widgets: [...turn.widgets, widget] }))
    } else if (parsed.type === "error") {
      updateAssistantTurn(turnId, (turn) => ({
        ...turn,
        isAiUnavailable: parsed.error === "ai_unavailable",
        content: turn.content || parsed.message || "Something went wrong during the voice session.",
      }))
    }
  }

  function stopVoiceSession() {
    wsRef.current?.close()
    wsRef.current = null
    micProcessorRef.current?.disconnect()
    micProcessorRef.current = null
    micStreamRef.current?.getTracks().forEach((track) => track.stop())
    micStreamRef.current = null
    void micContextRef.current?.close()
    micContextRef.current = null
    void playbackContextRef.current?.close()
    playbackContextRef.current = null
    playbackCursorRef.current = 0
    if (assistantTurnIdRef.current) {
      updateAssistantTurn(assistantTurnIdRef.current, (turn) => ({ ...turn, isStreaming: false }))
    }
    assistantTurnIdRef.current = null
    setIsSessionActive(false)
    setIsConnecting(false)
    setIsSpeaking(false)
  }

  async function startVoiceSession() {
    if (isSessionActive || isConnecting) return
    setIsConnecting(true)

    try {
      const micStream = await navigator.mediaDevices.getUserMedia({ audio: true })
      micStreamRef.current = micStream

      const micContext = new AudioContext({ sampleRate: MIC_SAMPLE_RATE })
      micContextRef.current = micContext
      // NOTE: playbackContextRef is NOT created here — it is created when the
      // backend sends the 'audio_config' event with the model's actual sample rate.
      // Creating it early with a hardcoded rate risks static if the model changes.
      playbackCursorRef.current = 0

      const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:"
      const token = encodeURIComponent(getAccessToken() ?? "")
      const ws = new WebSocket(
        `${wsProtocol}//${window.location.host}/api/v1/chat/voice/live?token=${token}&language=${language}`,
      )
      ws.binaryType = "arraybuffer"
      wsRef.current = ws

      ws.onopen = () => {
        setIsConnecting(false)
        setIsSessionActive(true)

        // ScriptProcessorNode is deprecated in favor of AudioWorklet, but needs
        // no separate worklet-module file to load — the simpler choice while
        // this can't be verified against a live Gemini Live session yet.
        const source = micContext.createMediaStreamSource(micStream)
        const processor = micContext.createScriptProcessor(4096, 1, 1)
        processor.onaudioprocess = (event) => {
          if (ws.readyState !== WebSocket.OPEN) return
          ws.send(encodePcm16(event.inputBuffer.getChannelData(0)))
        }
        source.connect(processor)
        processor.connect(micContext.destination)
        micProcessorRef.current = processor
      }

      ws.onmessage = (event) => {
        if (event.data instanceof ArrayBuffer) {
          playPcmChunk(event.data)
          return
        }
        try {
          handleServerEvent(JSON.parse(event.data as string) as VoiceLiveEvent)
        } catch {
          // Malformed control frame — ignore rather than tear down an otherwise-live session.
        }
      }

      ws.onerror = () => setIsConnecting(false)
      ws.onclose = () => stopVoiceSession()
    } catch {
      stopVoiceSession()
    }
  }

  // Mount/unmount cleanup only — stopVoiceSession closes over refs (stable
  // identity isn't needed), and re-running this on every render's new
  // function reference would tear down and never restart the mic/WS.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  React.useEffect(() => stopVoiceSession, [])

  return { isSessionActive, isConnecting, isSpeaking, startVoiceSession, stopVoiceSession }
}
