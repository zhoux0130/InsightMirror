from abc import ABC, abstractmethod
import numpy as np
from numpy.typing import NDArray


class FeatureCalculator(ABC):
    """Abstract base class for feature vector calculation."""

    @property
    @abstractmethod
    def version(self) -> str:
        """Feature version identifier."""
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Output feature vector dimension."""
        ...

    @abstractmethod
    def calculate(
        self,
        close: NDArray[np.float64],
        volume: NDArray[np.float64],
        high: NDArray[np.float64] | None = None,
        low: NDArray[np.float64] | None = None,
    ) -> NDArray[np.float64]:
        """Calculate feature vector from OHLCV data.

        Args:
            close: Close prices array of length W (window_size).
            volume: Volume array of length W.
            high: High prices array (optional, for amplitude features).
            low: Low prices array (optional, for amplitude features).

        Returns:
            Feature vector of shape (dimension,).
        """
        ...
