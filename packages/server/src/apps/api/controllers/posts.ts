import type { FastifyInstance, FastifyReply, FastifyRequest } from 'fastify'
import type { WebApplication as Application } from '@/types'
import { createPostService, PostServiceError } from '../services/post-service'

function handleError(error: unknown, reply: FastifyReply) {
  if (error instanceof PostServiceError) {
    reply.code(error.statusCode).send({ success: false, error: error.message })
    return
  }

  const message = error instanceof Error ? error.message : 'Internal server error'
  reply.code(500).send({ success: false, error: message })
}

function getUserId(request: FastifyRequest) {
  return request.userId!
}

export const PostController = (fastify: FastifyInstance) => {
  const app = fastify as Application
  const service = createPostService(app)

  app.get('/', { schema: { summary: 'Post 列表', tags: ['posts'] } }, async (request, reply) => {
    try {
      const data = await service.listPosts(getUserId(request))
      return { success: true, data }
    } catch (error) {
      handleError(error, reply)
    }
  })

  app.get(
    '/:id',
    { schema: { summary: 'Post 详情', tags: ['posts'] } },
    async (request: FastifyRequest<{ Params: { id: string } }>, reply) => {
      try {
        const data = await service.getPost(getUserId(request), request.params.id)
        return { success: true, data }
      } catch (error) {
        handleError(error, reply)
      }
    }
  )

  app.post(
    '/',
    { schema: { summary: '创建 Post', tags: ['posts'] } },
    async (
      request: FastifyRequest<{ Body: { title: string; content?: string; published?: boolean } }>,
      reply
    ) => {
      try {
        const data = await service.createPost(getUserId(request), request.body)
        return { success: true, data }
      } catch (error) {
        handleError(error, reply)
      }
    }
  )

  app.put(
    '/:id',
    { schema: { summary: '更新 Post', tags: ['posts'] } },
    async (
      request: FastifyRequest<{
        Params: { id: string }
        Body: { title?: string; content?: string | null; published?: boolean }
      }>,
      reply
    ) => {
      try {
        const data = await service.updatePost(getUserId(request), request.params.id, request.body)
        return { success: true, data }
      } catch (error) {
        handleError(error, reply)
      }
    }
  )

  app.delete(
    '/:id',
    { schema: { summary: '删除 Post', tags: ['posts'] } },
    async (request: FastifyRequest<{ Params: { id: string } }>, reply) => {
      try {
        await service.deletePost(getUserId(request), request.params.id)
        return { success: true, data: null }
      } catch (error) {
        handleError(error, reply)
      }
    }
  )
}
