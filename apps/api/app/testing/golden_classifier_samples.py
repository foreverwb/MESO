from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


EventStatus = Literal["today", "future", "previous", "none"]


@dataclass(frozen=True, slots=True)
class GoldenClassifierSample:
    symbol: str
    trade_date: str
    event_status: EventStatus
    expected_quadrant: str
    expected_signal_label: str
    expected_prob_tier: str
    expected_watchlist: bool
    expected_event_regime: str


GOLDEN_CLASSIFIER_SAMPLES: tuple[GoldenClassifierSample, ...] = (
    GoldenClassifierSample(
        symbol="IGV",
        trade_date="2026-03-09",
        event_status="none",
        expected_quadrant="bullish_expansion",
        expected_signal_label="directional_bias",
        expected_prob_tier="mid",
        expected_watchlist=False,
        expected_event_regime="neutral",
    ),
    GoldenClassifierSample(
        symbol="CRWD",
        trade_date="2026-03-06",
        event_status="none",
        expected_quadrant="bullish_compression",
        expected_signal_label="directional_bias",
        expected_prob_tier="low",
        expected_watchlist=True,
        expected_event_regime="neutral",
    ),
    GoldenClassifierSample(
        symbol="APH",
        trade_date="2026-03-09",
        event_status="none",
        expected_quadrant="bearish_expansion",
        expected_signal_label="directional_bias",
        expected_prob_tier="mid",
        expected_watchlist=False,
        expected_event_regime="neutral",
    ),
    GoldenClassifierSample(
        symbol="IBM",
        trade_date="2026-03-05",
        event_status="none",
        expected_quadrant="bearish_compression",
        expected_signal_label="directional_bias",
        expected_prob_tier="low",
        expected_watchlist=True,
        expected_event_regime="neutral",
    ),
    GoldenClassifierSample(
        symbol="XLV",
        trade_date="2026-03-09",
        event_status="none",
        expected_quadrant="neutral",
        expected_signal_label="neutral",
        expected_prob_tier="low",
        expected_watchlist=False,
        expected_event_regime="neutral",
    ),
    GoldenClassifierSample(
        symbol="SMH",
        trade_date="2026-03-09",
        event_status="none",
        expected_quadrant="bearish_expansion",
        expected_signal_label="volatility_bias",
        expected_prob_tier="mid",
        expected_watchlist=False,
        expected_event_regime="neutral",
    ),
)
