import fastifyPlugin from 'fastify-plugin'
import type { FastifyInstance, FastifyError } from 'fastify'
import type { WebApplication as Application } from '@/types'
import { ApiRoutes } from '@/apps/api/routes'

/**
 * 路由插件 - 注册所有路由
 */
export const RouterPlugin = fastifyPlugin(async (fastify: FastifyInstance) => {
  // 注册 API 路由
  await fastify.register(ApiRoutes as any)

  // 404 处理
  fastify.setNotFoundHandler((request, reply) => {
    reply.code(404).send({
      success: false,
      message: '接口不存在',
      path: request.url,
    })
  })

  // 错误处理
  fastify.setErrorHandler((error: FastifyError, request, reply) => {
    fastify.log.error(error, '请求处理错误')

    if (error.validation) {
      reply.code(400).send({
        success: false,
        message: '请求参数验证失败',
        error: 'Validation Error',
        details: error.validation.map((err: any) => ({
          field: err.instancePath || err.params?.missingProperty || 'unknown',
          message: err.message,
          value: err.data,
        })),
      })
      return
    }

    reply.code(error.statusCode || 500).send({
      success: false,
      message: error.message || '服务器内部错误',
      error: process.env.NODE_ENV === 'development' ? error.stack : undefined,
      validation: error.validation,
    })
  })
})
