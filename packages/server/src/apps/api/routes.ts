import type { FastifyInstance } from 'fastify'
import { HealthController } from './controllers/health'
import { SimilarController, PipelineController } from './controllers/similar'
import { StockController } from './controllers/stocks'

/**
 * API 路由注册
 */
export const ApiRoutes = async (fastify: FastifyInstance) => {
  // 健康检查
  fastify.register(async (app) => HealthController(app), { prefix: '/api/health' })

  // 相似行情查询
  fastify.register(async (app) => SimilarController(app), { prefix: '/api/similar' })

  // 个股详情
  fastify.register(async (app) => StockController(app), { prefix: '/api/stocks' })

  // Pipeline 管理
  fastify.register(async (app) => PipelineController(app), { prefix: '/api/pipeline' })
}
