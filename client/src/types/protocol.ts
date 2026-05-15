// WebSocket protocol types mirror the AsyncAPI spec under /spec/asyncapi.yaml.
// Every message on /ws is { "type": "...", "data": { ... } }.

import type { Player } from './api'

export type Direction =
  | 'north' | 'south' | 'east' | 'west'
  | 'northeast' | 'northwest' | 'southeast' | 'southwest'
  | 'up' | 'down'

export type Exit = {
  direction: Direction
  toRoomId: string
  description?: string | null
  locked?: boolean
  keyItemId?: string | null
}

export type Item = {
  id: string
  name: string
  shortDescription: string
  longDescription?: string | null
  takeable?: boolean
  weight?: number
  tags?: string[]
}

export type Npc = {
  id: string
  name: string
  shortDescription: string
  longDescription?: string | null
  homeRoomId: string
  dialogue?: string[]
}

export type RoomView = {
  id: string
  name: string
  description: string
  exits: Exit[]
  items: Item[]
  players: string[]
  npcs: Npc[]
}

// ---- client → server ----

export type ClientPing = { type: 'client.ping' }
export type ClientMove = { type: 'client.command.move'; data: { direction: Direction } }
export type ClientLook = { type: 'client.command.look'; data?: { target?: string } }
export type ClientSay = { type: 'client.command.say'; data: { message: string } }
export type ClientShout = { type: 'client.command.shout'; data: { message: string } }
export type ClientTake = { type: 'client.command.take'; data: { target: string } }
export type ClientDrop = { type: 'client.command.drop'; data: { target: string } }
export type ClientInventory = { type: 'client.command.inventory' }
export type ClientWho = { type: 'client.command.who' }
export type ClientQuit = { type: 'client.command.quit' }

export type ClientMessage =
  | ClientPing
  | ClientMove
  | ClientLook
  | ClientSay
  | ClientShout
  | ClientTake
  | ClientDrop
  | ClientInventory
  | ClientWho
  | ClientQuit

// ---- server → client ----

export type ServerWelcome = {
  type: 'server.welcome'
  data: { player: Player; room: RoomView }
}

export type ServerError = {
  type: 'server.error'
  data: { code: string; message: string }
}

export type ServerRoomEntered = {
  type: 'server.room.entered'
  data: RoomView
}

export type ServerPlayerArrived = {
  type: 'server.player.arrived'
  data: { playerName: string; fromDirection: string }
}

export type ServerPlayerDeparted = {
  type: 'server.player.departed'
  data: { playerName: string; toDirection: string }
}

export type ServerChatSay = {
  type: 'server.chat.say'
  data: { from: string; message: string }
}

export type ServerChatShout = {
  type: 'server.chat.shout'
  data: { from: string; message: string }
}

export type ServerInventoryUpdated = {
  type: 'server.inventory.updated'
  data: { items: Item[] }
}

export type ServerItemTaken = {
  type: 'server.item.taken'
  data: { playerName: string; itemName: string }
}

export type ServerItemDropped = {
  type: 'server.item.dropped'
  data: { playerName: string; itemName: string }
}

export type ServerExamineResult = {
  type: 'server.examine.result'
  data: { name: string; kind: 'item' | 'npc' | 'player'; description: string }
}

export type ServerNpcSpoke = {
  type: 'server.npc.spoke'
  data: { npcName: string; message: string }
}

export type ServerWhoList = {
  type: 'server.who.list'
  data: { players: string[] }
}

export type ServerPong = { type: 'server.pong' }

export type ServerMessage =
  | ServerWelcome
  | ServerError
  | ServerRoomEntered
  | ServerPlayerArrived
  | ServerPlayerDeparted
  | ServerChatSay
  | ServerChatShout
  | ServerInventoryUpdated
  | ServerItemTaken
  | ServerItemDropped
  | ServerExamineResult
  | ServerNpcSpoke
  | ServerWhoList
  | ServerPong
