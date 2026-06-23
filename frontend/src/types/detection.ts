export interface DetectedObject {
  class: string;
  confidence: number;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface ApiSuccessResponse<T> {
  success: true;
  data: T;
}
