import type { SwaggerOptions } from '@fastify/swagger'
import type { FastifySwaggerUiOptions } from '@fastify/swagger-ui'

export const swaggerConfig: SwaggerOptions = {
  openapi: {
    info: {
      title: 'InsightMirror API',
      description: 'InsightMirror API 文档',
      version: '1.0.0',
    },
    servers: [
      {
        url: 'http://localhost:3000',
        description: '开发服务器',
      },
    ],
    tags: [
      { name: 'system', description: '系统相关接口' },
      { name: 'user', description: '用户相关接口' },
      { name: 'auth', description: '认证相关接口' }
    ],
    components: {
      securitySchemes: {
        bearerAuth: {
          type: 'http',
          scheme: 'bearer',
          bearerFormat: 'JWT',
        },
      },
    },
  },
}

export const swaggerUIConfig: FastifySwaggerUiOptions = {
  routePrefix: '/docs',
  uiConfig: {
    docExpansion: 'list',
    deepLinking: false,
    tryItOutEnabled: true,
  },
  staticCSP: true,
  transformStaticCSP: (header) => header,
}
