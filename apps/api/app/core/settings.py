from dataclasses import dataclass, field
import os
from pathlib import Path


def _default_project_dir() -> Path:
    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class AppSettings:
    app_name: str = field(
        default_factory=lambda: os.getenv("MESO_APP_NAME", "Meso Options Analytics API"),
    )
    app_env: str = field(default_factory=lambda: os.getenv("MESO_APP_ENV", "development"))
    api_prefix: str = field(default_factory=lambda: os.getenv("MESO_API_PREFIX", "/api"))
    project_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv("MESO_PROJECT_DIR", str(_default_project_dir())),
        ),
    )
    config_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv(
                "MESO_CONFIG_DIR",
                str(_default_project_dir() / "app" / "config"),
            ),
        ),
    )
    data_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv("MESO_DATA_DIR", str(_default_project_dir() / "data")),
        ),
    )


settings = AppSettings()
