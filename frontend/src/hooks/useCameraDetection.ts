import { useCallback, useEffect, useRef, useState } from 'react';
import { Socket } from 'socket.io-client';

import type { DetectedObject } from '../types/detection';

const FRAME_INTERVAL_MS = 200;
const STICKY_TTL_MS = 600;

interface UseCameraDetectionReturn {
  objects: DetectedObject[];
  fps: number;
  isActive: boolean;
  start: () => void;
  stop: () => void;
}

export const useCameraDetection = (
  socket: Socket | null,
  captureFrame: () => string | null,
  isCameraReady: boolean,
): UseCameraDetectionReturn => {
  const [objects, setObjects] = useState<DetectedObject[]>([]);
  const [fps, setFps] = useState(0);
  const [isActive, setIsActive] = useState(false);

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const fpsTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const stickyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastObjectsRef = useRef<DetectedObject[]>([]);
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
    lastObjectsRef.current = [];
    frameCountRef.current = 0;
    setFps(0);
  }, []);

  const start = useCallback(() => {
    if (!socket || !isCameraReady) return;

    setIsActive(true);

    intervalRef.current = setInterval(() => {
      const frame = captureFrame();
      if (!frame) return;
      socket.emit('camera:frame', frame);
    }, FRAME_INTERVAL_MS);

    fpsTimerRef.current = setInterval(() => {
      setFps(frameCountRef.current);
      frameCountRef.current = 0;
    }, 1000);
  }, [socket, isCameraReady, captureFrame]);

  useEffect(() => {
    if (!socket) return;

    const onFrame = (data: { objects: DetectedObject[] }) => {
      frameCountRef.current += 1;

      if (data.objects.length > 0) {
        clearStickyTimer();
        lastObjectsRef.current = data.objects;
        setObjects(data.objects);
      } else {
        // Пустой кадр — держим последний результат ещё STICKY_TTL_MS
        clearStickyTimer();
        stickyTimerRef.current = setTimeout(() => {
          lastObjectsRef.current = [];
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

  return { objects, fps, isActive, start, stop };
};
