import { useEffect, useRef } from 'react';

import type { DetectedObject } from '../../types/detection';

interface CameraOverlayProps {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  objects: DetectedObject[];
}

const COLORS = ['#1677ff', '#52c41a', '#fa8c16', '#f5222d', '#722ed1', '#13c2c2'];

const getColor = (label: string): string => {
  let hash = 0;
  for (let i = 0; i < label.length; i++) {
    hash = label.charCodeAt(i) + ((hash << 5) - hash);
  }
  return COLORS[Math.abs(hash) % COLORS.length];
};

export const CameraOverlay = ({ videoRef, objects }: CameraOverlayProps) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const draw = () => {
    const canvas = canvasRef.current;
    const video = videoRef.current;
    if (!canvas || !video) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const vw = video.videoWidth || video.clientWidth;
    const vh = video.videoHeight || video.clientHeight;

    // Обновляем размер canvas только при изменении — избегаем лишнего сброса контекста
    if (canvas.width !== vw || canvas.height !== vh) {
      canvas.width = vw;
      canvas.height = vh;
    }

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const scaleX = canvas.width / (video.videoWidth || canvas.width);
    const scaleY = canvas.height / (video.videoHeight || canvas.height);

    for (const obj of objects) {
      const x = obj.x * scaleX;
      const y = obj.y * scaleY;
      const w = obj.width * scaleX;
      const h = obj.height * scaleY;
      const color = getColor(obj.class);

      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.strokeRect(x, y, w, h);

      const label = `${obj.class} ${Math.round(obj.confidence * 100)}%`;
      ctx.font = 'bold 13px sans-serif';
      const textWidth = ctx.measureText(label).width;
      const tagH = 20;

      ctx.fillStyle = color;
      ctx.fillRect(x, y - tagH, textWidth + 8, tagH);

      ctx.fillStyle = '#fff';
      ctx.fillText(label, x + 4, y - 5);
    }
  };

  // Перерисовываем при изменении объектов
  useEffect(() => {
    draw();
  }, [objects, videoRef]);

  // Независимый resize listener — перерисовка при изменении размера окна
  useEffect(() => {
    const handleResize = () => draw();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [objects, videoRef]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'absolute',
        inset: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
      }}
    />
  );
};
