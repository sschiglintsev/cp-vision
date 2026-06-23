import { Prisma } from '@prisma/client';

import { prisma } from '../config/database';
import { DetectedObjectDto } from '../types/detection';

export class DetectionResultRepository {
  createMany(detectionId: string, objects: DetectedObjectDto[]): Promise<Prisma.BatchPayload> {
    return prisma.detectionResult.createMany({
      data: objects.map((object) => ({
        detectionId,
        className: object.class,
        confidence: object.confidence,
        x: object.x,
        y: object.y,
        width: object.width,
        height: object.height,
      })),
    });
  }
}

export const detectionResultRepository = new DetectionResultRepository();
