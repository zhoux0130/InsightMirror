# 构建阶段
FROM node:24-slim AS builder

# 安装构建依赖和 OpenSSL
RUN apt-get update -y && apt-get install -y openssl libssl-dev ca-certificates && rm -rf /var/lib/apt/lists/*

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

# 安装运行时依赖：OpenSSL 和 libssl
RUN apt-get update -y && \
    apt-get install -y openssl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

RUN npm install -g pnpm@8.6.12
WORKDIR /app
COPY --from=builder /app/package.json /app/pnpm-workspace.yaml /app/pnpm-lock.yaml ./
COPY --from=builder /app/packages/server/package.json ./packages/server/
COPY --from=builder /app/packages/server/dist ./packages/server/dist
COPY --from=builder /app/packages/server/prisma ./packages/server/prisma
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/packages/server/node_modules ./packages/server/node_modules

EXPOSE 3000
CMD ["pnpm", "start:server"]
