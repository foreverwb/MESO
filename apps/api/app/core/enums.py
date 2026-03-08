from enum import StrEnum


class EarningsRegime(StrEnum):
    PRE_EARNINGS = "pre_earnings"
    POST_EARNINGS = "post_earnings"
    NEUTRAL = "neutral"


class Quadrant(StrEnum):
    NEUTRAL = "neutral"
    BULLISH_EXPANSION = "bullish_expansion"
    BULLISH_COMPRESSION = "bullish_compression"
    BEARISH_EXPANSION = "bearish_expansion"
    BEARISH_COMPRESSION = "bearish_compression"


class SignalLabel(StrEnum):
    NEUTRAL = "neutral"
    DIRECTIONAL_BIAS = "directional_bias"
    VOLATILITY_BIAS = "volatility_bias"
    TREND_CHANGE = "trend_change"


class ProbabilityTier(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
