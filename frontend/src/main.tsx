import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { ConfigProvider } from 'antd';
import ruRU from 'antd/locale/ru_RU';

import AppRouter from './router';
import { AuthInitializer } from './components/AuthInitializer/AuthInitializer';

import 'antd/dist/reset.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ConfigProvider locale={ruRU}>
      <AuthInitializer>
        <AppRouter />
      </AuthInitializer>
    </ConfigProvider>
  </StrictMode>,
);
