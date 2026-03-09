import 'dotenv/config'
import { run as runServer } from './runners/server'

const Command = {
  server: runServer,
}

async function run(cmd: string) {
  const fn = Command[cmd as keyof typeof Command]
  if (!fn) {
    console.error(`❌ 无效的命令: ${cmd}`)
    console.log('可用命令: server')
    process.exit(-1)
  }
  await fn()
}

if (require.main === module) {
  const cmd = process.argv[2] || process.env.APP_CMD || 'server'
  run(cmd).catch((e) => {
    console.error('❌ 启动失败:', e)
    process.exit(-1)
  })
}
