from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True, slots=True)
class AppConfig:
    csv_path: Path = PROJECT_ROOT / "posts.csv"
    accounts_path: Path = PROJECT_ROOT / "accounts.json"
    database_path: Path = PROJECT_ROOT / "scheduler.db"
    browser_profile_path: Path = PROJECT_ROOT / "browser_profile"
    logs_path: Path = PROJECT_ROOT / "logs"
    screenshots_path: Path = PROJECT_ROOT / "screenshots"
    business_suite_url: str = "https://business.facebook.com/latest/home"
    browser_channel: str | None = None
    headless: bool = False

    def ensure_directories(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.browser_profile_path.mkdir(parents=True, exist_ok=True)
        self.logs_path.mkdir(parents=True, exist_ok=True)
        self.screenshots_path.mkdir(parents=True, exist_ok=True)

