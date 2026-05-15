import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { GameSocket } from '../api/ws'
import { useAuth } from '../auth/AuthContext'
import MudConsole from '../components/MudConsole'
import type { ConsoleLine } from '../components/MudConsole'
import type {
  ClientMessage,
  Direction,
  RoomView,
  ServerMessage,
} from '../types/protocol'

// ---- text formatting helpers ----

function formatRoom(room: RoomView): string {
  const parts: string[] = [`${room.name}`, room.description]
  if (room.exits.length > 0) {
    parts.push(`Exits: ${room.exits.map((e) => e.direction).join(', ')}`)
  } else {
    parts.push('Exits: none')
  }
  if (room.items.length > 0) {
    parts.push(`You see: ${room.items.map((i) => i.name).join(', ')}`)
  }
  if (room.npcs.length > 0) {
    parts.push(`Also here: ${room.npcs.map((n) => n.name).join(', ')}`)
  }
  if (room.players.length > 0) {
    parts.push(`Players: ${room.players.join(', ')}`)
  }
  return parts.join('\n')
}

// ---- input parser: free-text → ClientMessage ----

const DIRECTION_ALIASES: Record<string, Direction> = {
  n: 'north', north: 'north',
  s: 'south', south: 'south',
  e: 'east', east: 'east',
  w: 'west', west: 'west',
  ne: 'northeast', northeast: 'northeast',
  nw: 'northwest', northwest: 'northwest',
  se: 'southeast', southeast: 'southeast',
  sw: 'southwest', southwest: 'southwest',
  u: 'up', up: 'up',
  d: 'down', down: 'down',
}

function parseCommand(raw: string): ClientMessage | { error: string } {
  const trimmed = raw.trim()
  if (!trimmed) return { error: 'empty input' }

  const spaceIdx = trimmed.indexOf(' ')
  const head = (spaceIdx === -1 ? trimmed : trimmed.slice(0, spaceIdx)).toLowerCase()
  const args = spaceIdx === -1 ? '' : trimmed.slice(spaceIdx + 1).trim()

  if (head in DIRECTION_ALIASES) {
    return { type: 'client.command.move', data: { direction: DIRECTION_ALIASES[head] } }
  }

  switch (head) {
    case 'look':
    case 'l':
      return args
        ? { type: 'client.command.look', data: { target: args } }
        : { type: 'client.command.look' }
    case 'say':
      return args
        ? { type: 'client.command.say', data: { message: args } }
        : { error: "usage: say <message>" }
    case 'shout':
    case 'yell':
      return args
        ? { type: 'client.command.shout', data: { message: args } }
        : { error: "usage: shout <message>" }
    case 'take':
    case 'get':
      return args
        ? { type: 'client.command.take', data: { target: args } }
        : { error: "usage: take <item>" }
    case 'drop':
      return args
        ? { type: 'client.command.drop', data: { target: args } }
        : { error: "usage: drop <item>" }
    case 'inventory':
    case 'inv':
    case 'i':
      return { type: 'client.command.inventory' }
    case 'who':
      return { type: 'client.command.who' }
    case 'quit':
    case 'exit':
    case 'q':
      return { type: 'client.command.quit' }
    case 'help':
    case '?':
      return { error: 'commands: look [target], n/s/e/w/ne/nw/se/sw/up/down, take <x>, drop <x>, inventory, who, say <msg>, shout <msg>, quit' }
    default:
      return { error: `unknown command: ${head} (try 'help')` }
  }
}

// ---- component ----

