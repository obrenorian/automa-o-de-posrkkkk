from __future__ import annotations

import logging
import tempfile
import unittest
from datetime import date, time
from pathlib import Path

from playwright.sync_api import sync_playwright

from app.automation.meta_business import MetaBusinessSuite


class MetaBusinessSuiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self) -> None:
        self.page = self.browser.new_page()
        self.logger = logging.getLogger("meta-business-test")

    def tearDown(self) -> None:
        self.page.close()

    def test_confirms_account_already_selected(self) -> None:
        self.page.set_content(
            '<div>Postar em</div>'
            '<button role="combobox" aria-label="Postar em">'
            'Achadinhos 01 e @achadinhos01</button>'
        )

        selected = MetaBusinessSuite(self.page, self.logger).select_instagram_account(
            "@achadinhos01"
        )

        self.assertIn("achadinhos01", selected)

    def test_selects_expected_account_from_options(self) -> None:
        self.page.set_content(
            """
            <div>Postar em</div>
            <button id="destination" role="combobox" aria-label="Postar em"
                    onclick="document.querySelector('#accounts').hidden=false">
              Outra pagina
            </button>
            <div id="accounts" role="listbox" hidden>
              <button role="option"
                      onclick="document.querySelector('#destination').textContent='Achadinhos 02 e @achadinhos02'; this.parentElement.hidden=true">
                Achadinhos 02 @achadinhos02
              </button>
            </div>
            """
        )

        selected = MetaBusinessSuite(self.page, self.logger).select_instagram_account(
            "@achadinhos02"
        )

        self.assertIn("achadinhos02", selected)

    def test_upload_sets_video_and_waits_until_next_is_enabled(self) -> None:
        self.page.set_content(
            """
            <input type="file" accept="video/mp4"
                   onchange="document.querySelector('#next').disabled=false">
            <button id="next" disabled>Avançar</button>
            """
        )
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / "video.mp4"
            video.write_bytes(b"fake-video")

            MetaBusinessSuite(self.page, self.logger).upload_video(video)

        self.assertTrue(self.page.locator("#next").is_enabled())

    def test_fills_and_confirms_caption(self) -> None:
        self.page.set_content(
            '<textarea placeholder="Informe os espectadores sobre o assunto do seu reel"></textarea>'
        )
        caption = "Legenda com emoji ✨ e\nduas linhas"

        MetaBusinessSuite(self.page, self.logger).fill_caption(caption)

        self.assertEqual(self.page.locator("textarea").input_value(), caption)

    def test_fills_real_meta_contenteditable_caption(self) -> None:
        self.page.set_content(
            """
            <div id="placeholder-abc">Informe os espectadores sobre o assunto do seu reel</div>
            <div contenteditable="true" role="textbox"
                 aria-describedby="placeholder-abc"
                 aria-label="Escreva na caixa de diálogo o texto a ser adicionado ao post."></div>
            """
        )
        caption = "Legenda real ✨"

        MetaBusinessSuite(self.page, self.logger).fill_caption(caption)

        self.assertEqual(
            self.page.locator('[contenteditable="true"]').inner_text(), caption
        )

    def test_waits_for_copyright_and_advances_once(self) -> None:
        self.page.set_content(
            """
            <div>Seu vídeo está seguro para ser publicado!</div>
            <h3 id="details">Detalhes do reel</h3>
            <button aria-label="Avançar"
                    onclick="this.dataset.clicked='yes'">›</button>
            <button id="footer-next"
                    onclick="document.querySelector('#details').remove(); document.body.insertAdjacentHTML('beforeend', '<button id=&quot;optimizations&quot;>Otimizações</button>')">Avançar</button>
            """
        )
        suite = MetaBusinessSuite(self.page, self.logger)

        suite.wait_copyright_check()
        suite.click_next_once()

        self.assertEqual(self.page.locator("#details").count(), 0)
        self.assertIsNone(
            self.page.get_by_role("button", name="Avançar").first.get_attribute(
                "data-clicked"
            )
        )

    def test_advances_from_edit_to_share(self) -> None:
        self.page.set_content(
            """
            <button id="optimizations">Otimizações</button>
            <button onclick="document.querySelector('#optimizations').remove(); document.body.insertAdjacentHTML('beforeend', '<h2>Opções de programação</h2>')">Avançar</button>
            """
        )

        MetaBusinessSuite(self.page, self.logger).click_next_to_share()

        self.assertTrue(
            self.page.get_by_role("heading", name="Opções de programação").is_visible()
        )

    def test_selects_schedule_tab_not_final_button(self) -> None:
        self.page.set_content(
            """
            <h2>Opções de programação</h2>
            <button id="schedule-tab"
                    onclick="document.body.insertAdjacentHTML('beforeend', '<div>Selecione uma data e hora no futuro para a publicação do seu reel.</div>')">
              Programar
            </button>
            <button id="final-schedule"
                    onclick="this.dataset.clicked='yes'">Programar</button>
            """
        )

        MetaBusinessSuite(self.page, self.logger).select_schedule_mode()

        self.assertIsNone(
            self.page.locator("#final-schedule").get_attribute("data-clicked")
        )

    def test_sets_schedule_on_all_selected_destinations(self) -> None:
        rows = "".join(
            """
            <section>
              <input placeholder="dd/mm/aaaa">
              <input role="spinbutton" aria-label="horas" aria-valuenow="1"
                     oninput="this.setAttribute('aria-valuenow', parseInt(this.value, 10))">
              <input role="spinbutton" aria-label="minutos" aria-valuenow="41"
                     oninput="this.setAttribute('aria-valuenow', parseInt(this.value, 10))">
            </section>
            """
            for _ in range(2)
        )
        self.page.set_content(rows)

        destinations = MetaBusinessSuite(
            self.page, self.logger
        ).set_schedule_datetime(date(2026, 9, 12), time(3, 5))

        self.assertEqual(destinations, 2)
        date_inputs = self.page.locator('input[placeholder="dd/mm/aaaa"]')
        self.assertEqual(
            [date_inputs.nth(index).input_value() for index in range(2)],
            ["12/09/2026", "12/09/2026"],
        )

    def test_clicks_final_schedule_and_requires_success_message(self) -> None:
        self.page.set_content(
            """
            <h2>Opções de programação</h2>
            <div>Selecione uma data e hora no futuro para a publicação do seu reel.</div>
            <button id="schedule-tab">Programar</button>
            <button id="final-schedule" onclick="this.remove(); document.body.insertAdjacentHTML('beforeend', '<div role=&quot;status&quot;>Seu reel foi programado com sucesso</div>')">Programar</button>
            """
        )
        suite = MetaBusinessSuite(self.page, self.logger)

        suite.click_final_schedule()
        confirmation = suite.verify_scheduled(timeout_ms=2_000)

        self.assertEqual(confirmation, "Seu reel foi programado com sucesso")
        self.assertEqual(self.page.locator("#final-schedule").count(), 0)


if __name__ == "__main__":
    unittest.main()
