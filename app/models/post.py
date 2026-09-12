from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time, datetime
from enum import StrEnum
from pathlib import Path


class PostStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SCHEDULED = "SCHEDULED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True, slots=True)
class Post:
    id: str
    conta: str
    video: Path
    legenda: str
    data: date
    hora: time

    @property
    def scheduled_for(self) -> datetime:
        return datetime.combine(self.data, self.hora)

    @property
    def formatted_schedule(self) -> str:
        return f"{self.data:%d/%m/%Y} {self.hora:%H:%M}"

