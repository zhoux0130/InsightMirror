import type { FastifyInstance } from 'fastify'
import type { WebApplication as Application } from '@/types'

const HealthSchema = {
  summary: '健康检查',
  tags: ['system'],
  response: {
    200: {
      type: 'object',
      properties: {
        status: { type: 'string' },
        timestamp: { type: 'string' },
        uptime: { type: 'number' },
      },
    },
  },
}

/**
 * 健康检查控制器
 */
export const HealthController = (fastify: FastifyInstance) => {
  const app = fastify as Application

  app.get('/', { schema: HealthSchema }, async (request, reply) => {
    return {
      status: 'ok',
      timestamp: new Date().toISOString(),
      uptime: process.uptime(),
    }
  })
}
