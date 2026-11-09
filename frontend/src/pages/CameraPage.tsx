import { useEffect, useRef } from 'react';
import { Alert, Badge, Button, Card, Layout, Select, Space, Tag, Typography } from 'antd';
import { useNavigate } from 'react-router-dom';
import { VideoCameraOutlined, StopOutlined, ArrowLeftOutlined } from '@ant-design/icons';

import { useCamera } from '../hooks/useCamera';
import { useSocket } from '../hooks/useSocket';
import { useCameraDetection } from '../hooks/useCameraDetection';
import { CameraOverlay } from '../components/CameraOverlay/CameraOverlay';
import { authStore } from '../store/authStore';

const { Header, Content } = Layout;
const { Title, Text } = Typography;

const CameraPage = () => {
  const navigate = useNavigate();
  const { socket, connected } = useSocket();
  const { videoRef, devices, activeDeviceId, isReady, error, startCamera, stopCamera, captureFrame, switchCamera } = useCamera();
  // activeDeviceId используется как cameraId для идентификации источника в DetectionResult
  const { objects, detectionError, fps, isActive, start, stop } = useCameraDetection(socket, captureFrame, isReady, activeDeviceId);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const user = authStore.getUser();

  useEffect(() => {
    startCamera();
    return () => stopCamera();
  }, []);

  const handleToggle = () => {
    if (isActive) {
      stop();
    } else {
      start();
    }
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingInline: 24 }}>
        <Space>
          <Button
            type="text"
            icon={<ArrowLeftOutlined />}
            style={{ color: '#fff' }}
            onClick={() => navigate('/dashboard', { replace: true })}
          />
          <Title level={4} style={{ color: '#fff', margin: 0 }}>
            Камера — реальное время
          </Title>
        </Space>
        <Space>
          <Badge status={connected ? 'success' : 'error'} text={
            <Text style={{ color: 'rgba(255,255,255,0.75)' }}>
              {connected ? 'Подключено' : 'Нет соединения'}
            </Text>
          } />
          {user && <Text style={{ color: 'rgba(255,255,255,0.55)' }}>{user.email}</Text>}
        </Space>
      </Header>

      <Content style={{ padding: 24 }}>
        <Card
          title="Детекция объектов"
          extra={
            <Space>
              {isActive && <Tag color="processing">~{fps} fps</Tag>}
              {objects.length > 0 && (
                <Tag color="success">Объектов: {objects.length}</Tag>
              )}
            </Space>
          }
        >
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>

            <Space wrap>
              {devices.length > 1 && (
                <Select
                  value={activeDeviceId ?? undefined}
                  onChange={switchCamera}
                  style={{ minWidth: 200 }}
                  placeholder="Выберите камеру"
                  options={devices.map((d) => ({ value: d.deviceId, label: d.label }))}
                />
              )}
              <Button
                type={isActive ? 'default' : 'primary'}
                danger={isActive}
                icon={isActive ? <StopOutlined /> : <VideoCameraOutlined />}
                onClick={handleToggle}
                disabled={!isReady || !connected}
              >
                {isActive ? 'Остановить' : 'Начать детекцию'}
              </Button>
            </Space>

            {error && <Alert type="error" message={error} showIcon />}

            {detectionError && (
              <Alert type="error" message={`Ошибка детекции: ${detectionError}`} showIcon />
            )}

            {!connected && (
              <Alert type="warning" message="WebSocket не подключён — проверьте, что backend запущен" showIcon />
            )}

            <div
              ref={containerRef}
              style={{
                position: 'relative',
                display: 'inline-block',
                maxWidth: '100%',
                background: '#000',
                borderRadius: 8,
                overflow: 'hidden',
              }}
            >
              <video
                ref={videoRef as React.RefObject<HTMLVideoElement>}
                playsInline
                muted
                style={{ display: 'block', maxWidth: '100%', maxHeight: '70vh' }}
              />
              {isActive && <CameraOverlay videoRef={videoRef} objects={objects} />}
            </div>

            {isActive && objects.length > 0 && (
              <Space wrap>
                {objects.map((obj, i) => (
                  <Tag key={i} color="blue">
                    {obj.class} — {Math.round(obj.confidence * 100)}%
                  </Tag>
                ))}
              </Space>
            )}
          </Space>
        </Card>
      </Content>
    </Layout>
  );
};

export default CameraPage;
