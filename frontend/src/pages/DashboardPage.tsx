import { Button, Card, Layout, Space, Typography } from 'antd';
import { VideoCameraOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';

import { useAuth } from '../features/auth/useAuth';
import { authStore } from '../store/authStore';

const { Header, Content } = Layout;
const { Title, Text, Paragraph } = Typography;

const DashboardPage = () => {
  const navigate = useNavigate();
  const { handleLogout } = useAuth();
  const user = authStore.getUser();

  const onLogout = async () => {
    await handleLogout();
    navigate('/');
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingInline: 24 }}>
        <Title level={4} style={{ color: '#fff', margin: 0 }}>
          Computer Vision Platform
        </Title>
        <Space>
          {user && <Text style={{ color: 'rgba(255,255,255,0.75)' }}>{user.email}</Text>}
          <Button type="default" onClick={onLogout}>
            Выйти
          </Button>
        </Space>
      </Header>
      <Content style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', padding: 24 }}>
        <Card style={{ textAlign: 'center', maxWidth: 480, width: '100%' }}>
          <VideoCameraOutlined style={{ fontSize: 64, color: '#1677ff', marginBottom: 24 }} />
          <Title level={3}>Детекция объектов в реальном времени</Title>
          <Paragraph type="secondary">
            Выберите камеру и запустите детекцию объектов с помощью YOLOv11.
            Результаты отображаются поверх видеопотока в реальном времени.
          </Paragraph>
          <Button
            type="primary"
            size="large"
            icon={<VideoCameraOutlined />}
            onClick={() => navigate('/camera')}
          >
            Открыть камеру
          </Button>
        </Card>
      </Content>
    </Layout>
  );
};

export default DashboardPage;
