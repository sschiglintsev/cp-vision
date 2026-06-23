import { createServer } from 'http';

import { createApp } from './app';
import { env } from './config/env';
import { prisma } from './config/database';
import { logger } from './utils/logger';
import { initSocketServer } from './websocket/socketEvents';

const start = async (): Promise<void> => {
  const app = createApp();
  const httpServer = createServer(app);

  initSocketServer(httpServer);

  await prisma.$connect();

  httpServer.listen(env.port, () => {
    logger.info(`Backend server started on port ${env.port}`);
  });
};

start().catch((error: Error) => {
  logger.error('Failed to start server', { message: error.message });
  process.exit(1);
});
