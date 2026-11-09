import { useCallback, useEffect, useRef, useState } from 'react';

export interface CameraDevice {
  deviceId: string;
  label: string;
}

interface UseCameraReturn {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  devices: CameraDevice[];
  activeDeviceId: string | null;
  isReady: boolean;
  error: string | null;
  startCamera: (deviceId?: string) => Promise<void>;
  stopCamera: () => void;
  captureFrame: () => string | null;
  switchCamera: (deviceId: string) => Promise<void>;
}

export const useCamera = (): UseCameraReturn => {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  // Переиспользуемый canvas для захвата кадров — не создаём новый элемент на каждый вызов
  const captureCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const [devices, setDevices] = useState<CameraDevice[]>([]);
  const [activeDeviceId, setActiveDeviceId] = useState<string | null>(null);
  const [isReady, setIsReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadDevices = useCallback(async () => {
    try {
      const allDevices = await navigator.mediaDevices.enumerateDevices();
      const cameras = allDevices
        .filter((d) => d.kind === 'videoinput')
        .map((d, index) => ({
          deviceId: d.deviceId,
          label: d.label || `Камера ${index + 1}`,
        }));
      setDevices(cameras);
    } catch {
      setError('Не удалось получить список камер');
    }
  }, []);

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setIsReady(false);
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  }, []);

  const startCamera = useCallback(
    async (deviceId?: string) => {
      stopCamera();
      setError(null);
      setIsReady(false);

      try {
        const constraints: MediaStreamConstraints = {
          video: deviceId
            ? { deviceId: { exact: deviceId }, width: { ideal: 1280 }, height: { ideal: 720 } }
            : { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } },
          audio: false,
        };

        const stream = await navigator.mediaDevices.getUserMedia(constraints);
        streamRef.current = stream;

        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
        }

        const track = stream.getVideoTracks()[0];
        setActiveDeviceId(track.getSettings().deviceId ?? null);
        setIsReady(true);

        await loadDevices();
      } catch (err) {
        const message =
          err instanceof DOMException && err.name === 'NotAllowedError'
            ? 'Доступ к камере запрещён — разрешите его в настройках браузера'
            : 'Не удалось подключиться к камере';
        setError(message);
      }
    },
    [stopCamera, loadDevices],
  );

  const switchCamera = useCallback(
    async (deviceId: string) => {
      await startCamera(deviceId);
    },
    [startCamera],
  );

  const captureFrame = useCallback((): string | null => {
    const video = videoRef.current;
    if (!video || !isReady || video.readyState < 2) return null;

    // Переиспользуем один canvas — создаём только при первом вызове или смене разрешения
    if (!captureCanvasRef.current) {
      captureCanvasRef.current = document.createElement('canvas');
    }

    const canvas = captureCanvasRef.current;
    if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
    }

    const ctx = canvas.getContext('2d');
    if (!ctx) return null;

    ctx.drawImage(video, 0, 0);
    return canvas.toDataURL('image/jpeg', 0.8);
  }, [isReady]);

  useEffect(() => {
    return () => stopCamera();
  }, [stopCamera]);

  return { videoRef, devices, activeDeviceId, isReady, error, startCamera, stopCamera, captureFrame, switchCamera };
};
