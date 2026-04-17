import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify'
import type { WebApplication as Application } from '@/types'
import { authMiddleware } from '@/middleware/auth'
import { HealthController } from './controllers/health'
import { AuthController } from './controllers/auth'
import { PostController } from './controllers/posts'

export const ApiRoutes = async (fastify: FastifyInstance) => {
  const app = fastify as Application

  fastify.register(async (app) => HealthController(app), { prefix: '/api/health' })
  fastify.register(async (app) => AuthController(app), { prefix: '/api/auth' })

  fastify.register(
    async (scoped) => {
      scoped.addHook('preHandler', (req: FastifyRequest, rep: FastifyReply) =>
        authMiddleware(req, rep, app)
      )
      PostController(scoped)
    },
    { prefix: '/api/posts' }
  )
}
