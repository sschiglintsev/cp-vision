export const getApiUrl = (): string => {
  return import.meta.env.VITE_API_URL ?? 'http://localhost:3000';
};

export const getWsUrl = (): string => {
  return import.meta.env.VITE_WS_URL ?? 'http://localhost:3000';
};
