import { Injectable, Logger } from '@nestjs/common';
import type { WebSocket } from 'ws';

// Full port of server/app/broker.py's in-process pub/sub. Single-process
// only — multi-worker deployments need Redis pub/sub fan-out instead (see
// the redis service already in docker-compose.yml, reserved for that).
//
// The Python version needs an asyncio.Lock because awaits can interleave
// mid-operation; Node's single-threaded event loop never interleaves
// between these synchronous Map/Set operations, so no lock is needed here.
//
// Reconnect policy: newer wins. See connect().
@Injectable()
export class BrokerService {
  private readonly logger = new Logger(BrokerService.name);
  private readonly players = new Map<string, WebSocket>();
  private readonly playerRooms = new Map<string, string>();
  private readonly roomMembers = new Map<string, Set<string>>();

  connect(playerId: string, ws: WebSocket, roomId: string): void {
    const existing = this.players.get(playerId);
    const displaced = existing && existing !== ws ? existing : undefined;
    this.players.set(playerId, ws);

    const prevRoom = this.playerRooms.get(playerId);
    if (prevRoom !== undefined && prevRoom !== roomId) {
      this.removeFromRoom(prevRoom, playerId);
    }
    this.playerRooms.set(playerId, roomId);
    this.addToRoom(roomId, playerId);

    if (displaced) {
      try {
        displaced.close(1000, 'Replaced by new connection');
      } catch {
        this.logger.debug('Failed to close displaced socket');
      }
    }
  }

  // Removes the player's socket only if it's still the registered one. If a
  // newer connect() already displaced this socket, this is a no-op so the
  // newer connection's room membership stays intact.
  disconnect(playerId: string, ws: WebSocket): void {
    if (this.players.get(playerId) !== ws) return;
    this.players.delete(playerId);
    const room = this.playerRooms.get(playerId);
    this.playerRooms.delete(playerId);
    if (room !== undefined) {
      this.removeFromRoom(room, playerId);
    }
  }

  connectedPlayerIds(): string[] {
    return [...this.players.keys()];
  }

  move(playerId: string, newRoomId: string): void {
    const oldRoom = this.playerRooms.get(playerId);
    if (oldRoom === newRoomId) return;
    if (oldRoom !== undefined) {
      this.removeFromRoom(oldRoom, playerId);
    }
    this.playerRooms.set(playerId, newRoomId);
    this.addToRoom(newRoomId, playerId);
  }

  publishToRoom(roomId: string, payload: unknown, excludePlayerId?: string): void {
    const members = new Set(this.roomMembers.get(roomId) ?? []);
    if (excludePlayerId !== undefined) members.delete(excludePlayerId);
    const sockets = [...members]
      .map((id) => this.players.get(id))
      .filter((ws): ws is WebSocket => ws !== undefined);
    this.fanOut(sockets, payload);
  }

  publishToAll(payload: unknown): void {
    this.fanOut([...this.players.values()], payload);
  }

  private fanOut(sockets: WebSocket[], payload: unknown): void {
    if (sockets.length === 0) return;
    const text = JSON.stringify(payload);
    for (const ws of sockets) this.safeSend(ws, text);
  }

  private safeSend(ws: WebSocket, text: string): void {
    try {
      ws.send(text);
    } catch {
      this.logger.debug('Broker fan-out send failed; socket likely closed.');
    }
  }

  private addToRoom(roomId: string, playerId: string): void {
    let members = this.roomMembers.get(roomId);
    if (!members) {
      members = new Set();
      this.roomMembers.set(roomId, members);
    }
    members.add(playerId);
  }

  private removeFromRoom(roomId: string, playerId: string): void {
    const members = this.roomMembers.get(roomId);
    if (!members) return;
    members.delete(playerId);
    if (members.size === 0) this.roomMembers.delete(roomId);
  }
}
