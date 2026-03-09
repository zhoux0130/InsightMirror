import { PrismaService } from './prisma';
import { SessionService } from './session';
import { PgVectorServiceFactory } from './pgvector';

export const services = {
  $prisma: PrismaService,
  $session: SessionService,
  $pgvector: PgVectorServiceFactory,
};
