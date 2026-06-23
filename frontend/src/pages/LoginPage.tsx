import { useState } from 'react';
import { Alert, Button, Card, Form, Input, Tabs, Typography } from 'antd';
import { useNavigate } from 'react-router-dom';

import { useAuth } from '../features/auth/useAuth';
import type { LoginDto, RegisterDto } from '../types/auth';

const LoginPage = () => {
  const navigate = useNavigate();
  const { isLoading, error, handleLogin, handleRegister } = useAuth();
  const [activeTab, setActiveTab] = useState<'login' | 'register'>('login');

  const onLogin = async (values: LoginDto) => {
    try {
      await handleLogin(values);
      navigate('/camera');
    } catch {
      // error displayed from useAuth
    }
  };

  const onRegister = async (values: RegisterDto & { confirmPassword: string }) => {
    try {
      await handleRegister({ email: values.email, password: values.password });
      navigate('/camera');
    } catch {
      // error displayed from useAuth
    }
  };

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', background: '#f0f2f5' }}>
      <Card style={{ width: 420, boxShadow: '0 2px 12px rgba(0,0,0,0.08)' }}>
        <Typography.Title level={3} style={{ textAlign: 'center', marginBottom: 24 }}>
          Computer Vision Platform
        </Typography.Title>

        <Tabs
          activeKey={activeTab}
          onChange={(key) => setActiveTab(key as 'login' | 'register')}
          centered
          items={[
            {
              key: 'login',
              label: 'Вход',
              children: (
                <Form layout="vertical" onFinish={onLogin} autoComplete="off">
                  <Form.Item
                    label="Email"
                    name="email"
                    rules={[
                      { required: true, message: 'Введите email' },
                      { type: 'email', message: 'Некорректный email' },
                    ]}
                  >
                    <Input placeholder="user@example.com" />
                  </Form.Item>
                  <Form.Item
                    label="Пароль"
                    name="password"
                    rules={[{ required: true, message: 'Введите пароль' }]}
                  >
                    <Input.Password placeholder="••••••••" />
                  </Form.Item>
                  {error && activeTab === 'login' && (
                    <Form.Item>
                      <Alert type="error" message={error} showIcon />
                    </Form.Item>
                  )}
                  <Form.Item>
                    <Button type="primary" htmlType="submit" block loading={isLoading}>
                      Войти
                    </Button>
                  </Form.Item>
                </Form>
              ),
            },
            {
              key: 'register',
              label: 'Регистрация',
              children: (
                <Form layout="vertical" onFinish={onRegister} autoComplete="off">
                  <Form.Item
                    label="Email"
                    name="email"
                    rules={[
                      { required: true, message: 'Введите email' },
                      { type: 'email', message: 'Некорректный email' },
                    ]}
                  >
                    <Input placeholder="user@example.com" />
                  </Form.Item>
                  <Form.Item
                    label="Пароль"
                    name="password"
                    rules={[
                      { required: true, message: 'Введите пароль' },
                      { min: 6, message: 'Минимум 6 символов' },
                    ]}
                  >
                    <Input.Password placeholder="••••••••" />
                  </Form.Item>
                  <Form.Item
                    label="Подтвердите пароль"
                    name="confirmPassword"
                    dependencies={['password']}
                    rules={[
                      { required: true, message: 'Подтвердите пароль' },
                      ({ getFieldValue }) => ({
                        validator(_, value) {
                          if (!value || getFieldValue('password') === value) {
                            return Promise.resolve();
                          }
                          return Promise.reject(new Error('Пароли не совпадают'));
                        },
                      }),
                    ]}
                  >
                    <Input.Password placeholder="••••••••" />
                  </Form.Item>
                  {error && activeTab === 'register' && (
                    <Form.Item>
                      <Alert type="error" message={error} showIcon />
                    </Form.Item>
                  )}
                  <Form.Item>
                    <Button type="primary" htmlType="submit" block loading={isLoading}>
                      Зарегистрироваться
                    </Button>
                  </Form.Item>
                </Form>
              ),
            },
          ]}
        />
      </Card>
    </div>
  );
};

export default LoginPage;
