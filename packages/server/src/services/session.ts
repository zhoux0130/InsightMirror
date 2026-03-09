import type { Application } from '../types'
import { generateToken } from '../utils/token'

/**
 * Session 服务
 */
export const SessionService = (app: Application) => {
  /**
   * 创建会话
   */
  const create = async (params: {
    userId: string
    type?: string
    sessionKey?: string
  }) => {
    const token = generateToken()

    const session = await app.$prisma.session.create({
      data: {
        userId: params.userId,
        token,
        type: params.type || 'h5',
        sessionKey: params.sessionKey,
      },
    })

    return session
  }

  /**
   * 通过 token 获取会话
   */
  const getByToken = async (token: string) => {
    const session = await app.$prisma.session.findUnique({
      where: { token },
      include: { user: true },
    })

    if (session) {
      // 更新最后访问时间
      await app.$prisma.session.update({
        where: { id: session.id },
        data: { accessAt: new Date() },
      })
    }

    return session
  }

  /**
   * 删除会话（登出）
   */
  const destroy = async (token: string) => {
    const session = await app.$prisma.session.findUnique({
      where: { token },
    })

    if (session) {
      await app.$prisma.session.delete({
        where: { id: session.id },
      })
      return true
    }

    return false
  }

  /**
   * 清理过期会话（超过 30 天未访问）
   */
  const cleanup = async () => {
    const thirtyDaysAgo = new Date()
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30)

    const result = await app.$prisma.session.deleteMany({
      where: {
        accessAt: {
          lt: thirtyDaysAgo,
        },
      },
    })

    return result.count
  }

  return {
    create,
    getByToken,
    destroy,
    cleanup,
  }
}
