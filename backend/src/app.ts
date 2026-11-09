import cookieParser from 'cookie-parser';
import cors from 'cors';
import express from 'express';

import { authRoutes } from './routes/authRoutes';
import { errorHandler } from './middleware/errorHandler';
import { sendSuccess } from './utils/apiResponse';
import { env } from './config/env';

export const createApp = (): express.Application => {
  const app = express();

  app.use(cors({ origin: env.corsOrigin, credentials: true }));
  app.use(express.json());
  app.use(cookieParser());

  app.get('/health', (_req, res) => {
    sendSuccess(res, { status: 'ok' });
  });

  app.use('/api/v1/auth', authRoutes);

  app.use(errorHandler);

  return app;
};
