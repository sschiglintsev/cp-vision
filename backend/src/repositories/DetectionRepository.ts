import { Detection, DetectionResult, DetectionStatus, Prisma } from '@prisma/client';

import { prisma } from '../config/database';

export type DetectionWithResults = Detection & { results: DetectionResult[] };

export class DetectionRepository {
  create(data: Prisma.DetectionCreateInput): Promise<Detection> {
    return prisma.detection.create({ data });
  }

  updateStatus(id: string, status: DetectionStatus): Promise<Detection> {
    return prisma.detection.update({
      where: { id },
      data: { status },
    });
  }

  findByIdWithResults(id: string): Promise<DetectionWithResults | null> {
    return prisma.detection.findUnique({
      where: { id },
      include: { results: true },
    });
  }
}

export const detectionRepository = new DetectionRepository();
