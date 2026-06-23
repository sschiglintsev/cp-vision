import { Request, Response, NextFunction } from 'express';

import { authService } from '../services/AuthService';
import { sendSuccess } from '../utils/apiResponse';
import { AppError } from '../utils/AppError';
import { env } from '../config/env';

const REFRESH_COOKIE = 'refreshToken';

const refreshCookieOptions = {
  httpOnly: true,
  secure: env.nodeEnv === 'production',
  sameSite: 'strict' as const,
  maxAge: 30 * 24 * 60 * 60 * 1000,
  path: '/api/v1/auth',
};

export class AuthController {
  register = async (req: Request, res: Response, next: NextFunction): Promise<void> => {
    try {
      const result = await authService.register(req.body);
      sendSuccess(res, result, 201);
    } catch (error) {
      next(error);
    }
  };

  login = async (req: Request, res: Response, next: NextFunction): Promise<void> => {
    try {
      const { tokens, refreshToken } = await authService.login(req.body);
      res.cookie(REFRESH_COOKIE, refreshToken, refreshCookieOptions);
      sendSuccess(res, tokens);
    } catch (error) {
      next(error);
    }
  };

  refresh = async (req: Request, res: Response, next: NextFunction): Promise<void> => {
    try {
      const token = req.cookies?.[REFRESH_COOKIE] as string | undefined;
      if (!token) {
        throw new AppError('Refresh token missing', 401);
      }

      const { accessToken, refreshToken, user } = await authService.refresh(token);
      res.cookie(REFRESH_COOKIE, refreshToken, refreshCookieOptions);
      sendSuccess(res, { accessToken, user });
    } catch (error) {
      next(error);
    }
  };

  logout = (_req: Request, res: Response): void => {
    res.clearCookie(REFRESH_COOKIE, { path: '/api/v1/auth' });
    sendSuccess(res, { message: 'Logged out' });
  };
}

export const authController = new AuthController();
