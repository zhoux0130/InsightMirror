import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify'
import type { WebApplication as Application } from '@/types'
import { authMiddleware, optionalAuthMiddleware } from '@/middleware/auth'
import { HealthController } from './controllers/health'
import { SimilarController, PipelineController } from './controllers/similar'
import { StockController } from './controllers/stocks'
import { BasketController } from './controllers/baskets'
import { AuthController } from './controllers/auth'

/**
 * API 路由注册
 */
export const ApiRoutes = async (fastify: FastifyInstance) => {
  const app = fastify as Application

  // 健康检查
  fastify.register(async (app) => HealthController(app), { prefix: '/api/health' })

  // 认证
  fastify.register(async (app) => AuthController(app), { prefix: '/api/auth' })

  // 相似行情查询（可选认证）
  fastify.register(
    async (scoped) => {
      scoped.addHook('preHandler', (req: FastifyRequest, rep: FastifyReply) =>
        optionalAuthMiddleware(req, rep, app)
      )
      SimilarController(scoped)
    },
    { prefix: '/api/similar' }
  )

  // 个股详情（可选认证）
  fastify.register(
    async (scoped) => {
      scoped.addHook('preHandler', (req: FastifyRequest, rep: FastifyReply) =>
        optionalAuthMiddleware(req, rep, app)
      )
      StockController(scoped)
    },
    { prefix: '/api/stocks' }
  )

  // Pipeline 管理
  fastify.register(async (app) => PipelineController(app), { prefix: '/api/pipeline' })

  // 实盘模拟 - 策略篮子（需登录）
  fastify.register(
    async (scoped) => {
      scoped.addHook('preHandler', (req: FastifyRequest, rep: FastifyReply) =>
        authMiddleware(req, rep, app)
      )
      BasketController(scoped)
    },
    { prefix: '/api/baskets' }
  )
}
