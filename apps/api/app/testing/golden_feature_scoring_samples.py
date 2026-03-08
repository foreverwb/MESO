from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GoldenFeatureScoringSample:
    symbol: str
    trade_date: str
    expected_features: dict[str, float]
    expected_scores: dict[str, float]


GOLDEN_FEATURE_SCORING_TOLERANCE = 1e-6

GOLDEN_FEATURE_SCORING_SAMPLES: tuple[GoldenFeatureScoringSample, ...] = (
    GoldenFeatureScoringSample(
        symbol="XLV",
        trade_date="2026-03-09",
        expected_features={
            "vol_imb": -0.012341130963343862,
            "not_imb": -0.12426035502958577,
            "type_imb": -0.07949266540308901,
            "vol_gap_s": 0.2698043815782092,
            "iv_level": 0.6699999999999999,
            "imb_agree": 0.9440403879668791,
            "money_rich": 0.0,
        },
        expected_scores={
            "s_dir": -6.041612011421481,
            "s_vol": 16.798284082948427,
            "s_conf": 81.65953625823904,
            "s_pers": 35.61409451019583,
        },
    ),
    GoldenFeatureScoringSample(
        symbol="CSCO",
        trade_date="2026-03-09",
        expected_features={
            "vol_imb": 0.1274864141033275,
            "not_imb": 0.4490785645004849,
            "type_imb": 0.3204417043416219,
            "vol_gap_s": -0.12064057136458751,
            "iv_level": 0.615,
            "imb_agree": 0.8392039248014214,
            "money_rich": -0.26826398659467926,
        },
        expected_scores={
            "s_dir": 22.87851099348061,
            "s_vol": 2.3232394464542576,
            "s_conf": 81.75065749649568,
            "s_pers": 23.88680348671212,
        },
    ),
    GoldenFeatureScoringSample(
        symbol="KLAC",
        trade_date="2026-03-09",
        expected_features={
            "vol_imb": -0.4017895185341279,
            "not_imb": -0.30649350649350643,
            "type_imb": -0.34461191130975505,
            "vol_gap_s": 0.3363998018333461,
            "iv_level": 0.845,
            "imb_agree": 0.9523519939796893,
            "money_rich": -0.051735674399188865,
        },
        expected_scores={
            "s_dir": -23.50862027975582,
            "s_vol": 26.29278521476473,
            "s_conf": 71.57091754081804,
            "s_pers": 70.60944571031365,
        },
    ),
    GoldenFeatureScoringSample(
        symbol="APH",
        trade_date="2026-03-09",
        expected_features={
            "vol_imb": -0.49783549783533204,
            "not_imb": -0.4397321428571426,
            "type_imb": -0.4629734848484184,
            "vol_gap_s": 0.11313044349976159,
            "iv_level": 0.9299999999999999,
            "imb_agree": 0.9709483225109052,
            "money_rich": -0.2682639865946794,
        },
        expected_scores={
            "s_dir": -32.2922098170486,
            "s_vol": 22.879508050050983,
            "s_conf": 96.27370806277263,
            "s_pers": 59.98888315697104,
        },
    ),
)