export default function Game() {
  const { token, clear } = useAuth()
  const navigate = useNavigate()

  const [lines, setLines] = useState<ConsoleLine[]>([])
  const [connected, setConnected] = useState(false)
  const [status, setStatus] = useState('connecting…')

  const socketRef = useRef<GameSocket | null>(null)
  const lineIdRef = useRef(0)
  // Set when the user types quit/exit. Tells onClose to navigate back to
  // the character screen instead of rendering a "Disconnected" line.
  const quittingRef = useRef(false)

  const append = useCallback((kind: ConsoleLine['kind'], text: string) => {
    setLines((prev) => [
      ...prev,
      { id: ++lineIdRef.current, kind, text },
    ])
  }, [])

  const handleServer = useCallback(
    (msg: ServerMessage) => {
      switch (msg.type) {
        case 'server.welcome':
          append('system', `Welcome, ${msg.data.player.name}.`)
          append('narration', formatRoom(msg.data.room))
          return
        case 'server.room.entered':
          append('narration', formatRoom(msg.data))
          return
        case 'server.player.arrived':
          append('narration', `${msg.data.playerName} arrives from the ${msg.data.fromDirection}.`)
          return
        case 'server.player.departed':
          append('narration', `${msg.data.playerName} leaves to the ${msg.data.toDirection}.`)
          return
        case 'server.chat.say':
          append('chat', `${msg.data.from} says, "${msg.data.message}"`)
          return
        case 'server.chat.shout':
          append('chat', `${msg.data.from} shouts, "${msg.data.message}"`)
          return
        case 'server.npc.spoke':
          append('chat', `${msg.data.npcName}: ${msg.data.message}`)
          return
        case 'server.inventory.updated': {
          const names = msg.data.items.map((i) => i.name)
          append('narration', names.length
            ? `Inventory: ${names.join(', ')}`
            : 'Your inventory is empty.')
          return
        }
        case 'server.item.taken':
          append('narration', `${msg.data.playerName} picks up the ${msg.data.itemName}.`)
          return
        case 'server.item.dropped':
          append('narration', `${msg.data.playerName} drops the ${msg.data.itemName}.`)
          return
        case 'server.examine.result':
          append('narration', `${msg.data.name} — ${msg.data.description}`)
          return
        case 'server.who.list': {
          const list = msg.data.players
          append(
            'narration',
            list.length
              ? `Online (${list.length}): ${list.join(', ')}`
              : 'No one is online.',
          )
          return
        }
        case 'server.error':
          append('error', `[${msg.data.code}] ${msg.data.message}`)
          return
        case 'server.pong':
          // Quiet by design — keep-alive only.
          return
      }
    },
    [append],
  )

  // Open the WebSocket once.
  //
  // React StrictMode mounts effects twice in development, so the first
  // socket gets close()d while still in CONNECTING state (browser fires
  // a 1006 onclose). The `active` flag suppresses callbacks from that
  // throwaway socket so the UI doesn't show a phantom disconnect.
  useEffect(() => {
    if (!token) return

    let active = true

    const socket = new GameSocket({
      token,
      onMessage: (msg) => {
        if (!active) return
        handleServer(msg)
      },
      onOpen: () => {
        if (!active) return
        setConnected(true)
        setStatus('connected')
      },
      onClose: (ev) => {
        if (!active) return
        setConnected(false)
        if (quittingRef.current) {
          // User-initiated quit; route back to character select silently.
          navigate('/characters', { replace: true })
          return
        }
        if (ev.code === 1008) {
          setStatus('auth rejected')
          append('error', 'Authentication rejected. Please sign in again.')
          clear()
          navigate('/', { replace: true })
        } else {
          setStatus(`disconnected (${ev.code})`)
          append('system', `Disconnected (code ${ev.code}).`)
        }
      },
      onError: () => {
        if (!active) return
        setStatus('connection error')
      },
    })

    socketRef.current = socket
    socket.connect()

    return () => {
      active = false
      socket.close()
      socketRef.current = null
    }
  }, [token, handleServer, append, clear, navigate])

  const send = useCallback(
    (raw: string) => {
      append('self', `> ${raw}`)
      const parsed = parseCommand(raw)
      if ('error' in parsed) {
        append('error', parsed.error)
        return
      }
      if (parsed.type === 'client.command.quit') {
        quittingRef.current = true
      }
      const ok = socketRef.current?.send(parsed)
      if (!ok) append('error', 'Not connected.')
    },
    [append],
  )

  // Memoize lines so the console only re-renders when content changes.
  const renderedLines = useMemo(() => lines, [lines])

  return (
    <div className="h-full">
      <MudConsole
        lines={renderedLines}
        onSend={send}
        connected={connected}
        status={status}
      />
    </div>
  )
}
