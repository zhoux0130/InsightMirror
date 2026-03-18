import type { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import type { WebApplication as Application } from '@/types';
import { compute } from '@/config';
import { authMiddleware } from '@/middleware/auth';

// --- Schemas ---

const SimilarQuerySchema = {
  summary: '相似行情查询',
  tags: ['similar'],
  body: {
    type: 'object',
    required: ['close', 'volume'],
    properties: {
      close: { type: 'array', items: { type: 'number' } },
      volume: { type: 'array', items: { type: 'number' } },
      high: { type: 'array', items: { type: 'number' } },
      low: { type: 'array', items: { type: 'number' } },
      feature_version: { type: 'string', default: 'v1' },
      window_size: { type: 'number', default: 60 },
      future_days: { type: 'number', default: 20 },
      top_k: { type: 'number', default: 50 },
      query_end_date: { type: 'string' },
      query_symbol: { type: 'string' },
    },
  },
};

const FeatureVersionsSchema = {
  summary: '特征版本列表',
  tags: ['similar'],
};

const PipelineStatusSchema = {
  summary: 'Pipeline 状态查询',
  tags: ['pipeline'],
  querystring: {
    type: 'object',
    properties: {
      run_date: { type: 'string' },
    },
  },
};

const PipelineTriggerSchema = {
  summary: '触发 EOD Pipeline',
  tags: ['pipeline'],
  body: {
    type: 'object',
    properties: {
      run_date: { type: 'string' },
    },
  },
};

const PipelineInitSchema = {
  summary: '触发股票数据初始化',
  tags: ['pipeline'],
  body: {
    type: 'object',
    properties: {
      market: { type: 'string', enum: ['CN', 'US'], default: 'CN' },
      symbols: { type: 'array', items: { type: 'string' }, nullable: true },
      start_date: { type: 'string', nullable: true },
      end_date: { type: 'string', nullable: true },
      skip_hnsw: { type: 'boolean', default: false },
    },
  },
};

// --- Helper ---

async function proxyToCompute(
  url: string,
  method: 'GET' | 'POST',
  body?: any,
  query?: Record<string, string>
) {
  const targetUrl = new URL(url, compute.url);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value) targetUrl.searchParams.set(key, value);
    }
  }

  const options: RequestInit = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body && method === 'POST') {
    options.body = JSON.stringify(body);
  }

  const response = await fetch(targetUrl.toString(), options);

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Compute service error (${response.status}): ${errorText}`);
  }

  return response.json();
}

// --- Controller ---

/**
 * 相似行情查询控制器
 */
export const SimilarController = (fastify: FastifyInstance) => {
  const app = fastify as Application;

  // POST /api/similar/query - 相似行情查询
  app.post(
    '/query',
    { schema: SimilarQuerySchema },
    async (request: FastifyRequest, reply: FastifyReply) => {
      try {
        const result = await proxyToCompute('/compute/v1/search', 'POST', request.body);
        return { success: true, data: result };
      } catch (error: any) {
        reply.code(502).send({
          success: false,
          error: error.message || 'Compute service unavailable',
        });
      }
    }
  );

  // GET /api/similar/versions - 特征版本列表
  app.get(
    '/versions',
    { schema: FeatureVersionsSchema },
    async (request: FastifyRequest, reply: FastifyReply) => {
      try {
        const result = await proxyToCompute('/compute/v1/feature-versions', 'GET');
        return { success: true, data: result };
      } catch (error: any) {
        reply.code(502).send({
          success: false,
          error: error.message || 'Compute service unavailable',
        });
      }
    }
  );
};

/**
 * Pipeline 管理控制器
 */
export const PipelineController = (fastify: FastifyInstance) => {
  const app = fastify as Application;

  // GET /api/pipeline/status - Pipeline 状态
  app.get(
    '/status',
    { schema: PipelineStatusSchema },
    async (request: FastifyRequest<{ Querystring: { run_date?: string } }>, reply: FastifyReply) => {
      try {
        const result = await proxyToCompute(
          '/compute/v1/pipeline/status',
          'GET',
          undefined,
          request.query.run_date ? { run_date: request.query.run_date } : undefined
        );
        return { success: true, data: result };
      } catch (error: any) {
        reply.code(502).send({
          success: false,
          error: error.message || 'Compute service unavailable',
        });
      }
    }
  );

  // POST /api/pipeline/trigger - 触发 EOD Pipeline（需认证）
  app.post(
    '/trigger',
    {
      schema: PipelineTriggerSchema,
      preHandler: async (request: FastifyRequest, reply: FastifyReply) => {
        await authMiddleware(request, reply, app);
      },
    },
    async (request: FastifyRequest, reply: FastifyReply) => {
      try {
        const result = await proxyToCompute('/compute/v1/pipeline/eod', 'POST', request.body);
        return { success: true, data: result };
      } catch (error: any) {
        reply.code(502).send({
          success: false,
          error: error.message || 'Compute service unavailable',
        });
      }
    }
  );

  // POST /api/pipeline/init - 触发股票数据初始化（需认证）
  app.post(
    '/init',
    {
      schema: PipelineInitSchema,
      preHandler: async (request: FastifyRequest, reply: FastifyReply) => {
        await authMiddleware(request, reply, app);
      },
    },
    async (request: FastifyRequest, reply: FastifyReply) => {
      try {
        const result = await proxyToCompute('/compute/v1/pipeline/init', 'POST', request.body);
        return { success: true, data: result };
      } catch (error: any) {
        reply.code(502).send({
          success: false,
          error: error.message || 'Compute service unavailable',
        });
      }
    }
  );
};
