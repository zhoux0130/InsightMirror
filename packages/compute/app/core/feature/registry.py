from app.core.feature.base import FeatureCalculator

_registry: dict[str, FeatureCalculator] = {}


def register(calculator: FeatureCalculator) -> None:
    _registry[calculator.version] = calculator


def get(version: str) -> FeatureCalculator:
    if version not in _registry:
        raise ValueError(f"Unknown feature version: {version}. Available: {list(_registry.keys())}")
    return _registry[version]


def list_versions() -> list[str]:
    return list(_registry.keys())
