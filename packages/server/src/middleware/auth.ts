import type { FastifyRequest, FastifyReply } from 'fastify'
import type { WebApplication as Application } from '@/types'

// 扩展 Request 类型
declare module 'fastify' {
  interface FastifyRequest {
    userId?: string
    user?: any
    token?: string
  }
}

/**
 * 认证中间件 - 验证用户登录状态
 */
export async function authMiddleware(
  request: FastifyRequest,
  reply: FastifyReply,
  app: Application
) {
  // 从 header 中获取 token
  const token = request.headers.authorization?.replace('Bearer ', '') ||
                request.headers['x-token'] as string

  if (!token) {
    reply.code(401).send({
      success: false,
      message: '未登录',
      code: 'UNAUTHORIZED',
    })
    return
  }

  try {
    // 验证 token
    const session = await app.$session.getByToken(token)

    if (!session) {
      reply.code(401).send({
        success: false,
        message: '登录已过期',
        code: 'TOKEN_EXPIRED',
      })
      return
    }

    // 将用户信息附加到请求对象
    request.userId = session.userId
    request.user = session.user
    request.token = token
  } catch (error) {
    reply.code(401).send({
      success: false,
      message: '认证失败',
      code: 'AUTH_FAILED',
    })
  }
}

/**
 * 可选认证中间件 - token 存在则验证，不存在也可以继续
 */
export async function optionalAuthMiddleware(
  request: FastifyRequest,
  reply: FastifyReply,
  app: Application
) {
  const token = request.headers.authorization?.replace('Bearer ', '') ||
                request.headers['x-token'] as string

  if (token) {
    try {
      const session = await app.$session.getByToken(token)
      if (session) {
        request.userId = session.userId
        request.user = session.user
        request.token = token
      }
    } catch (error) {
      // 可选认证，失败也继续
    }
  }
}
