import { apiClient, unwrapApiResponse } from './client';
import type { AuthTokensResponse, LoginDto, RegisterDto } from '../types/auth';

export const register = async (dto: RegisterDto): Promise<AuthTokensResponse> => {
  const response = await apiClient.post('/api/v1/auth/register', dto);
  return unwrapApiResponse<AuthTokensResponse>(response);
};

export const login = async (dto: LoginDto): Promise<AuthTokensResponse> => {
  const response = await apiClient.post('/api/v1/auth/login', dto);
  return unwrapApiResponse<AuthTokensResponse>(response);
};

export const refreshTokens = async (): Promise<{ accessToken: string; user: { id: string; email: string } }> => {
  const response = await apiClient.post('/api/v1/auth/refresh');
  return unwrapApiResponse<{ accessToken: string; user: { id: string; email: string } }>(response);
};

export const logout = async (): Promise<void> => {
  await apiClient.post('/api/v1/auth/logout');
};
