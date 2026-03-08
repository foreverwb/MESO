from __future__ import annotations

from fastapi import APIRouter

from app.core.enums import Quadrant, SignalLabel
from app.schemas.api_response import ApiMeta, ApiResponse, FiltersPayload
from app.services.config_loader import ConfigLoader


router = APIRouter(tags=["filters"])


@router.get("/filters", response_model=ApiResponse[FiltersPayload])
def get_filters() -> ApiResponse[FiltersPayload]:
    config_loader = ConfigLoader()
    ui_config = config_loader.get_ui()

    probability_tiers = [
        _normalize_probability_tier(probability_tier.value)
        for probability_tier in ui_config.default_filters.probability_tiers
    ]
    payload = FiltersPayload(
        event_statuses=["today", "future", "previous", "none"],
        quadrants=[
            Quadrant.BULLISH_EXPANSION.value,
            Quadrant.BULLISH_COMPRESSION.value,
            Quadrant.BEARISH_EXPANSION.value,
            Quadrant.BEARISH_COMPRESSION.value,
            SignalLabel.NEUTRAL.value,
        ],
        signal_labels=[
            SignalLabel.NEUTRAL.value,
            SignalLabel.DIRECTIONAL_BIAS.value,
            SignalLabel.VOLATILITY_BIAS.value,
        ],
        probability_tiers=["high", "mid", "low"],
        default_date_group_size_days=ui_config.default_date_group_size_days,
        default_filters={
            "earnings_regimes": [regime.value for regime in ui_config.default_filters.earnings_regimes],
            "quadrants": [quadrant.value for quadrant in ui_config.default_filters.quadrants],
            "probability_tiers": probability_tiers,
            "min_trade_count": ui_config.default_filters.min_trade_count,
        },
        highlight_rules={
            "default_signal_label": ui_config.highlight_rules.default_signal_label.value,
            "emphasis_probability_tier": _normalize_probability_tier(
                ui_config.highlight_rules.emphasis_probability_tier.value,
            ),
            "highlight_quadrants": [
                quadrant.value for quadrant in ui_config.highlight_rules.highlight_quadrants
            ],
        },
    )
    return ApiResponse(data=payload, meta=ApiMeta())


def _normalize_probability_tier(value: str) -> str:
    if value == "medium":
        return "mid"
    return value
