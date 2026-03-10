import type { FastifyInstance, FastifyReply, FastifyRequest } from 'fastify';
import type { WebApplication as Application } from '@/types';
import { createBasketService, BasketServiceError } from '../services/basket-service';

function handleError(error: unknown, reply: FastifyReply) {
  if (error instanceof BasketServiceError) {
    reply.code(error.statusCode).send({ success: false, error: error.message });
  } else {
    const message = error instanceof Error ? error.message : 'Internal server error';
    reply.code(500).send({ success: false, error: message });
  }
}

function getUserId(request: FastifyRequest): string {
  return request.userId!;
}

export const BasketController = (fastify: FastifyInstance) => {
  const app = fastify as Application;
  const service = createBasketService(app);

  // ── Basket CRUD ──────────────────────────────────────────────

  app.post(
    '/',
    { schema: { summary: '创建策略篮子', tags: ['baskets'] } },
    async (
      request: FastifyRequest<{ Body: { name: string; description?: string; capital?: number } }>,
      reply: FastifyReply
    ) => {
      try {
        const data = await service.createBasket(getUserId(request), request.body);
        return { success: true, data };
      } catch (error) {
        handleError(error, reply);
      }
    }
  );

  app.get(
    '/',
    { schema: { summary: '篮子列表', tags: ['baskets'] } },
    async (request: FastifyRequest, reply: FastifyReply) => {
      try {
        const data = await service.listBaskets(getUserId(request));
        return { success: true, data };
      } catch (error) {
        handleError(error, reply);
      }
    }
  );

  app.get(
    '/:id',
    { schema: { summary: '篮子详情', tags: ['baskets'] } },
    async (
      request: FastifyRequest<{ Params: { id: string } }>,
      reply: FastifyReply
    ) => {
      try {
        const data = await service.getBasket(getUserId(request), request.params.id);
        return { success: true, data };
      } catch (error) {
        handleError(error, reply);
      }
    }
  );

  app.put(
    '/:id',
    { schema: { summary: '更新篮子', tags: ['baskets'] } },
    async (
      request: FastifyRequest<{
        Params: { id: string };
        Body: { name?: string; description?: string; capital?: number; status?: 'active' | 'archived' };
      }>,
      reply: FastifyReply
    ) => {
      try {
        const data = await service.updateBasket(getUserId(request), request.params.id, request.body);
        return { success: true, data };
      } catch (error) {
        handleError(error, reply);
      }
    }
  );

  app.delete(
    '/:id',
    { schema: { summary: '删除篮子', tags: ['baskets'] } },
    async (
      request: FastifyRequest<{ Params: { id: string } }>,
      reply: FastifyReply
    ) => {
      try {
        await service.deleteBasket(getUserId(request), request.params.id);
        return { success: true, data: null };
      } catch (error) {
        handleError(error, reply);
      }
    }
  );

  // ── Watchlist ────────────────────────────────────────────────

  app.post(
    '/:id/stocks',
    { schema: { summary: '添加关注股票', tags: ['baskets'] } },
    async (
      request: FastifyRequest<{ Params: { id: string }; Body: { symbol: string } }>,
      reply: FastifyReply
    ) => {
      try {
        const data = await service.addStock(getUserId(request), request.params.id, request.body.symbol);
        return { success: true, data };
      } catch (error) {
        handleError(error, reply);
      }
    }
  );

  app.delete(
    '/:id/stocks/:symbol',
    { schema: { summary: '移除关注股票', tags: ['baskets'] } },
    async (
      request: FastifyRequest<{ Params: { id: string; symbol: string } }>,
      reply: FastifyReply
    ) => {
      try {
        await service.removeStock(getUserId(request), request.params.id, request.params.symbol);
        return { success: true, data: null };
      } catch (error) {
        handleError(error, reply);
      }
    }
  );

  // ── Rules ────────────────────────────────────────────────────

  app.post(
    '/:id/rules',
    { schema: { summary: '创建规则', tags: ['baskets'] } },
    async (
      request: FastifyRequest<{
        Params: { id: string };
        Body: { name?: string; conditionGroup: any; enabled?: boolean };
      }>,
      reply: FastifyReply
    ) => {
      try {
        const data = await service.createRule(getUserId(request), request.params.id, request.body);
        return { success: true, data };
      } catch (error) {
        handleError(error, reply);
      }
    }
  );

  app.put(
    '/:id/rules/:ruleId',
    { schema: { summary: '更新规则', tags: ['baskets'] } },
    async (
      request: FastifyRequest<{
        Params: { id: string; ruleId: string };
        Body: { name?: string; conditionGroup?: any; enabled?: boolean };
      }>,
      reply: FastifyReply
    ) => {
      try {
        const data = await service.updateRule(
          getUserId(request), request.params.id, request.params.ruleId, request.body
        );
        return { success: true, data };
      } catch (error) {
        handleError(error, reply);
      }
    }
  );

  app.delete(
    '/:id/rules/:ruleId',
    { schema: { summary: '删除规则', tags: ['baskets'] } },
    async (
      request: FastifyRequest<{ Params: { id: string; ruleId: string } }>,
      reply: FastifyReply
    ) => {
      try {
        await service.deleteRule(getUserId(request), request.params.id, request.params.ruleId);
        return { success: true, data: null };
      } catch (error) {
        handleError(error, reply);
      }
    }
  );

  // ── Positions ────────────────────────────────────────────────

  app.post(
    '/:id/positions',
    { schema: { summary: '买入', tags: ['baskets'] } },
    async (
      request: FastifyRequest<{
        Params: { id: string };
        Body: {
          symbol: string;
          buyDate: string;
          buyPrice?: number;
          shares?: number;
          triggerType?: 'manual' | 'rule';
          ruleId?: string;
          note?: string;
        };
      }>,
      reply: FastifyReply
    ) => {
      try {
        const data = await service.buy(getUserId(request), request.params.id, request.body);
        return { success: true, data };
      } catch (error) {
        handleError(error, reply);
      }
    }
  );

  app.put(
    '/:id/positions/:posId/sell',
    { schema: { summary: '卖出', tags: ['baskets'] } },
    async (
      request: FastifyRequest<{
        Params: { id: string; posId: string };
        Body: { sellDate: string; sellPrice?: number; note?: string };
      }>,
      reply: FastifyReply
    ) => {
      try {
        const data = await service.sell(
          getUserId(request), request.params.id, request.params.posId, request.body
        );
        return { success: true, data };
      } catch (error) {
        handleError(error, reply);
      }
    }
  );

  app.get(
    '/:id/positions',
    { schema: { summary: '持仓列表', tags: ['baskets'] } },
    async (
      request: FastifyRequest<{
        Params: { id: string };
        Querystring: { status?: 'open' | 'closed' | 'all' };
      }>,
      reply: FastifyReply
    ) => {
      try {
        const data = await service.listPositions(
          getUserId(request), request.params.id, request.query.status
        );
        return { success: true, data };
      } catch (error) {
        handleError(error, reply);
      }
    }
  );

  // ── PnL & Compare ───────────────────────────────────────────

  app.get(
    '/:id/pnl',
    { schema: { summary: '单篮子收益', tags: ['baskets'] } },
    async (
      request: FastifyRequest<{ Params: { id: string } }>,
      reply: FastifyReply
    ) => {
      try {
        const data = await service.getBasketPnl(getUserId(request), request.params.id);
        return { success: true, data };
      } catch (error) {
        handleError(error, reply);
      }
    }
  );

  app.get(
    '/compare',
    { schema: { summary: '多篮子对比', tags: ['baskets'] } },
    async (request: FastifyRequest, reply: FastifyReply) => {
      try {
        const data = await service.compareBaskets(getUserId(request));
        return { success: true, data };
      } catch (error) {
        handleError(error, reply);
      }
    }
  );

  // ── Scan ─────────────────────────────────────────────────────

  app.post(
    '/:id/scan',
    { schema: { summary: '规则扫描', tags: ['baskets'] } },
    async (
      request: FastifyRequest<{ Params: { id: string } }>,
      reply: FastifyReply
    ) => {
      try {
        const data = await service.scanRules(getUserId(request), request.params.id);
        return { success: true, data };
      } catch (error) {
        handleError(error, reply);
      }
    }
  );
};
