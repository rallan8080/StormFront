import type { ClientMessage, ServerMessage } from '../types/protocol'

const WS_BASE = import.meta.env.VITE_WS_BASE ?? 'ws://localhost:8000'

export type GameSocketOpts = {
  token: string
  onMessage: (msg: ServerMessage) => void
  onOpen?: () => void
  onClose?: (ev: CloseEvent) => void
  onError?: (ev: Event) => void
}

export class GameSocket {
  private ws: WebSocket | null = null

  constructor(private readonly opts: GameSocketOpts) {}

  connect(): void {
    const url = `${WS_BASE}/ws?token=${encodeURIComponent(this.opts.token)}`
    const ws = new WebSocket(url)
    ws.onopen = () => this.opts.onOpen?.()
    ws.onclose = (ev) => this.opts.onClose?.(ev)
    ws.onerror = (ev) => this.opts.onError?.(ev)
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data) as ServerMessage
        this.opts.onMessage(msg)
      } catch {
        // Malformed JSON from the server is a bug worth surfacing later;
        // for now we drop it silently so a single bad frame can't kill the loop.
      }
    }
    this.ws = ws
  }

  send(msg: ClientMessage): boolean {
    if (this.ws?.readyState !== WebSocket.OPEN) return false
    this.ws.send(JSON.stringify(msg))
    return true
  }

  close(): void {
    this.ws?.close()
    this.ws = null
  }
}
