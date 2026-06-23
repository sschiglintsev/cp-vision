import { NextFunction, Request, Response } from 'express';
import multer from 'multer';

import { AppError } from '../utils/AppError';
import { logger } from '../utils/logger';
import { sendError } from '../utils/apiResponse';

export const errorHandler = (
  err: Error,
  _req: Request,
  res: Response,
  _next: NextFunction,
): void => {
  if (err instanceof AppError) {
    sendError(res, err.message, err.statusCode);
    return;
  }

  if (err instanceof multer.MulterError) {
    sendError(res, err.message, 400);
    return;
  }

  if (err.message === 'Only image files are allowed') {
    sendError(res, err.message, 400);
    return;
  }

  logger.error('Unhandled error', { message: err.message });
  sendError(res, 'Internal server error', 500);
};
