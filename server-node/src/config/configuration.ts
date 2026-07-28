// Env-driven settings, mirroring server/app/config.py. Keep the env var
// names identical across both backends so docker-compose can pass the same
// environment block to whichever one is running.
export default () => ({
  port: parseInt(process.env.PORT ?? '8000', 10),

  mongoUrl: process.env.MONGO_URL ?? 'mongodb://localhost:27017',
  mongoDb: process.env.MONGO_DB ?? 'stormfront',

  redisUrl: process.env.REDIS_URL ?? 'redis://localhost:6379/0',

  jwtSecret: process.env.JWT_SECRET ?? 'dev-only-change-me',
  jwtAlgorithm: process.env.JWT_ALGORITHM ?? 'HS256',
  jwtAccessTtlMin: parseInt(process.env.JWT_ACCESS_TTL_MIN ?? '15', 10),
  jwtRefreshTtlDays: parseInt(process.env.JWT_REFRESH_TTL_DAYS ?? '30', 10),

  corsOrigins: JSON.parse(
    process.env.CORS_ORIGINS ?? '["http://localhost:5173"]',
  ) as string[],

  logLevel: process.env.LOG_LEVEL ?? 'info',
});
