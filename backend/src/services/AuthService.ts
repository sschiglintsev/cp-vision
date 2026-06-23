import bcrypt from 'bcryptjs';

import { userRepository } from '../repositories/UserRepository';
import { signAccessToken, signRefreshToken, verifyRefreshToken } from '../utils/jwt';
import { AppError } from '../utils/AppError';
import { AuthTokensDto, LoginDto, RegisterDto } from '../types/auth';

const SALT_ROUNDS = 12;

export class AuthService {
  async register(dto: RegisterDto): Promise<AuthTokensDto> {
    const existing = await userRepository.findByEmail(dto.email);
    if (existing) {
      throw new AppError('Email already in use', 409);
    }

    const passwordHash = await bcrypt.hash(dto.password, SALT_ROUNDS);
    const user = await userRepository.create({ email: dto.email, passwordHash });

    const payload = { userId: user.id, email: user.email };
    return {
      accessToken: signAccessToken(payload),
      user: { id: user.id, email: user.email },
    };
  }

  async login(dto: LoginDto): Promise<{ tokens: AuthTokensDto; refreshToken: string }> {
    const user = await userRepository.findByEmail(dto.email);
    if (!user) {
      throw new AppError('Invalid credentials', 401);
    }

    const isMatch = await bcrypt.compare(dto.password, user.passwordHash);
    if (!isMatch) {
      throw new AppError('Invalid credentials', 401);
    }

    const payload = { userId: user.id, email: user.email };
    const accessToken = signAccessToken(payload);
    const refreshToken = signRefreshToken(payload);

    return {
      tokens: { accessToken, user: { id: user.id, email: user.email } },
      refreshToken,
    };
  }

  async refresh(
    refreshToken: string,
  ): Promise<{ accessToken: string; refreshToken: string; user: { id: string; email: string } }> {
    let payload: { userId: string; email: string };

    try {
      payload = verifyRefreshToken(refreshToken);
    } catch {
      throw new AppError('Invalid or expired refresh token', 401);
    }

    const user = await userRepository.findById(payload.userId);
    if (!user) {
      throw new AppError('User not found', 401);
    }

    const newPayload = { userId: user.id, email: user.email };
    return {
      accessToken: signAccessToken(newPayload),
      refreshToken: signRefreshToken(newPayload),
      user: { id: user.id, email: user.email },
    };
  }
}

export const authService = new AuthService();
