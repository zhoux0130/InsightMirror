"""PgVector-based similarity search with P0/P1 optimizations.

P0: Sliding window dedup (min_gap = W/2)
P0: Information leakage gap (gap = 2 * future_days)
P1: Two-stage matching (ANN top-200 → stats filter to final top-K)
P1: Dynamic K truncation with floor protection
"""

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.core.search.base import (
    SearchRequest,
    SearchResult,
    SimilaritySearchEngine,
)


class PgVectorSearchEngine(SimilaritySearchEngine):
    def __init__(self, db: Session):
        self.db = db

    def search(self, request: SearchRequest) -> list[SearchResult]:
        # Stage 1: ANN retrieval (top-200)
        ann_results = self._ann_search(request)

        # Apply dedup and leakage filters
        filtered = self._apply_filters(ann_results, request)

        # Stage 2: Dynamic K truncation (P1)
        final = self._dynamic_k_truncate(filtered, request.top_k)

        return final

    def _ann_search(self, request: SearchRequest) -> list[SearchResult]:
        """Stage 1: Approximate nearest neighbor search via pgvector."""
        vector_str = "[" + ",".join(str(x) for x in request.query_vector) + "]"

        # Build exclusion conditions
        conditions = []
        params: dict = {
            "vector": vector_str,
            "ann_k": settings.ann_top_k,
            "window_size": request.window_size,
            "feature_version": request.feature_version,
        }

        # Information leakage gap (P0): exclude segments too close to query date
        if request.query_end_date:
            leakage_gap = settings.leakage_gap_multiplier * request.future_days
            conditions.append(
                "(si.end_date < :query_end_date::date - :leakage_gap * INTERVAL '1 day'"
                " OR si.end_date > :query_end_date::date + :leakage_gap * INTERVAL '1 day')"
            )
            params["query_end_date"] = request.query_end_date
            params["leakage_gap"] = leakage_gap

        # Exclude query symbol to avoid self-matching
        if request.query_symbol:
            conditions.append("si.symbol != :query_symbol")
            params["query_symbol"] = request.query_symbol

        where_clause = ""
        if conditions:
            where_clause = "AND " + " AND ".join(conditions)

        sql = text(f"""
            SELECT
                si.id AS segment_id,
                si.symbol,
                si.start_date::text,
                si.end_date::text,
                sf.feature_vector <=> :vector::vector AS distance
            FROM segment_feature sf
            JOIN segment_index si ON si.id = sf.segment_id
            WHERE si.window_size = :window_size
              AND si.feature_version = :feature_version
              {where_clause}
            ORDER BY sf.feature_vector <=> :vector::vector
            LIMIT :ann_k
        """)

        rows = self.db.execute(sql, params).fetchall()
        return [
            SearchResult(
                segment_id=row[0],
                symbol=row[1],
                start_date=row[2],
                end_date=row[3],
                distance=float(row[4]),
                similarity=1.0 - float(row[4]),
            )
            for row in rows
        ]

    def _apply_filters(
        self, results: list[SearchResult], request: SearchRequest
    ) -> list[SearchResult]:
        """Apply sliding window dedup (P0)."""
        min_gap = request.window_size // 2

        # Sort by distance (best first)
        results.sort(key=lambda r: r.distance)

        filtered: list[SearchResult] = []
        # Track accepted (symbol, end_date) to enforce min_gap
        accepted: dict[str, list[str]] = {}

        for r in results:
            if r.symbol not in accepted:
                accepted[r.symbol] = []
                filtered.append(r)
                accepted[r.symbol].append(r.end_date)
                continue

            # Check gap with all accepted segments of same symbol
            too_close = False
            for prev_date_str in accepted[r.symbol]:
                # Simple date distance check (YYYY-MM-DD format)
                from datetime import date

                prev_date = date.fromisoformat(prev_date_str)
                curr_date = date.fromisoformat(r.end_date)
                gap_days = abs((curr_date - prev_date).days)
                if gap_days < min_gap:
                    too_close = True
                    break

            if not too_close:
                filtered.append(r)
                accepted[r.symbol].append(r.end_date)

        return filtered

    def _dynamic_k_truncate(
        self, results: list[SearchResult], target_k: int
    ) -> list[SearchResult]:
        """Dynamic K truncation with floor protection (P1).

        Truncate when similarity gap exceeds threshold,
        but ensure at least min_k results.
        """
        if len(results) <= 5:
            return results

        min_k = max(10, target_k // 3)  # Floor protection
        gap_threshold = 0.05  # Similarity drop threshold

        for i in range(min_k, min(len(results) - 1, target_k)):
            gap = results[i].similarity - results[i + 1].similarity
            if gap > gap_threshold:
                return results[: i + 1]

        return results[:target_k]
