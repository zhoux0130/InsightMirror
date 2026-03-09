# 构建阶段
FROM node:24-slim AS builder

RUN npm install -g pnpm@8.6.12
WORKDIR /app

COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY packages/web/package.json ./packages/web/
RUN pnpm install --frozen-lockfile --filter web...

COPY packages/web ./packages/web
RUN pnpm build:web

# 运行阶段
FROM nginx:alpine AS runner

COPY --from=builder /app/packages/web/dist /usr/share/nginx/html
COPY packages/web/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
