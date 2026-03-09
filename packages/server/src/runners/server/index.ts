import fastify from 'fastify'
import fastifyCors from '@fastify/cors'
import fastifyCookie from '@fastify/cookie'
import fastifyMultipart from '@fastify/multipart'
import fastifySwagger from '@fastify/swagger'
import fastifySwaggerUI from '@fastify/swagger-ui'
import { web as config } from '@/config'
import { swaggerConfig, swaggerUIConfig } from '@/config/swagger'
import { ServicePlugin } from './service'
import { RouterPlugin } from './router'

/**
 * 创建 Fastify 应用
 */
function createApp() {
  const app = fastify({
    logger: {
      level: process.env.NODE_ENV === 'development' ? 'info' : 'warn',
      transport:
        process.env.NODE_ENV === 'development'
          ? {
              target: 'pino-pretty',
              options: {
                translateTime: 'HH:MM:ss Z',
                ignore: 'pid,hostname',
              },
            }
          : undefined,
    },
  })

  // 注册插件
  app.register(fastifySwagger, swaggerConfig)
  app.register(fastifySwaggerUI, swaggerUIConfig)
  app.register(fastifyCors, {
    origin: true,
    credentials: true,
  })
  app.register(fastifyCookie)
  app.register(fastifyMultipart, config.multipart)

  // 注册服务和路由
  app.register(ServicePlugin)
  app.register(RouterPlugin)

  return app
}

/**
 * 启动服务器
 */
export async function run() {
  const app = createApp()

  try {
    await app.listen({ port: +config.port, host: '0.0.0.0' })
    await app.ready()

    const address = app.server.address()
    const port = typeof address === 'string' ? address : address?.port

    console.log('')
    console.log('🚀 服务器启动成功！')
    console.log(`📝 环境: ${process.env.NODE_ENV || 'development'}`)
    console.log(`🌐 地址: http://localhost:${port}`)
    console.log(`📚 API 文档: http://localhost:${port}/docs`)
    console.log('')
  } catch (error) {
    app.log.error(error, '服务器启动失败')
    process.exit(1)
  }

  // 优雅关闭
  const close = (signal: string) => {
    console.log(`\n收到 ${signal} 信号，正在关闭服务器...`)
    app.close().finally(() => {
      console.log('✅ 服务器已关闭')
      process.exit(0)
    })
  }

  process.once('SIGUSR2', () => close('SIGUSR2'))
  process.once('SIGINT', () => close('SIGINT'))
  process.once('SIGTERM', () => close('SIGTERM'))
}
