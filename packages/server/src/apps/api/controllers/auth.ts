import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify'
import type { WebApplication as Application } from '@/types'
import bcrypt from 'bcryptjs'
import { authMiddleware } from '@/middleware/auth'

export const AuthController = (fastify: FastifyInstance) => {
  const app = fastify as Application

  app.post(
    '/register',
    { schema: { summary: '用户名密码注册', tags: ['auth'] } },
    async (
      request: FastifyRequest<{ Body: { username: string; password: string; nickname?: string } }>,
      reply: FastifyReply
    ) => {
      const { username, password, nickname } = request.body

      if (!username || username.length < 3) {
        reply.code(400).send({ success: false, error: '用户名至少 3 个字符' })
        return
      }
      if (!password || password.length < 6) {
        reply.code(400).send({ success: false, error: '密码至少 6 个字符' })
        return
      }

      const existing = await app.$prisma.user.findUnique({ where: { username } })
      if (existing) {
        reply.code(409).send({ success: false, error: '用户名已存在' })
        return
      }

      const passwordHash = await bcrypt.hash(password, 10)
      const user = await app.$prisma.user.create({
        data: {
          username,
          passwordHash,
          nickname: nickname || username,
        },
      })

      const session = await app.$session.create({
        userId: user.id,
        type: 'password',
      })

      return {
        success: true,
        data: {
          token: session.token,
          user: { id: user.id, nickname: user.nickname, avatar: user.avatar },
        },
      }
    }
  )

  app.post(
    '/login',
    { schema: { summary: '用户名密码登录', tags: ['auth'] } },
    async (
      request: FastifyRequest<{ Body: { username: string; password: string } }>,
      reply: FastifyReply
    ) => {
      const { username, password } = request.body

      if (!username || !password) {
        reply.code(400).send({ success: false, error: '请输入用户名和密码' })
        return
      }

      const user = await app.$prisma.user.findUnique({ where: { username } })
      if (!user || !user.passwordHash) {
        reply.code(401).send({ success: false, error: '用户名或密码错误' })
        return
      }

      const valid = await bcrypt.compare(password, user.passwordHash)
      if (!valid) {
        reply.code(401).send({ success: false, error: '用户名或密码错误' })
        return
      }

      const session = await app.$session.create({
        userId: user.id,
        type: 'password',
      })

      return {
        success: true,
        data: {
          token: session.token,
          user: { id: user.id, nickname: user.nickname, avatar: user.avatar },
        },
      }
    }
  )

  app.get(
    '/me',
    {
      schema: { summary: '当前用户信息', tags: ['auth'] },
      preHandler: (req: FastifyRequest, rep: FastifyReply) => authMiddleware(req, rep, app),
    },
    async (request: FastifyRequest) => {
      const user = await app.$prisma.user.findUnique({
        where: { id: request.userId! },
        select: { id: true, nickname: true, avatar: true, createdAt: true },
      })
      return { success: true, data: user }
    }
  )

  app.post(
    '/logout',
    {
      schema: { summary: '登出', tags: ['auth'] },
      preHandler: (req: FastifyRequest, rep: FastifyReply) => authMiddleware(req, rep, app),
    },
    async (request: FastifyRequest) => {
      await app.$session.destroy(request.token!)
      return { success: true, data: null }
    }
  )
}
