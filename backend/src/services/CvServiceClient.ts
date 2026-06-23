import axios from 'axios';
import FormData from 'form-data';

import { env } from '../config/env';
import { logger } from '../utils/logger';
import { AppError } from '../utils/AppError';
import { CvDetectionResponse } from '../types/detection';

export class CvServiceClient {
  async detect(file: Express.Multer.File): Promise<CvDetectionResponse> {
    return this.detectBuffer(file.buffer, file.originalname, file.mimetype);
  }

  async detectBuffer(
    buffer: Buffer,
    filename = 'frame.jpg',
    mimetype = 'image/jpeg',
  ): Promise<CvDetectionResponse> {
    const formData = new FormData();
    formData.append('file', buffer, { filename, contentType: mimetype });

    const url = `${env.cvServiceUrl}/detect`;

    try {
      const response = await axios.post<CvDetectionResponse>(url, formData, {
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
