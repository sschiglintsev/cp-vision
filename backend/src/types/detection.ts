export interface DetectedObjectDto {
  class: string;
  confidence: number;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface CvDetectionResponse {
  objects: DetectedObjectDto[];
}
