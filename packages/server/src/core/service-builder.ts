import type { Application } from '../types'

/**
 * 服务构建器 - 用于简化服务创建
 */
export class ServiceBuilder<T> {
  private service: T
  private stopCallback?: () => Promise<void>

  constructor(service: T) {
    this.service = service
  }

  /**
   * 设置停止回调
   */
  onStop(callback: () => Promise<void>): this {
    this.stopCallback = callback
    return this
  }

  /**
   * 构建服务
   */
  build(): [T, (() => Promise<void>) | undefined] {
    return [this.service, this.stopCallback]
  }
}

/**
 * 创建服务构建器
 */
export function createService<T>(service: T): ServiceBuilder<T> {
  return new ServiceBuilder(service)
}

/**
 * 简单服务工厂 - 不需要停止回调
 */
export function simpleService<T>(factory: (app: Application) => T) {
  return factory
}
