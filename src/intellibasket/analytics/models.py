"""Configuration models for customer and basket analytics."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from intellibasket.config import PROJECT_ROOT


@dataclass(frozen=True, slots=True)
class RfmConfig:
    """Configuration for dynamic RFM scoring."""

    scoreBins: int = 5
    snapshotFrequency: str = "ME"
    minimumHistoryDays: int = 30


@dataclass(frozen=True, slots=True)
class BasketMiningConfig:
    """Configuration for global and segmented market basket mining."""

    globalMinSupport: float = 0.002
    segmentMinSupport: float = 0.01
    minConfidence: float = 0.25
    minLift: float = 1.05
    minBasketSize: int = 2
    minSegmentBaskets: int = 200
    maxProducts: int = 500
    maxItemsetLength: int = 3
    topRulesPerScope: int = 500


@dataclass(frozen=True, slots=True)
class AnalyticsConfig:
    """Combined analytics configuration."""

    rfm: RfmConfig
    basket: BasketMiningConfig

    @classmethod
    def fromToml(cls, configPath: Path | None = None) -> AnalyticsConfig:
        """Load analytics thresholds from the project TOML file."""
        effectivePath = configPath or PROJECT_ROOT / "config" / "analysis.toml"
        with effectivePath.open("rb") as configFile:
            rawConfig = tomllib.load(configFile)
        return cls(
            rfm=RfmConfig(**rawConfig.get("rfm", {})),
            basket=BasketMiningConfig(**rawConfig.get("basket", {})),
        )
