import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify'
import type { WebApplication as Application } from '@/types'
import { randomBytes } from 'crypto'
import bcrypt from 'bcryptjs'
import { authMiddleware } from '@/middleware/auth'
import * as wechatService from '../services/wechat-service'

export const AuthController = (fastify: FastifyInstance) => {
  const app = fastify as Application

  /**
   * POST /register — 用户名密码注册
   */
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

  /**
   * POST /login — 用户名密码登录
   */
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

  /**
   * GET /url — 返回微信扫码登录 URL
   */
  app.get(
    '/wechat/url',
    { schema: { summary: '获取微信登录URL', tags: ['auth'] } },
    async (_request: FastifyRequest, _reply: FastifyReply) => {
      const state = randomBytes(16).toString('hex')
      const url = wechatService.getAuthUrl(state)
      return { success: true, data: { url, state } }
    }
  )

  /**
   * POST /wechat/callback — 前端拿到 code 后调用完成登录
   */
  app.post(
    '/wechat/callback',
    { schema: { summary: '微信登录回调', tags: ['auth'] } },
    async (
      request: FastifyRequest<{ Body: { code: string; state: string } }>,
      reply: FastifyReply
    ) => {
      const { code } = request.body

      if (!code) {
        reply.code(400).send({ success: false, error: '缺少 code 参数' })
        return
      }

      try {
        // 1. 用 code 换 access_token + openid
        const tokenRes = await wechatService.getAccessToken(code)
        const { access_token, openid, unionid } = tokenRes

        // 2. 获取微信用户信息
        const userInfo = await wechatService.getUserInfo(access_token, openid)

        // 3. 查找或创建 OAuth + User
        const oauth = await app.$prisma.oAuth.findUnique({
          where: { type_openid: { type: 'wechat_open', openid } },
          include: { user: true },
        })

        let user
        if (oauth) {
          user = oauth.user
          // 更新用户信息（头像/昵称可能变化）
          await app.$prisma.user.update({
            where: { id: user.id },
            data: {
              nickname: userInfo.nickname || user.nickname,
              avatar: userInfo.headimgurl || user.avatar,
            },
          })
        } else {
          // 创建新用户 + OAuth 记录
          user = await app.$prisma.user.create({
            data: {
              nickname: userInfo.nickname || '微信用户',
              avatar: userInfo.headimgurl || null,
              oauths: {
                create: {
                  type: 'wechat_open',
                  openid,
                  unionid: unionid || userInfo.unionid || null,
                },
              },
            },
          })
        }

        // 4. 创建 Session
        const session = await app.$session.create({
          userId: user.id,
          type: 'wechat_open',
        })

        return {
          success: true,
          data: {
            token: session.token,
            user: {
              id: user.id,
              nickname: user.nickname,
              avatar: user.avatar,
            },
          },
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : '微信登录失败'
        reply.code(500).send({ success: false, error: message })
      }
    }
  )

  /**
   * GET /me — 返回当前登录用户信息
   */
  app.get(
    '/me',
    {
      schema: { summary: '当前用户信息', tags: ['auth'] },
      preHandler: (req: FastifyRequest, rep: FastifyReply) => authMiddleware(req, rep, app),
    },
    async (request: FastifyRequest, _reply: FastifyReply) => {
      const user = await app.$prisma.user.findUnique({
        where: { id: request.userId! },
        select: { id: true, nickname: true, avatar: true, createdAt: true },
      })
      return { success: true, data: user }
    }
  )

  /**
   * POST /logout — 登出，销毁 session
   */
  app.post(
    '/logout',
    {
      schema: { summary: '登出', tags: ['auth'] },
      preHandler: (req: FastifyRequest, rep: FastifyReply) => authMiddleware(req, rep, app),
    },
    async (request: FastifyRequest, _reply: FastifyReply) => {
      await app.$session.destroy(request.token!)
      return { success: true, data: null }
    }
  )
}
