import { Pool, PoolClient } from 'pg';
import { database } from '@/config';
import type { Application } from '@/types';

export interface SearchSimilarOptions {
  vector: number[];
  topK?: number;
  windowSize?: number;
  featureVersion?: string;
  excludeSymbol?: string;
  excludeDateRange?: { endDate: string; gapDays: number };
  dateFrom?: string;
  dateTo?: string;
}

export interface SimilarResult {
  segmentId: number;
  symbol: string;
  startDate: string;
  endDate: string;
  distance: number;
  similarity: number;
  baseClose?: number;
}

export interface PgVectorService {
  searchSimilar(options: SearchSimilarOptions): Promise<SimilarResult[]>;
  query(sql: string, params?: any[]): Promise<any[]>;
}

/**
 * PgVector 服务 - 管理 pg 连接池，提供向量检索
 */
export const PgVectorServiceFactory = (_app: Application) => {
  const pool = new Pool({
    connectionString: database.url,
    max: 10,
    idleTimeoutMillis: 30000,
    connectionTimeoutMillis: 5000,
  });

  pool
    .query('SELECT 1')
    .then(() => {
      console.log('✅ PgVector 连接池已就绪');
    })
    .catch((err) => {
      console.warn('⚠️  PgVector 连接池初始化警告:', err.message);
    });

  const service: PgVectorService = {
    async searchSimilar(options: SearchSimilarOptions): Promise<SimilarResult[]> {
      const {
        vector,
        topK = 50,
        windowSize = 60,
        featureVersion = 'v1',
        excludeSymbol,
        excludeDateRange,
      } = options;

      const vectorStr = '[' + vector.join(',') + ']';
      const conditions: string[] = [];
      const params: any[] = [vectorStr, windowSize, featureVersion, topK];
      let paramIdx = 5;

      if (excludeSymbol) {
        conditions.push(`si.symbol != $${paramIdx}`);
        params.push(excludeSymbol);
        paramIdx++;
      }

      if (excludeDateRange) {
        conditions.push(
          `(si.end_date < ($${paramIdx})::date - ($${paramIdx + 1})::int * INTERVAL '1 day'` +
            ` OR si.end_date > ($${paramIdx})::date + ($${paramIdx + 1})::int * INTERVAL '1 day')`
        );
        params.push(excludeDateRange.endDate, excludeDateRange.gapDays);
        paramIdx += 2;
      }

      if (options.dateFrom) {
        conditions.push(`si.end_date >= $${paramIdx}::date`);
        params.push(options.dateFrom);
        paramIdx++;
      }

      if (options.dateTo) {
        conditions.push(`si.end_date <= $${paramIdx}::date`);
        params.push(options.dateTo);
        paramIdx++;
      }

      const whereExtra = conditions.length > 0 ? 'AND ' + conditions.join(' AND ') : '';

      const sql = `
        SELECT
          si.id AS segment_id,
          si.symbol,
          si.start_date::text,
          si.end_date::text,
          db.close::text AS base_close,
          sf.feature_vector <=> $1::vector AS distance
        FROM segment_feature sf
        JOIN segment_index si ON si.id = sf.segment_id
        JOIN daily_bar db ON db.symbol = si.symbol AND db.trade_date = si.end_date
        WHERE si.window_size = $2
          AND si.feature_version = $3
          ${whereExtra}
        ORDER BY sf.feature_vector <=> $1::vector
        LIMIT $4
      `;

      const result = await pool.query(sql, params);
      return result.rows.map((row: any) => ({
        segmentId: Number(row.segment_id),
        symbol: row.symbol,
        startDate: row.start_date,
        endDate: row.end_date,
        distance: parseFloat(row.distance),
        similarity: 1.0 - parseFloat(row.distance),
        baseClose: row.base_close == null ? undefined : parseFloat(row.base_close),
      }));
    },

    async query(sql: string, params?: any[]): Promise<any[]> {
      const result = await pool.query(sql, params);
      return result.rows;
    },
  };

  const stop = async () => {
    await pool.end();
    console.log('📦 PgVector 连接池已关闭');
  };

  return [service, stop];
};
