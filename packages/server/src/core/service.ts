import type { Application, ServiceFactory } from '../types'

/**
 * 启动服务
 * @param services 服务工厂对象
 * @returns [app, stop] - 应用实例和停止函数
 */
export async function start(services: Record<string, ServiceFactory>): Promise<[Application, () => Promise<void>]> {
  const app = {} as Application
  const stopCallbacks: Array<() => Promise<void>> = []

  // 初始化所有服务
  for (const [name, factory] of Object.entries(services)) {
    const result = factory(app)

    if (Array.isArray(result)) {
      const [service, stop] = result
      app[name as keyof Application] = service
      if (stop) {
        stopCallbacks.push(stop)
      }
    } else {
      app[name as keyof Application] = result
    }
  }

  // 停止函数
  const stop = async () => {
    console.log('🛑 正在停止服务...')
    for (const callback of stopCallbacks) {
      try {
        await callback()
      } catch (error) {
        console.error('停止服务时发生错误:', error)
      }
    }
    console.log('✅ 所有服务已停止')
  }

  app.stop = stop

  return [app, stop]
}
