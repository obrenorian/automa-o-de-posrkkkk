from __future__ import annotations

import os
import subprocess
from pathlib import Path


def find_chrome_executable() -> Path:
    """Localiza uma instalacao normal do Google Chrome no Windows."""
    candidates = [
        Path(os.environ.get("PROGRAMFILES", ""))
        / "Google"
        / "Chrome"
        / "Application"
        / "chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", ""))
        / "Google"
        / "Chrome"
        / "Application"
        / "chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Google"
        / "Chrome"
        / "Application"
        / "chrome.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        "Google Chrome nao encontrado. Instale o Chrome ou informe um caminho valido."
    )


def launch_normal_chrome(profile_path: Path, url: str) -> subprocess.Popen[bytes]:
    """Abre Chrome sem Playwright para login/2FA exclusivamente manual."""
    chrome = find_chrome_executable()
    profile_path.mkdir(parents=True, exist_ok=True)
    return subprocess.Popen(
        [
            str(chrome),
            f"--user-data-dir={profile_path}",
            url,
        ],
        cwd=chrome.parent,
    )

