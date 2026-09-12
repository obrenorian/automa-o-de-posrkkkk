from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from app.models import Post


REQUIRED_COLUMNS = ("id", "conta", "video", "legenda", "data", "hora")
SUPPORTED_VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".m4v"})
OPTIONAL_ACCOUNT_ID_FIELDS = ("business_id", "page_id", "asset_id")


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    message: str
    row: int | None = None
    field: str | None = None
    severity: str = "ERROR"

    def __str__(self) -> str:
        location = ""
        if self.row is not None:
            location += f"linha {self.row}"
        if self.field:
            location += f", campo '{self.field}'" if location else f"campo '{self.field}'"
        return f"{self.severity}: {location + ': ' if location else ''}{self.message}"


@dataclass(slots=True)
class ValidationReport:
    posts: list[Post] = field(default_factory=list)
    accounts: dict[str, dict[str, str]] = field(default_factory=dict)
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "ERROR"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "WARNING"]

    @property
    def is_valid(self) -> bool:
        return not self.errors


def load_and_validate(
    csv_path: Path,
    accounts_path: Path,
    *,
    require_future_schedule: bool = True,
) -> ValidationReport:
    report = load_accounts_only(accounts_path)
    if report.errors:
        return report
    _load_posts(csv_path, report, require_future_schedule=require_future_schedule)
    return report


def load_accounts_only(accounts_path: Path) -> ValidationReport:
    report = ValidationReport()
    report.accounts = _load_accounts(accounts_path, report)
    return report


def _load_accounts(path: Path, report: ValidationReport) -> dict[str, dict[str, str]]:
    if not path.is_file():
        report.issues.append(ValidationIssue(f"arquivo de contas nao encontrado: {path}"))
        return {}

    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        report.issues.append(ValidationIssue(f"nao foi possivel ler accounts.json: {exc}"))
        return {}

    if not isinstance(raw, dict) or not raw:
        report.issues.append(ValidationIssue("accounts.json deve conter um objeto nao vazio"))
        return {}

    result: dict[str, dict[str, str]] = {}
    instagram_owners: dict[str, str] = {}
    for internal_name, settings in raw.items():
        if not isinstance(internal_name, str) or not internal_name.strip():
            report.issues.append(ValidationIssue("nome interno de conta vazio ou invalido"))
            continue
        if not isinstance(settings, dict):
            report.issues.append(ValidationIssue(
                f"configuracao da conta '{internal_name}' deve ser um objeto"
            ))
            continue
        instagram_name = settings.get("instagram_name")
        if not isinstance(instagram_name, str) or not instagram_name.strip():
            report.issues.append(ValidationIssue(
                f"conta '{internal_name}' nao possui instagram_name valido"
            ))
            continue
        key = internal_name.strip()
        handle = instagram_name.strip()
        normalized_handle = handle.casefold().lstrip("@")
        if normalized_handle in instagram_owners:
            report.issues.append(ValidationIssue(
                f"instagram_name '{handle}' esta mapeado tambem por "
                f"'{instagram_owners[normalized_handle]}'"
            ))
            continue
        instagram_owners[normalized_handle] = key
        normalized_settings = {"instagram_name": handle}
        invalid_settings = False
        for field_name in OPTIONAL_ACCOUNT_ID_FIELDS:
            field_value = settings.get(field_name)
            if field_value is None:
                continue
            if not isinstance(field_value, str) or not field_value.strip().isdigit():
                report.issues.append(ValidationIssue(
                    f"conta '{internal_name}' possui {field_name} invalido; "
                    "use apenas digitos entre aspas"
                ))
                invalid_settings = True
                continue
            normalized_settings[field_name] = field_value.strip()
        if invalid_settings:
            continue
        result[key] = normalized_settings
    return result


