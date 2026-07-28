import { Injectable, OnModuleDestroy, OnModuleInit } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Db, MongoClient } from 'mongodb';

// Mirrors server/app/db.py: a single Mongo connection held for the process
// lifetime, with the same indexes created up front.
@Injectable()
export class DatabaseService implements OnModuleInit, OnModuleDestroy {
  private client!: MongoClient;
  private _db!: Db;

  constructor(private readonly config: ConfigService) {}

  async onModuleInit(): Promise<void> {
    this.client = new MongoClient(
      this.config.get<string>('mongoUrl', 'mongodb://localhost:27017'),
    );
    await this.client.connect();
    this._db = this.client.db(this.config.get<string>('mongoDb', 'stormfront'));
    await this.ensureIndexes();
  }

  async onModuleDestroy(): Promise<void> {
    await this.client?.close();
  }

  get db(): Db {
    return this._db;
  }

  private async ensureIndexes(): Promise<void> {
    await this._db.collection('accounts').createIndex('email', { unique: true });
    await this._db.collection('players').createIndex('name', {
      unique: true,
      collation: { locale: 'en', strength: 2 },
    });
    await this._db.collection('players').createIndex('accountId');
    await this._db.collection('rooms').createIndex('id', { unique: true });
    await this._db.collection('items').createIndex('id', { unique: true });
    await this._db.collection('npcs').createIndex('id', { unique: true });
  }
}
