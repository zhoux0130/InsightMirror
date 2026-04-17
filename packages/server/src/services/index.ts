import { PrismaService } from './prisma';
import { SessionService } from './session';

export const services = {
  $prisma: PrismaService,
  $session: SessionService,
};
