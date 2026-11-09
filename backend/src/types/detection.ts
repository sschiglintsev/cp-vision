// ---------------------------------------------------------------------------
// Объект распознавания — поля не менять (Frontend зависит от них)
// ---------------------------------------------------------------------------

export interface DetectedObjectDto {
  class: string;
  confidence: number;
  x: number;
  y: number;
  width: number;
  height: number;
}

// ---------------------------------------------------------------------------
// Метаданные источника видеопотока
// ---------------------------------------------------------------------------

export type CameraSourceType = 'browser' | 'usb' | 'rtsp' | 'robot' | 'unknown';

export interface SourceMetadataDto {
  type: CameraSourceType;
  id: string | null;
  name: string | null;
}

// ---------------------------------------------------------------------------
// Метаданные изображения
// ---------------------------------------------------------------------------

export interface ImageMetadataDto {
  width: number;
  height: number;
  format: string;
}

// ---------------------------------------------------------------------------
// Метаданные модели инференса
// ---------------------------------------------------------------------------

export interface ModelMetadataDto {
  id: string;
  name: string;
  type: string;
}

// ---------------------------------------------------------------------------
// Универсальный результат распознавания — ответ CV Service POST /detect
// ---------------------------------------------------------------------------

export interface CvDetectionResult {
  schema_version: string;
  camera_id: string | null;
  source: SourceMetadataDto;
  image: ImageMetadataDto;
  model: ModelMetadataDto;
  objects: DetectedObjectDto[];
  timestamp: number;
}

// ---------------------------------------------------------------------------
// Устаревший тип — оставлен для справки, не используется в новом коде
// ---------------------------------------------------------------------------

/** @deprecated Use CvDetectionResult */
export interface CvDetectionResponse {
  objects: DetectedObjectDto[];
}
