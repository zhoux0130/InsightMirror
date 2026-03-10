# 构建阶段
FROM node:24-slim AS builder

RUN npm install -g pnpm@8.6.12
WORKDIR /app
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY packages/server/package.json ./packages/server/
COPY packages/server/prisma ./packages/server/prisma
RUN pnpm install --frozen-lockfile --filter server...

# 生成 Prisma Client（指定 OpenSSL 版本）
RUN cd packages/server && npx prisma generate

COPY packages/server ./packages/server
RUN pnpm --filter server build

# 运行阶段
FROM node:24-slim AS runner

WORKDIR /app
COPY --from=builder /app/packages/server/dist ./packages/server/dist
COPY --from=builder /app/packages/server/prisma ./packages/server/prisma
COPY --from=builder /app/packages/server/node_modules ./packages/server/node_modules
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/packages/server/package.json ./packages/server/

EXPOSE 3000
CMD ["node", "packages/server/dist/start.js"]
