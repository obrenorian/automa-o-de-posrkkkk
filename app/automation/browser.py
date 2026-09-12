from __future__ import annotations

from pathlib import Path
from types import TracebackType

from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright


class PersistentBrowser:
    """Contexto visivel com cookies/sessao gravados em user_data_dir."""

    def __init__(
        self,
        profile_path: Path,
        *,
        headless: bool = False,
        channel: str | None = None,
    ) -> None:
        self.profile_path = profile_path
        self.headless = headless
        self.channel = channel
        self._playwright: Playwright | None = None
        self.context: BrowserContext | None = None

    def open(self, url: str) -> Page:
        self.profile_path.mkdir(parents=True, exist_ok=True)
        self._playwright = sync_playwright().start()
        launch_options: dict[str, object] = {
            "user_data_dir": str(self.profile_path),
            "headless": self.headless,
            # Sem isto, o Playwright mantem uma area interna fixa (normalmente
            # 1280x720) mesmo quando o usuario maximiza a janela do Chrome.
            "no_viewport": True,
            "locale": "pt-BR",
            "args": ["--start-maximized"],
        }
        if self.channel:
            launch_options["channel"] = self.channel
        try:
            self.context = self._playwright.chromium.launch_persistent_context(
                **launch_options
            )
            page = self.context.pages[0] if self.context.pages else self.context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=90_000)
            return page
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        if self.context is not None:
            self.context.close()
            self.context = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None

    def __enter__(self) -> "PersistentBrowser":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
