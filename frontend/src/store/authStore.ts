import { AuthUser } from '../types/auth';

interface AuthState {
  accessToken: string | null;
  user: AuthUser | null;
}

const state: AuthState = {
  accessToken: null,
  user: null,
};

export const authStore = {
  getAccessToken: (): string | null => state.accessToken,

  getUser: (): AuthUser | null => state.user,

  isAuthenticated: (): boolean => state.accessToken !== null,

  setTokens: (accessToken: string, user: AuthUser): void => {
    state.accessToken = accessToken;
    state.user = user;
  },

  setAccessToken: (accessToken: string): void => {
    state.accessToken = accessToken;
  },

  clear: (): void => {
    state.accessToken = null;
    state.user = null;
  },
};
