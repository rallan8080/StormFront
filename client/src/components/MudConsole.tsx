import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'

export type ConsoleLineKind =
  | 'system'      // status from the client itself
  | 'self'        // echo of the command the user just typed
  | 'narration'   // server-driven world events (room view, arrival/departure)
  | 'chat'        // say / shout / NPC dialogue
  | 'error'       // server.error frames or client-side parse failures

export type ConsoleLine = {
  id: number
  kind: ConsoleLineKind
  text: string
}

type Props = {
  lines: ConsoleLine[]
  onSend: (line: string) => void
  connected: boolean
  status?: string
}

const KIND_CLASS: Record<ConsoleLineKind, string> = {
  system: 'text-zinc-500',
  self: 'text-emerald-400',
  narration: 'text-amber-100',
  chat: 'text-sky-300',
  error: 'text-rose-400',
}

export default function MudConsole({ lines, onSend, connected, status }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [input, setInput] = useState('')

  // Auto-scroll on new lines.
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [lines.length])

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const trimmed = input.trim()
    if (!trimmed) return
    onSend(trimmed)
    setInput('')
  }

  return (
    <div className="flex h-full flex-col bg-zinc-950 text-sm">
      <header className="flex items-center justify-between border-b border-zinc-800 px-4 py-2 text-xs text-zinc-500">
        <span>StormFront</span>
        <span>
          <span
            className={`inline-block h-2 w-2 rounded-full mr-2 ${
              connected ? 'bg-emerald-500' : 'bg-rose-500'
            }`}
          />
          {status ?? (connected ? 'connected' : 'disconnected')}
        </span>
      </header>

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-4 py-3 space-y-1 leading-relaxed"
      >
        {lines.map((line) => (
          <div
            key={line.id}
            className={`whitespace-pre-wrap break-words ${KIND_CLASS[line.kind]}`}
          >
            {line.text}
          </div>
        ))}
      </div>

      <form
        onSubmit={submit}
        className="border-t border-zinc-800 px-4 py-2"
      >
        <div className="flex items-center gap-2">
          <span className="text-emerald-500">{connected ? '>' : '×'}</span>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={!connected}
            placeholder={
              connected
                ? 'look · north · take rusty key · say hello · who · inventory'
                : 'disconnected'
            }
            className="flex-1 bg-transparent text-zinc-100 outline-none placeholder-zinc-600 disabled:opacity-50"
            autoFocus
            autoComplete="off"
            spellCheck={false}
          />
        </div>
      </form>
    </div>
  )
}
