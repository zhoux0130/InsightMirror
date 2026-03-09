from abc import ABC, abstractmethod
from dataclasses import dataclass
import numpy as np
from numpy.typing import NDArray


@dataclass
class SearchResult:
    segment_id: int
    symbol: str
    start_date: str
    end_date: str
    distance: float
    similarity: float


@dataclass
class SearchRequest:
    query_vector: NDArray[np.float64]
    window_size: int = 60
    future_days: int = 20
    feature_version: str = "v1"
    top_k: int = 50
    query_end_date: str | None = None
    query_symbol: str | None = None


class SimilaritySearchEngine(ABC):
    @abstractmethod
    def search(self, request: SearchRequest) -> list[SearchResult]:
        ...
