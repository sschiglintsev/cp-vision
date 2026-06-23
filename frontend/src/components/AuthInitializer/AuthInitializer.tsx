import { useEffect, useState } from 'react';
import { Flex, Spin } from 'antd';

import { refreshTokens } from '../../api/authApi';
import { authStore } from '../../store/authStore';

interface AuthInitializerProps {
  children: React.ReactNode;
}

export const AuthInitializer = ({ children }: AuthInitializerProps) => {
  const [isChecking, setIsChecking] = useState(true);

  useEffect(() => {
    const restore = async () => {
      try {
        const { accessToken, user } = await refreshTokens();
        authStore.setTokens(accessToken, user);
      } catch {
        // нет cookie или токен истёк — остаёмся на странице входа
      } finally {
        setIsChecking(false);
      }
    };

    restore();
  }, []);

  if (isChecking) {
    return (
      <Flex justify="center" align="center" style={{ minHeight: '100vh' }}>
        <Spin size="large" />
      </Flex>
    );
  }

  return <>{children}</>;
};
