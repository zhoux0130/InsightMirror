import { FastifyInstance } from 'fastify'
import { PrismaClient } from '@prisma/client'
import type { PgVectorService } from './services/pgvector'

// 扩展 FastifyInstance 添加服务
export type Application = FastifyInstance & {
  $prisma: PrismaClient
  $session: ReturnType<typeof import('./services/session').SessionService>
  $pgvector: PgVectorService
  stop?: () => Promise<void>
}

// Web 应用类型
export type WebApplication = Application

// Service Factory 类型
export type ServiceFactory = (app: Application) => any | [any, () => Promise<void>]

// JSON 类型
export type JsonValue = string | number | boolean | null | JsonObject | JsonArray
export type JsonObject = { [key: string]: JsonValue }
export type JsonArray = JsonValue[]

// API 响应类型
export interface ApiResponse<T = any> {
  success: boolean
  data?: T
  message?: string
  error?: string
}

// 分页参数
export interface PaginationParams {
  page?: number
  pageSize?: number
}

// 分页响应
export interface PaginationResponse<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
  totalPages: number
}
