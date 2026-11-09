import dotenv from 'dotenv';

dotenv.config();

const requiredEnvVars = ['DATABASE_URL', 'JWT_SECRET', 'JWT_REFRESH_SECRET', 'CV_SERVICE_URL'] as const;

for (const key of requiredEnvVars) {
  if (!process.env[key]) {
    throw new Error(`Missing required environment variable: ${key}`);
  }
}

export const env = {
  port: Number(process.env.PORT ?? 3000),
  nodeEnv: process.env.NODE_ENV ?? 'development',
  databaseUrl: process.env.DATABASE_URL as string,
  jwtSecret: process.env.JWT_SECRET as string,
  jwtRefreshSecret: process.env.JWT_REFRESH_SECRET as string,
  cvServiceUrl: process.env.CV_SERVICE_URL as string,
  corsOrigin: process.env.CORS_ORIGIN ?? 'http://localhost:5173',
  jwtAccessExpiresIn: '15m',
  jwtRefreshExpiresIn: '30d',
} as const;
