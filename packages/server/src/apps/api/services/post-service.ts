import type { PrismaClient } from '@prisma/client'
import type { Application } from '@/types'

export interface CreatePostInput {
  title: string
  content?: string
  published?: boolean
}

export interface UpdatePostInput {
  title?: string
  content?: string | null
  published?: boolean
}

export class PostServiceError extends Error {
  statusCode: number

  constructor(message: string, statusCode = 400) {
    super(message)
    this.statusCode = statusCode
  }
}

export function createPostService(app: Application) {
  return new PostService(app.$prisma)
}

export class PostService {
  constructor(private readonly prisma: PrismaClient) {}

  async listPosts(authorId: string) {
    return this.prisma.post.findMany({
      where: { authorId },
      orderBy: { createdAt: 'desc' },
    })
  }

  async getPost(authorId: string, postId: string) {
    const post = await this.prisma.post.findFirst({
      where: { id: postId, authorId },
    })

    if (!post) {
      throw new PostServiceError('Post not found', 404)
    }

    return post
  }

  async createPost(authorId: string, input: CreatePostInput) {
    const title = input.title?.trim()
    if (!title) {
      throw new PostServiceError('Title is required')
    }

    const content = normalizeContent(input.content)

    return this.prisma.post.create({
      data: {
        authorId,
        title,
        content,
        published: input.published ?? false,
      },
    })
  }

  async updatePost(authorId: string, postId: string, input: UpdatePostInput) {
    await this.getPost(authorId, postId)

    if (input.title !== undefined && !input.title.trim()) {
      throw new PostServiceError('Title is required')
    }

    return this.prisma.post.update({
      where: { id: postId },
      data: {
        ...(input.title !== undefined && { title: input.title.trim() }),
        ...(input.content !== undefined && { content: normalizeContent(input.content) }),
        ...(input.published !== undefined && { published: input.published }),
      },
    })
  }

  async deletePost(authorId: string, postId: string) {
    await this.getPost(authorId, postId)
    await this.prisma.post.delete({ where: { id: postId } })
  }
}

function normalizeContent(content?: string | null) {
  if (content === undefined || content === null) {
    return content ?? null
  }

  const trimmed = content.trim()
  return trimmed.length > 0 ? trimmed : null
}
