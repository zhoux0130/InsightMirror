import api from './api'

type ApiEnvelope<T> = { success: boolean; data: T; error?: string }

export interface Post {
  id: string
  title: string
  content: string | null
  published: boolean
  createdAt: string
  updatedAt: string
  authorId: string
}

export async function listPosts(): Promise<Post[]> {
  const res = await api.get<ApiEnvelope<Post[]>, ApiEnvelope<Post[]>>('/posts')
  return res.data
}

export async function getPost(id: string): Promise<Post> {
  const res = await api.get<ApiEnvelope<Post>, ApiEnvelope<Post>>(`/posts/${id}`)
  return res.data
}

export async function createPost(input: {
  title: string
  content?: string
  published?: boolean
}): Promise<Post> {
  const res = await api.post<ApiEnvelope<Post>, ApiEnvelope<Post>>('/posts', input)
  return res.data
}

export async function updatePost(
  id: string,
  input: { title?: string; content?: string | null; published?: boolean }
): Promise<Post> {
  const res = await api.put<ApiEnvelope<Post>, ApiEnvelope<Post>>(`/posts/${id}`, input)
  return res.data
}

export async function deletePost(id: string): Promise<void> {
  await api.delete(`/posts/${id}`)
}
