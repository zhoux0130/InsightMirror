import api from './api';

type ApiEnvelope<T> = { success: boolean; data: T; error?: string };

export interface AuthUser {
  id: string;
  nickname: string | null;
  avatar: string | null;
}

export async function getWechatLoginUrl(): Promise<{ url: string; state: string }> {
  const res = await api.get<ApiEnvelope<{ url: string; state: string }>, ApiEnvelope<{ url: string; state: string }>>(
    '/auth/wechat/url'
  );
  return res.data;
}

export async function wechatCallback(
  code: string,
  state: string
): Promise<{ token: string; user: AuthUser }> {
  const res = await api.post<
    ApiEnvelope<{ token: string; user: AuthUser }>,
    ApiEnvelope<{ token: string; user: AuthUser }>
  >('/auth/wechat/callback', { code, state });
  return res.data;
}

export async function getMe(): Promise<AuthUser> {
  const res = await api.get<ApiEnvelope<AuthUser>, ApiEnvelope<AuthUser>>('/auth/me');
  return res.data;
}

export async function logout(): Promise<void> {
  await api.post('/auth/logout');
}
