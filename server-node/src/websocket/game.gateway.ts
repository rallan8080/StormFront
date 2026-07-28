import { Logger } from '@nestjs/common';
import { OnGatewayConnection, WebSocketGateway } from '@nestjs/websockets';
import type { WebSocket } from 'ws';
import { BrokerService } from './broker.service';

// Not yet ported. Reference implementation: server/app/routers/websocket.py
// — token auth via query string, server.welcome handshake, command dispatch
// for look/move/say/shout/take/drop/inventory/who/ping, and NPC chatter via
// a scheduler (server/app/npc_scheduler.py). BrokerService above is already
// a working port; this gateway just doesn't use it for anything real yet.
@WebSocketGateway({ path: '/ws' })
export class GameGateway implements OnGatewayConnection {
  private readonly logger = new Logger(GameGateway.name);

  constructor(private readonly broker: BrokerService) {}

  handleConnection(client: WebSocket): void {
    this.logger.debug('connection received; game protocol not yet ported');
    client.send(
      JSON.stringify({
        type: 'server.error',
        data: {
          code: 'UNIMPLEMENTED',
          message: 'Game protocol not yet ported to the Node server.',
        },
      }),
    );
    client.close(1011, 'not implemented');
  }
}
