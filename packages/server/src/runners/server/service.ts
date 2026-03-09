import fastifyPlugin from 'fastify-plugin'
import type { FastifyInstance } from 'fastify'
import { start } from '@/core/service'
import { services } from '@/services'

/**
 * 服务插件 - 将所有服务注册到 Fastify 实例
 */
export const ServicePlugin = fastifyPlugin(async (fastify: FastifyInstance) => {
  const [app, stopServices] = await start(services)

  // 将所有服务挂载到 fastify 实例
  for (const [key, value] of Object.entries(app)) {
    if (key !== 'stop') {
      (fastify as any)[key] = value
    }
  }

  // 在服务器关闭时停止所有服务
  fastify.addHook('onClose', async () => {
    await stopServices()
  })
})
