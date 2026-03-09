"""V1 Feature Calculator — 182-dimensional feature vector.

Composition:
  - Price pattern (P):  z-score normalized close prices → 60 dims
  - Return sequence (R): daily log returns → 59 dims
  - Volume profile (V): z-score normalized volume → 60 dims
  - Statistical signature (S): [skew, kurtosis, max_drawdown] → 3 dims

Sub-feature weights (P2 optimization):
  w_P = 1.0, w_R = 0.5, w_V = 0.7, w_S = 1.5

Total: 60 + 59 + 60 + 3 = 182 dims
"""

import numpy as np
from numpy.typing import NDArray
from scipy import stats as sp_stats

from app.core.feature.base import FeatureCalculator
from app.core.feature import registry


class V1FeatureCalculator(FeatureCalculator):
    WINDOW_SIZE = 60
    # Sub-feature weights (P2)
    W_P = 1.0
    W_R = 0.5
    W_V = 0.7
    W_S = 1.5

    @property
    def version(self) -> str:
        return "v1"

    @property
    def dimension(self) -> int:
        return 182

    def calculate(
        self,
        close: NDArray[np.float64],
        volume: NDArray[np.float64],
        high: NDArray[np.float64] | None = None,
        low: NDArray[np.float64] | None = None,
    ) -> NDArray[np.float64]:
        if len(close) < self.WINDOW_SIZE:
            raise ValueError(
                f"Need at least {self.WINDOW_SIZE} data points, got {len(close)}"
            )

        close = close[-self.WINDOW_SIZE:]
        volume = volume[-self.WINDOW_SIZE:]

        # --- Price pattern (P0: segment z-score normalization) ---
        price_feat = self._zscore(close)  # 60 dims

        # --- Return sequence ---
        log_returns = np.diff(np.log(close))  # 59 dims

        # --- Volume profile ---
        vol_feat = self._zscore(volume)  # 60 dims

        # --- Statistical signature ---
        skew = float(sp_stats.skew(log_returns))
        kurt = float(sp_stats.kurtosis(log_returns))
        max_dd = self._max_drawdown(close)
        stat_feat = np.array([skew, kurt, max_dd])  # 3 dims

        # --- Weighted concatenation (P2) ---
        feature = np.concatenate([
            price_feat * self.W_P,
            log_returns * self.W_R,
            vol_feat * self.W_V,
            stat_feat * self.W_S,
        ])

        # Final L2 normalization for cosine similarity
        norm = np.linalg.norm(feature)
        if norm > 0:
            feature = feature / norm

        return feature

    @staticmethod
    def _zscore(arr: NDArray[np.float64]) -> NDArray[np.float64]:
        """Segment z-score normalization (P0)."""
        mean = np.mean(arr)
        std = np.std(arr)
        if std < 1e-10:
            return np.zeros_like(arr)
        return (arr - mean) / std

    @staticmethod
    def _max_drawdown(prices: NDArray[np.float64]) -> float:
        """Calculate maximum drawdown from price series."""
        cummax = np.maximum.accumulate(prices)
        drawdowns = (prices - cummax) / cummax
        return float(np.min(drawdowns))


# Auto-register
_v1 = V1FeatureCalculator()
registry.register(_v1)