def _load_posts(
    path: Path, report: ValidationReport, *, require_future_schedule: bool
) -> None:
    if not path.is_file():
        report.issues.append(ValidationIssue(f"arquivo CSV nao encontrado: {path}"))
        return

    try:
        csv_file = path.open("r", encoding="utf-8-sig", newline="")
    except (OSError, UnicodeError) as exc:
        report.issues.append(ValidationIssue(f"nao foi possivel abrir o CSV: {exc}"))
        return

    seen_ids: dict[str, int] = {}
    seen_videos: dict[str, int] = {}
    with csv_file:
        try:
            reader = csv.DictReader(csv_file)
            columns = tuple(reader.fieldnames or ())
            missing = [name for name in REQUIRED_COLUMNS if name not in columns]
            if missing:
                report.issues.append(ValidationIssue(
                    "colunas obrigatorias ausentes: " + ", ".join(missing)
                ))
                return

            for row_number, row in enumerate(reader, start=2):
                post = _validate_row(
                    row=row,
                    row_number=row_number,
                    csv_directory=path.resolve().parent,
                    accounts=report.accounts,
                    seen_ids=seen_ids,
                    seen_videos=seen_videos,
                    report=report,
                    require_future_schedule=require_future_schedule,
                )
                if post is not None:
                    report.posts.append(post)
        except (csv.Error, UnicodeError) as exc:
            report.issues.append(ValidationIssue(f"CSV invalido: {exc}"))

    if not report.posts and not report.errors:
        report.issues.append(ValidationIssue("o CSV nao possui posts"))


def _validate_row(
    *,
    row: dict[str, str | None],
    row_number: int,
    csv_directory: Path,
    accounts: dict[str, dict[str, str]],
    seen_ids: dict[str, int],
    seen_videos: dict[str, int],
    report: ValidationReport,
    require_future_schedule: bool,
) -> Post | None:
    start_error_count = len(report.errors)

    post_id = (row.get("id") or "").strip()
    account = (row.get("conta") or "").strip()
    video_text = (row.get("video") or "").strip().strip('"')
    caption = row.get("legenda") or ""
    date_text = (row.get("data") or "").strip()
    time_text = (row.get("hora") or "").strip()

    if not post_id:
        _error(report, row_number, "id", "ID obrigatorio")
    elif post_id in seen_ids:
        _error(
            report,
            row_number,
            "id",
            f"ID duplicado; primeira ocorrencia na linha {seen_ids[post_id]}",
        )
    else:
        seen_ids[post_id] = row_number

    if not account:
        _error(report, row_number, "conta", "conta obrigatoria")
    elif account not in accounts:
        _error(report, row_number, "conta", f"conta '{account}' nao existe em accounts.json")

    video_path: Path | None = None
    if not video_text:
        _error(report, row_number, "video", "caminho do video obrigatorio")
    else:
        expanded = Path(os.path.expandvars(os.path.expanduser(video_text)))
        video_path = expanded if expanded.is_absolute() else csv_directory / expanded
        video_path = video_path.resolve()
        normalized_video = os.path.normcase(str(video_path))
        if normalized_video in seen_videos:
            _error(
                report,
                row_number,
                "video",
                f"video duplicado; primeira ocorrencia na linha {seen_videos[normalized_video]}",
            )
        else:
            seen_videos[normalized_video] = row_number
        if video_path.suffix.casefold() not in SUPPORTED_VIDEO_EXTENSIONS:
            _error(
                report,
                row_number,
                "video",
                "extensao nao suportada (use .mp4, .mov ou .m4v)",
            )
        if not video_path.is_file():
            _error(report, row_number, "video", f"arquivo nao encontrado: {video_path}")

    parsed_date = None
    parsed_time = None
    try:
        parsed_date = datetime.strptime(date_text, "%d/%m/%Y").date()
    except ValueError:
        _error(report, row_number, "data", "data invalida; use DD/MM/AAAA")
    try:
        parsed_time = datetime.strptime(time_text, "%H:%M").time()
    except ValueError:
        _error(report, row_number, "hora", "hora invalida; use HH:MM no formato 24 horas")

    if require_future_schedule and parsed_date is not None and parsed_time is not None:
        local_now = datetime.now().astimezone().replace(tzinfo=None)
        if datetime.combine(parsed_date, parsed_time) <= local_now:
            _error(report, row_number, "data", "data e hora de agendamento estao no passado")

    if len(report.errors) != start_error_count:
        return None
    assert video_path is not None and parsed_date is not None and parsed_time is not None
    return Post(
        id=post_id,
        conta=account,
        video=video_path,
        legenda=caption,
        data=parsed_date,
        hora=parsed_time,
    )


def _error(report: ValidationReport, row: int, field: str, message: str) -> None:
    report.issues.append(ValidationIssue(message=message, row=row, field=field))
