import { Server as HttpServer } from 'http';
import { Server, Socket } from 'socket.io';

import { env } from '../config/env';
import { logger } from '../utils/logger';
import { verifyAccessToken } from '../utils/jwt';
import { cvServiceClient } from '../services/CvServiceClient';
import {
  DetectedObjectDto,
  ImageMetadataDto,
  ModelMetadataDto,
  SourceMetadataDto,
} from '../types/detection';

// ---------------------------------------------------------------------------
// camera:frame — принимает строку (legacy) или объект с метаданными (Stage 3+)
// ---------------------------------------------------------------------------
type CameraFramePayload =
  | string
  | { frame: string; cameraId?: string | null };

// ---------------------------------------------------------------------------
// detection:frame — расширенный payload с метаданными
// ---------------------------------------------------------------------------
export interface DetectionFramePayload {
  // Результат распознавания
  objects: DetectedObjectDto[];
  error: string | null;
  timestamp: number;
  // Метаданные источника и модели (опциональны при ошибке)
  cameraId?: string | null;
  source?: SourceMetadataDto | null;
  image?: ImageMetadataDto | null;
  model?: ModelMetadataDto | null;
}

let io: Server | null = null;

export const initSocketServer = (httpServer: HttpServer): Server => {
  io = new Server(httpServer, {
    cors: {
      origin: env.corsOrigin,
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

    // Флаг per-socket — ошибка одного пользователя не влияет на другого
    let isProcessing = false;

    socket.on('camera:frame', async (raw: CameraFramePayload) => {
      if (isProcessing) return;
      isProcessing = true;

      // Поддержка legacy-формата (строка) и нового формата (объект)
      const frameData = typeof raw === 'string' ? raw : raw.frame;
      const cameraId = typeof raw === 'string' ? null : (raw.cameraId ?? null);

      try {
        const base64 = frameData.replace(/^data:image\/\w+;base64,/, '');
        const buffer = Buffer.from(base64, 'base64');

        const result = await cvServiceClient.detectBuffer(buffer, {
          filename: 'frame.jpg',
          mimetype: 'image/jpeg',
          cameraId,
          sourceType: 'browser',
        });

        const payload: DetectionFramePayload = {
          objects: result.objects,
          error: null,
          timestamp: result.timestamp,
          cameraId: result.camera_id,
          source: result.source,
          image: result.image,
          model: result.model,
        };

        socket.emit('detection:frame', payload);
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Detection failed';
        logger.error('Camera frame detection failed', { message, socketId: socket.id, cameraId });

        const payload: DetectionFramePayload = {
          objects: [],
          error: message,
          timestamp: Date.now(),
          cameraId,
        };

        socket.emit('detection:frame', payload);
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
