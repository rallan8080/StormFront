import 'reflect-metadata';
import { ValidationPipe } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { NestFactory } from '@nestjs/core';
import { WsAdapter } from '@nestjs/platform-ws';
import { AppModule } from './app.module';

async function bootstrap(): Promise<void> {
  const app = await NestFactory.create(AppModule);
  const config = app.get(ConfigService);

  app.enableCors({
    origin: config.get<string[]>('corsOrigins'),
    credentials: true,
  });
  app.useGlobalPipes(new ValidationPipe({ whitelist: true, transform: true }));
  // Raw `ws` gateways instead of the socket.io default, to match the plain
  // JSON-over-WebSocket protocol in spec/asyncapi.yaml.
  app.useWebSocketAdapter(new WsAdapter(app));

  const port = config.get<number>('port') ?? 8000;
  await app.listen(port, '0.0.0.0');
}

void bootstrap();
