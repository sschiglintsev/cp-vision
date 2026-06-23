export interface AuthUser {
  id: string;
  email: string;
}

export interface LoginDto {
  email: string;
  password: string;
}

export interface RegisterDto {
  email: string;
  password: string;
}

export interface AuthTokensResponse {
  accessToken: string;
  user: AuthUser;
}
