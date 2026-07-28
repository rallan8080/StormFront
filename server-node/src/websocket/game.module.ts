import { Module } from '@nestjs/common';
import { BrokerService } from './broker.service';
import { GameGateway } from './game.gateway';

@Module({
  providers: [BrokerService, GameGateway],
  exports: [BrokerService],
})
export class GameModule {}
