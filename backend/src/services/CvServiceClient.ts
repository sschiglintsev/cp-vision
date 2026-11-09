import axios from 'axios';
import FormData from 'form-data';

import { env } from '../config/env';
import { logger } from '../utils/logger';
import { AppError } from '../utils/AppError';
import { CvDetectionResult } from '../types/detection';

export interface DetectBufferOptions {
  filename?: string;
  mimetype?: string;
  cameraId?: string | null;
  sourceType?: string;
  sourceName?: string | null;
}

export class CvServiceClient {
  async detectBuffer(
    buffer: Buffer,
    options: DetectBufferOptions = {},
  ): Promise<CvDetectionResult> {
    const {
      filename = 'frame.jpg',
      mimetype = 'image/jpeg',
      cameraId,
      sourceType,
      sourceName,
    } = options;

    const formData = new FormData();
    formData.append('file', buffer, { filename, contentType: mimetype });

    // Передаём метаданные источника как дополнительные form-поля
    // CV Service ожидает необязательные поля camera_id, source_type, source_name
    if (cameraId) formData.append('camera_id', cameraId);
    if (sourceType) formData.append('source_type', sourceType);
    if (sourceName) formData.append('source_name', sourceName);

    const url = `${env.cvServiceUrl}/detect`;

    try {
      const response = await axios.post<CvDetectionResult>(url, formData, {
        headers: formData.getHeaders(),
        timeout: 10_000,
      });
      return response.data;
    } catch (error) {
      logger.error('CV Service request failed', {
        message: error instanceof Error ? error.message : 'Unknown error',
      });
      throw new AppError('CV Service is unavailable', 502);
    }
  }
}

export const cvServiceClient = new CvServiceClient();
