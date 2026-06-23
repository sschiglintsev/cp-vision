import { NextFunction, Request, Response } from 'express';
import { ZodSchema } from 'zod';

import { sendError } from '../utils/apiResponse';

export const validate =
  (schema: ZodSchema) => (req: Request, res: Response, next: NextFunction): void => {
    const result = schema.safeParse({
      body: req.body,
      query: req.query,
      params: req.params,
    });

    if (!result.success) {
      const message = result.error.errors.map((error) => error.message).join(', ');
      sendError(res, message, 400);
      return;
    }

    next();
  };
