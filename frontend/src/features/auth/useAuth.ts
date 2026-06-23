import { useCallback, useState } from 'react';

import { login as apiLogin, logout as apiLogout, register as apiRegister } from '../../api/authApi';
import { authStore } from '../../store/authStore';
import type { LoginDto, RegisterDto } from '../../types/auth';

interface UseAuthReturn {
  isLoading: boolean;
  error: string | null;
  handleLogin: (dto: LoginDto) => Promise<void>;
  handleRegister: (dto: RegisterDto) => Promise<void>;
  handleLogout: () => Promise<void>;
}

export const useAuth = (): UseAuthReturn => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLogin = useCallback(async (dto: LoginDto) => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await apiLogin(dto);
      authStore.setTokens(result.accessToken, result.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка входа');
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const handleRegister = useCallback(async (dto: RegisterDto) => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await apiRegister(dto);
      authStore.setTokens(result.accessToken, result.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка регистрации');
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const handleLogout = useCallback(async () => {
    setIsLoading(true);
    try {
      await apiLogout();
    } finally {
      authStore.clear();
      setIsLoading(false);
    }
  }, []);

  return { isLoading, error, handleLogin, handleRegister, handleLogout };
};
