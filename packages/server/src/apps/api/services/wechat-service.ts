import { wechat } from '@/config'

const WECHAT_AUTH_URL = 'https://open.weixin.qq.com/connect/qrconnect'
const WECHAT_TOKEN_URL = 'https://api.weixin.qq.com/sns/oauth2/access_token'
const WECHAT_USERINFO_URL = 'https://api.weixin.qq.com/sns/userinfo'

export interface WechatTokenResponse {
  access_token: string
  expires_in: number
  refresh_token: string
  openid: string
  scope: string
  unionid?: string
  errcode?: number
  errmsg?: string
}

export interface WechatUserInfo {
  openid: string
  nickname: string
  sex: number
  province: string
  city: string
  country: string
  headimgurl: string
  unionid?: string
  errcode?: number
  errmsg?: string
}

/**
 * 生成微信扫码登录 URL
 */
export function getAuthUrl(state: string): string {
  const params = new URLSearchParams({
    appid: wechat.openAppId,
    redirect_uri: wechat.openRedirectUri,
    response_type: 'code',
    scope: 'snsapi_login',
    state,
  })
  return `${WECHAT_AUTH_URL}?${params.toString()}#wechat_redirect`
}

/**
 * 用授权 code 换取 access_token + openid
 */
export async function getAccessToken(code: string): Promise<WechatTokenResponse> {
  const params = new URLSearchParams({
    appid: wechat.openAppId,
    secret: wechat.openSecret,
    code,
    grant_type: 'authorization_code',
  })
  const res = await fetch(`${WECHAT_TOKEN_URL}?${params.toString()}`)
  const data = (await res.json()) as WechatTokenResponse
  if (data.errcode) {
    throw new Error(`WeChat token error: ${data.errcode} ${data.errmsg}`)
  }
  return data
}

/**
 * 获取微信用户信息
 */
export async function getUserInfo(accessToken: string, openid: string): Promise<WechatUserInfo> {
  const params = new URLSearchParams({
    access_token: accessToken,
    openid,
    lang: 'zh_CN',
  })
  const res = await fetch(`${WECHAT_USERINFO_URL}?${params.toString()}`)
  const data = (await res.json()) as WechatUserInfo
  if (data.errcode) {
    throw new Error(`WeChat userinfo error: ${data.errcode} ${data.errmsg}`)
  }
  return data
}
