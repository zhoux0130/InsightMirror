export const system = {
  env: process.env.NODE_ENV || 'development',
  isDevelopment: process.env.NODE_ENV === 'development',
  isProduction: process.env.NODE_ENV === 'production',
}

const checkRequiredEnv = (key: string, value: any, description: string) => {
  if (!value) {
    if (process.env.NODE_ENV === 'production') {
      throw new Error(`❌ 生产环境必须设置 ${key}（${description}）`)
    } else {
      console.warn(`⚠️  警告: ${key} 未设置（${description}），使用开发默认值`)
    }
  }
}

export const web = {
  secret: (() => {
    const secret = process.env.WEB_SECRET
    checkRequiredEnv('WEB_SECRET', secret, 'Web 服务密钥')
    return secret || 'dev-secret-change-in-production-min-32-chars'
  })(),
  port: process.env.PORT || 3000,

  multipart: {
    limits: {
      fileSize: 10 * 1024 * 1024,
    },
  },
}

export const app = {
  secretKey: (() => {
    const secret = process.env.APP_SECRET
    checkRequiredEnv('APP_SECRET', secret, '应用密钥')
    return secret || 'dev-app-secret-change-in-production-min-32-chars'
  })(),
}

export const jwt = {
  secret: (() => {
    const secret = process.env.JWT_SECRET
    checkRequiredEnv('JWT_SECRET', secret, 'JWT 签名密钥')
    return secret || 'dev-jwt-secret-change-in-production-min-32-chars'
  })(),
  expiresIn: process.env.JWT_EXPIRES_IN || '7d',
}

export const database = {
  url: process.env.DATABASE_URL,
}
