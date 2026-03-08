from __future__ import annotations

from datetime import date
import importlib.util
import json
from pathlib import Path

from sqlalchemy import select

from app.db.models import RawOptionSnapshot, SignalSnapshot
from app.db.session import build_database_url, create_engine_from_url, create_session_factory


def _load_cli_module():
    script_path = Path(__file__).resolve().parents[3] / "scripts" / "import_json_to_app_db.py"
    spec = importlib.util.spec_from_file_location("import_json_to_app_db", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load CLI script: {script_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_args_defaults_to_today() -> None:
    module = _load_cli_module()

    args = module.parse_args(["-f", "sample.json"])

    assert args.file == "sample.json"
    assert args.date == date.today()
    assert args.target_db == "apps/api/data/app.db"


def test_main_imports_returned_json_file_with_date_override(tmp_path: Path) -> None:
    module = _load_cli_module()
    source_path = tmp_path / "mkocr.json"
    target_path = tmp_path / "app.db"
    source_path.write_text(
        json.dumps(
            [
                {
                    "symbol": "SPY",
                    "PriceChgPct": "+0.9%",
                    "RelNotionalTo90D": 1.72,
                    "CallNotional": "1.58 B",
                    "PutNotional": "2.33 B",
                    "SingleLegPct": "81%",
                    "MultiLegPct": "19%",
                    "ContingentPct": "",
                    "RelVolTo90D": 1.3,
                    "CallVolume": 5637338,
                    "PutVolume": 7362239,
                    "PutPct": "56.6%",
                    "IV30": 19.1,
                    "IV30ChgPct": "-15.9%",
                    "HV20": 16.4,
                    "HV1Y": 15.4,
                    "IVR": "85%",
                    "IV_52W_P": "25%",
                    "Volume": 12999577,
                    "OI_PctRank": "23%",
                    "Earnings": "30-Apr-2026 BMO",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    exit_code = module.main(
        [
            "-d",
            "2026-03-10",
            "-f",
            str(source_path),
            "--target-db",
            str(target_path),
        ],
    )

    assert exit_code == 0

    engine = create_engine_from_url(build_database_url(target_path))
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        raw_snapshot = session.execute(select(RawOptionSnapshot)).scalar_one()
        signal_snapshot = session.execute(select(SignalSnapshot)).scalar_one()

    engine.dispose()

    assert raw_snapshot.trade_date.isoformat() == "2026-03-10"
    assert raw_snapshot.symbol == "SPY"
    assert raw_snapshot.call_notional == 1_580_000_000.0
    assert raw_snapshot.put_notional == 2_330_000_000.0
    assert raw_snapshot.iv30_chg_pct == -15.9
    assert raw_snapshot.earnings == "30-Apr-2026 BMO"
    assert raw_snapshot.raw_payload_json["PriceChgPct"] == "+0.9%"
    assert raw_snapshot.raw_payload_json["trade_date"] == "2026-03-10"
    assert signal_snapshot.trade_date.isoformat() == "2026-03-10"
    assert signal_snapshot.symbol == "SPY"
    assert signal_snapshot.batch_id == raw_snapshot.batch_id
