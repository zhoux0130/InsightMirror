import api from './api'

type ApiEnvelope<T> = { success: boolean; data: T; error?: string }

export interface AuthUser {
  id: string
  nickname: string | null
  avatar: string | null
}

export async function register(
  username: string,
  password: string,
  nickname?: string
): Promise<{ token: string; user: AuthUser }> {
  const res = await api.post<
    ApiEnvelope<{ token: string; user: AuthUser }>,
    ApiEnvelope<{ token: string; user: AuthUser }>
  >('/auth/register', { username, password, nickname })
  return res.data
}

export async function loginByPassword(
  username: string,
  password: string
): Promise<{ token: string; user: AuthUser }> {
  const res = await api.post<
    ApiEnvelope<{ token: string; user: AuthUser }>,
    ApiEnvelope<{ token: string; user: AuthUser }>
  >('/auth/login', { username, password })
  return res.data
}

export async function getMe(): Promise<AuthUser> {
  const res = await api.get<ApiEnvelope<AuthUser>, ApiEnvelope<AuthUser>>('/auth/me')
  return res.data
}

export async function logout(): Promise<void> {
  await api.post('/auth/logout')
}
