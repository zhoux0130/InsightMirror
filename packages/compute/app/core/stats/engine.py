"""Statistics engine for analyzing matched segments' future performance.

P1: Similarity-weighted probability
P1: Matching Quality Score
P2: Bootstrap confidence interval
"""

from dataclasses import dataclass
import numpy as np
from numpy.typing import NDArray
from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass
class FutureStats:
    """Statistics about future performance of matched segments."""
    count: int
    win_rate: float
    weighted_win_rate: float  # P1: similarity-weighted
    avg_return: float
    median_return: float
    max_return: float
    min_return: float
    avg_max_drawdown: float
    avg_max_profit: float
    quality_score: float  # P1: Matching Quality Score
    confidence_lower: float | None = None  # P2: Bootstrap CI
    confidence_upper: float | None = None


class StatsEngine:
    def __init__(self, db: Session):
        self.db = db

    def compute_future_stats(
        self,
        segment_ids: list[int],
        similarities: list[float],
        future_days: int = 20,
    ) -> FutureStats:
        """Compute future performance statistics for matched segments."""
        if not segment_ids:
            return FutureStats(
                count=0, win_rate=0.0, weighted_win_rate=0.0,
                avg_return=0.0, median_return=0.0,
                max_return=0.0, min_return=0.0,
                avg_max_drawdown=0.0, avg_max_profit=0.0,
                quality_score=0.0,
            )

        # Fetch labels from database
        labels = self._fetch_labels(segment_ids, future_days)

        if not labels:
            return FutureStats(
                count=0, win_rate=0.0, weighted_win_rate=0.0,
                avg_return=0.0, median_return=0.0,
                max_return=0.0, min_return=0.0,
                avg_max_drawdown=0.0, avg_max_profit=0.0,
                quality_score=0.0,
            )

        # Build arrays
        seg_id_to_sim = dict(zip(segment_ids, similarities))
        returns = []
        weights = []
        wins = []
        max_drawdowns = []
        max_profits = []

        for label in labels:
            seg_id, return_rate, max_dd, max_pf, win_flag = label
            if return_rate is None:
                continue
            returns.append(float(return_rate))
            weights.append(seg_id_to_sim.get(seg_id, 0.5))
            wins.append(1.0 if win_flag else 0.0)
            if max_dd is not None:
                max_drawdowns.append(float(max_dd))
            if max_pf is not None:
                max_profits.append(float(max_pf))

        if not returns:
            return FutureStats(
                count=0, win_rate=0.0, weighted_win_rate=0.0,
                avg_return=0.0, median_return=0.0,
                max_return=0.0, min_return=0.0,
                avg_max_drawdown=0.0, avg_max_profit=0.0,
                quality_score=0.0,
            )

        returns_arr = np.array(returns)
        weights_arr = np.array(weights)
        wins_arr = np.array(wins)

        # Basic stats
        win_rate = float(np.mean(wins_arr))

        # P1: Similarity-weighted win rate
        weight_sum = np.sum(weights_arr)
        weighted_win_rate = float(
            np.sum(wins_arr * weights_arr) / weight_sum
        ) if weight_sum > 0 else win_rate

        # P1: Matching Quality Score
        quality_score = self._compute_quality_score(
            similarities, returns_arr, weights_arr
        )

        result = FutureStats(
            count=len(returns),
            win_rate=win_rate,
            weighted_win_rate=weighted_win_rate,
            avg_return=float(np.mean(returns_arr)),
            median_return=float(np.median(returns_arr)),
            max_return=float(np.max(returns_arr)),
            min_return=float(np.min(returns_arr)),
            avg_max_drawdown=float(np.mean(max_drawdowns)) if max_drawdowns else 0.0,
            avg_max_profit=float(np.mean(max_profits)) if max_profits else 0.0,
            quality_score=quality_score,
        )

        # P2: Bootstrap confidence interval
        if len(returns) >= 10:
            ci_lower, ci_upper = self._bootstrap_ci(returns_arr, weights_arr)
            result.confidence_lower = ci_lower
            result.confidence_upper = ci_upper

        return result

    def _fetch_labels(self, segment_ids: list[int], future_days: int):
        """Fetch future labels from database."""
        sql = text("""
            SELECT segment_id, return_rate, max_drawdown, max_profit, win_flag
            FROM segment_future_label
            WHERE segment_id = ANY(:ids)
              AND future_days = :future_days
              AND label_status = 'filled'
        """)
        return self.db.execute(
            sql, {"ids": segment_ids, "future_days": future_days}
        ).fetchall()

    @staticmethod
    def _compute_quality_score(
        similarities: list[float],
        returns: NDArray[np.float64],
        weights: NDArray[np.float64],
    ) -> float:
        """P1: Matching Quality Score.

        Combines:
        - Mean similarity (higher = better matches)
        - Consistency of returns (lower std = more reliable)
        - Number of matches (more = more reliable)
        """
        sim_arr = np.array(similarities[:len(returns)])

        mean_sim = float(np.mean(sim_arr))
        return_std = float(np.std(returns))
        consistency = 1.0 / (1.0 + return_std)  # Higher when returns are consistent
        coverage = min(1.0, len(returns) / 30.0)  # Saturates at 30 matches

        # Weighted combination
        score = 0.4 * mean_sim + 0.35 * consistency + 0.25 * coverage
        return round(float(score), 4)

    @staticmethod
    def _bootstrap_ci(
        returns: NDArray[np.float64],
        weights: NDArray[np.float64],
        n_bootstrap: int = 1000,
        alpha: float = 0.05,
    ) -> tuple[float, float]:
        """P2: Bootstrap confidence interval for weighted mean return."""
        rng = np.random.default_rng(42)
        n = len(returns)
        boot_means = np.empty(n_bootstrap)

        for i in range(n_bootstrap):
            idx = rng.integers(0, n, size=n)
            boot_returns = returns[idx]
            boot_weights = weights[idx]
            w_sum = np.sum(boot_weights)
            if w_sum > 0:
                boot_means[i] = np.sum(boot_returns * boot_weights) / w_sum
            else:
                boot_means[i] = np.mean(boot_returns)

        lower = float(np.percentile(boot_means, 100 * alpha / 2))
        upper = float(np.percentile(boot_means, 100 * (1 - alpha / 2)))
        return lower, upper
