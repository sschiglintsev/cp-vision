import { useCallback, useEffect, useRef, useState } from 'react';
import { Socket } from 'socket.io-client';

import type { DetectedObject, ImageMetadata, ModelMetadata, SourceMetadata } from '../types/detection';

const FRAME_INTERVAL_MS = 200;
const STICKY_TTL_MS = 600;

// ---------------------------------------------------------------------------
// detection:frame payload — соответствует backend DetectionFramePayload
// ---------------------------------------------------------------------------
export interface DetectionFramePayload {
  objects: DetectedObject[];
  error?: string | null;
  timestamp?: number;
  // Метаданные Stage 3+ (опциональны — для обратной совместимости)
  cameraId?: string | null;
  source?: SourceMetadata | null;
  image?: ImageMetadata | null;
  model?: ModelMetadata | null;
}

interface UseCameraDetectionReturn {
  objects: DetectedObject[];
  detectionError: string | null;
  fps: number;
  isActive: boolean;
  start: () => void;
  stop: () => void;
}

export const useCameraDetection = (
  socket: Socket | null,
  captureFrame: () => string | null,
  isCameraReady: boolean,
  cameraId?: string | null,
): UseCameraDetectionReturn => {
  const [objects, setObjects] = useState<DetectedObject[]>([]);
  const [detectionError, setDetectionError] = useState<string | null>(null);
  const [fps, setFps] = useState(0);
  const [isActive, setIsActive] = useState(false);

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const fpsTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const stickyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const frameCountRef = useRef(0);

  const clearStickyTimer = () => {
    if (stickyTimerRef.current) {
      clearTimeout(stickyTimerRef.current);
      stickyTimerRef.current = null;
    }
  };

  const stop = useCallback(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (fpsTimerRef.current) clearInterval(fpsTimerRef.current);
    clearStickyTimer();
    intervalRef.current = null;
    fpsTimerRef.current = null;
    setIsActive(false);
    setObjects([]);
    setDetectionError(null);
    frameCountRef.current = 0;
    setFps(0);
  }, []);

  const start = useCallback(() => {
    if (!socket || !isCameraReady) return;

    setIsActive(true);
    setDetectionError(null);

    intervalRef.current = setInterval(() => {
      const frame = captureFrame();
      if (!frame) return;
      // Stage 3: отправляем объект с cameraId для мультикамерной поддержки.
      // Backend обрабатывает как строку (legacy), так и объект (Stage 3+).
      socket.emit('camera:frame', { frame, cameraId: cameraId ?? null });
    }, FRAME_INTERVAL_MS);

    fpsTimerRef.current = setInterval(() => {
      setFps(frameCountRef.current);
      frameCountRef.current = 0;
    }, 1000);
  }, [socket, isCameraReady, captureFrame, cameraId]);

  useEffect(() => {
    if (!socket) return;

    const onFrame = (data: DetectionFramePayload) => {
      // Ошибка обработки кадра — показываем пользователю, не маскируем
      if (data.error) {
        setDetectionError(data.error);
        return;
      }

      // Успешная детекция
      setDetectionError(null);
      frameCountRef.current += 1;

      if (data.objects.length > 0) {
        clearStickyTimer();
        setObjects(data.objects);
      } else {
        // Пустой кадр — sticky TTL, не сбрасываем сразу
        clearStickyTimer();
        stickyTimerRef.current = setTimeout(() => {
          setObjects([]);
        }, STICKY_TTL_MS);
      }
    };

    socket.on('detection:frame', onFrame);
    return () => {
      socket.off('detection:frame', onFrame);
    };
  }, [socket]);

  useEffect(() => {
    if (!isCameraReady && isActive) stop();
  }, [isCameraReady, isActive, stop]);

  useEffect(() => () => stop(), [stop]);

  return { objects, detectionError, fps, isActive, start, stop };
};
