"""Query API routes."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import numpy as np

from app.core.feature import registry as feature_registry
from app.core.search.pgvector import PgVectorSearchEngine
from app.core.search.base import SearchRequest as CoreSearchRequest
from app.core.stats.engine import StatsEngine
from app.db.connection import get_db

router = APIRouter(prefix="/compute/v1", tags=["query"])


class FeatureRequest(BaseModel):
    close: list[float]
    volume: list[float]
    high: list[float] | None = None
    low: list[float] | None = None
    feature_version: str = "v1"


class FeatureResponse(BaseModel):
    version: str
    dimension: int
    vector: list[float]


class SearchRequest(BaseModel):
    close: list[float]
    volume: list[float]
    high: list[float] | None = None
    low: list[float] | None = None
    feature_version: str = "v1"
    window_size: int = 60
    future_days: int = 20
    top_k: int = 50
    query_end_date: str | None = None
    query_symbol: str | None = None


class MatchResult(BaseModel):
    segment_id: int
    symbol: str
    start_date: str
    end_date: str
    similarity: float


class StatsResult(BaseModel):
    count: int
    win_rate: float
    weighted_win_rate: float
    avg_return: float
    median_return: float
    max_return: float
    min_return: float
    avg_max_drawdown: float
    avg_max_profit: float
    quality_score: float
    confidence_lower: float | None = None
    confidence_upper: float | None = None


class SearchResponse(BaseModel):
    matches: list[MatchResult]
    stats: StatsResult


@router.post("/feature", response_model=FeatureResponse)
def compute_feature(req: FeatureRequest):
    calculator = feature_registry.get(req.feature_version)

    close = np.array(req.close, dtype=np.float64)
    volume = np.array(req.volume, dtype=np.float64)
    high = np.array(req.high, dtype=np.float64) if req.high else None
    low = np.array(req.low, dtype=np.float64) if req.low else None

    try:
        vector = calculator.calculate(close, volume, high, low)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return FeatureResponse(
        version=calculator.version,
        dimension=calculator.dimension,
        vector=vector.tolist(),
    )


@router.post("/search", response_model=SearchResponse)
def search_similar(req: SearchRequest):
    # Step 1: Compute feature vector
    calculator = feature_registry.get(req.feature_version)

    close = np.array(req.close, dtype=np.float64)
    volume = np.array(req.volume, dtype=np.float64)
    high = np.array(req.high, dtype=np.float64) if req.high else None
    low = np.array(req.low, dtype=np.float64) if req.low else None

    try:
        query_vector = calculator.calculate(close, volume, high, low)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Step 2: Search similar segments
    with get_db() as db:
        engine = PgVectorSearchEngine(db)
        search_req = CoreSearchRequest(
            query_vector=query_vector,
            window_size=req.window_size,
            future_days=req.future_days,
            feature_version=req.feature_version,
            top_k=req.top_k,
            query_end_date=req.query_end_date,
            query_symbol=req.query_symbol,
        )
        results = engine.search(search_req)

        # Step 3: Compute statistics
        stats_engine = StatsEngine(db)
        stats = stats_engine.compute_future_stats(
            segment_ids=[r.segment_id for r in results],
            similarities=[r.similarity for r in results],
            future_days=req.future_days,
        )

    matches = [
        MatchResult(
            segment_id=r.segment_id,
            symbol=r.symbol,
            start_date=r.start_date,
            end_date=r.end_date,
            similarity=round(r.similarity, 4),
        )
        for r in results
    ]

    return SearchResponse(
        matches=matches,
        stats=StatsResult(
            count=stats.count,
            win_rate=round(stats.win_rate, 4),
            weighted_win_rate=round(stats.weighted_win_rate, 4),
            avg_return=round(stats.avg_return, 4),
            median_return=round(stats.median_return, 4),
            max_return=round(stats.max_return, 4),
            min_return=round(stats.min_return, 4),
            avg_max_drawdown=round(stats.avg_max_drawdown, 4),
            avg_max_profit=round(stats.avg_max_profit, 4),
            quality_score=stats.quality_score,
            confidence_lower=(round(stats.confidence_lower, 4)
                              if stats.confidence_lower is not None else None),
            confidence_upper=(round(stats.confidence_upper, 4)
                              if stats.confidence_upper is not None else None),
        ),
    )


@router.get("/feature-versions")
def list_feature_versions():
    versions = feature_registry.list_versions()
    result = []
    for v in versions:
        calc = feature_registry.get(v)
        result.append({
            "version": calc.version,
            "dimension": calc.dimension,
        })
    return {"versions": result}
