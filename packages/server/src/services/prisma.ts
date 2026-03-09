import { PrismaClient } from '@prisma/client'
import type { Application } from '../types'
import { system } from '../config'

type QueryEvent = {
  query: unknown
  duration: number
  params: unknown
}

/**
 * Prisma 数据库服务
 */
export const PrismaService = (_app: Application) => {
  const client = new PrismaClient({
    log: system.isDevelopment
      ? [
          { emit: 'event', level: 'query' },
          { emit: 'stdout', level: 'info' },
          { emit: 'stdout', level: 'warn' },
          { emit: 'stdout', level: 'error' },
        ]
      : [
          { emit: 'stdout', level: 'info' },
          { emit: 'stdout', level: 'warn' },
          { emit: 'stdout', level: 'error' },
        ],
    errorFormat: 'colorless',
  })

  // 开发环境下打印查询日志
  if (system.isDevelopment) {
    client.$on('query', (e: QueryEvent) => {
      console.log('📝 Query:', e.query)
      console.log('⏱️  Duration:', `${e.duration}ms`)
      if (e.params) {
        console.log('📋 Params:', e.params)
      }
    })
  }

  // 测试数据库连接
  client.$connect()
    .then(() => {
      console.log('✅ 数据库连接成功')
    })
    .catch((error) => {
      console.error('❌ 数据库连接失败:', error)
    })

  const stop = async () => {
    await client.$disconnect()
    console.log('📦 数据库连接已关闭')
  }

  return [client, stop]
}
