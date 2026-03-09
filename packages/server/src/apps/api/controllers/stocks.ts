import type { FastifyInstance, FastifyReply, FastifyRequest } from 'fastify';
import type { WebApplication as Application } from '@/types';
import { createStockDetailService, StockDetailError } from '../services/stock-detail-service';

const StockOptionsSchema = {
  summary: '股票选项列表',
  tags: ['stocks'],
};

const StockDetailSchema = {
  summary: '个股详情页数据',
  tags: ['stocks'],
  params: {
    type: 'object',
    required: ['symbol'],
    properties: {
      symbol: { type: 'string' },
    },
  },
  querystring: {
    type: 'object',
    properties: {
      endDate: { type: 'string' },
      topK: { type: 'number', minimum: 20, maximum: 150, default: 100 },
    },
  },
};

export const StockController = (fastify: FastifyInstance) => {
  const app = fastify as Application;
  const service = createStockDetailService(app);

  app.get('/options', { schema: StockOptionsSchema }, async (_request, reply) => {
    try {
      const data = await service.listOptions();
      return { success: true, data };
    } catch (error: any) {
      reply.code(500).send({
        success: false,
        error: error.message || 'Failed to load stock options',
      });
    }
  });

  app.get(
    '/:symbol/detail',
    { schema: StockDetailSchema },
    async (
      request: FastifyRequest<{
        Params: { symbol: string };
        Querystring: { endDate?: string; topK?: number };
      }>,
      reply: FastifyReply
    ) => {
      try {
        const data = await service.getDetail({
          symbol: request.params.symbol,
          endDate: request.query.endDate,
          topK: request.query.topK,
        });
        return { success: true, data };
      } catch (error: any) {
        const statusCode = error instanceof StockDetailError ? error.statusCode : 500;
        reply.code(statusCode).send({
          success: false,
          error: error.message || 'Failed to build stock detail',
        });
      }
    }
  );
};
