import { Server as HttpServer } from 'http';
import { Server, Socket } from 'socket.io';

import { logger } from '../utils/logger';
import { verifyAccessToken } from '../utils/jwt';
import { cvServiceClient } from '../services/CvServiceClient';

let io: Server | null = null;

export const initSocketServer = (httpServer: HttpServer): Server => {
  io = new Server(httpServer, {
    cors: {
      origin: 'http://localhost:5173',
      methods: ['GET', 'POST'],
      credentials: true,
    },
    maxHttpBufferSize: 5 * 1024 * 1024,
  });

  io.on('connection', (socket: Socket) => {
    const token = socket.handshake.auth?.token as string | undefined;

    if (token) {
      try {
        const payload = verifyAccessToken(token);
        void socket.join(`user:${payload.userId}`);
        logger.info('WebSocket authenticated', { socketId: socket.id, userId: payload.userId });
      } catch {
        logger.info('WebSocket connected without valid token', { socketId: socket.id });
      }
    } else {
      logger.info('WebSocket connected (anonymous)', { socketId: socket.id });
    }

    let isProcessing = false;

    socket.on('camera:frame', async (frameData: string) => {
      if (isProcessing) return;
      isProcessing = true;

      try {
        const base64 = frameData.replace(/^data:image\/\w+;base64,/, '');
        const buffer = Buffer.from(base64, 'base64');
        const result = await cvServiceClient.detectBuffer(buffer, 'frame.jpg', 'image/jpeg');
        socket.emit('detection:frame', { objects: result.objects });
      } catch (error) {
        logger.error('Camera frame detection failed', {
          message: error instanceof Error ? error.message : 'Unknown',
        });
        socket.emit('detection:frame', { objects: [] });
      } finally {
        isProcessing = false;
      }
    });

    socket.on('disconnect', () => {
      logger.info('WebSocket client disconnected', { socketId: socket.id });
    });
  });

  return io;
};

export const getSocketServer = (): Server => {
  if (!io) {
    throw new Error('Socket.IO server is not initialized');
  }
  return io;
};
