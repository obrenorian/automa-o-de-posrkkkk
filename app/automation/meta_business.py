from __future__ import annotations

import logging
import re
from datetime import date, time
from time import monotonic

from pathlib import Path

from playwright.sync_api import (
    Locator,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    expect,
)

from app.automation import selectors


class ManualActionRequired(RuntimeError):
    """A interface exige login, 2FA, CAPTCHA ou outra acao humana."""


class MetaBusinessSuite:
    def __init__(self, page: Page, logger: logging.Logger) -> None:
        self.page = page
        self.logger = logger

    def test_session(self) -> bool:
        """Confirma sessao por elementos visiveis, nunca apenas pela URL."""
        if _any_visible(selectors.login_markers(self.page), timeout_each=1_000):
            raise ManualActionRequired(
                "Login da Meta necessario; conclua login/2FA/CAPTCHA manualmente."
            )

        if "/latest/reels_composer/" in self.page.url and _any_visible(
            selectors.reel_composer_markers(self.page), timeout_each=2_000
        ):
            self.logger.info("Sessao valida | tela=Criar reel")
            return True

        if _any_visible(
            selectors.authenticated_home_markers(self.page), timeout_each=3_000
        ):
            self.logger.info("Sessao valida | Meta Business Suite autenticado")
            return True

        raise RuntimeError(
            "Nao foi possivel confirmar a sessao pela interface visivel."
        )

    def create_reel(self) -> None:
        """Abre e confirma o compositor; nao seleciona conta nem envia video."""
        if "/latest/reels_composer/" in self.page.url and _any_visible(
            selectors.reel_composer_markers(self.page), timeout_each=1_000
        ):
            self.logger.info("Tela Criar reel ja estava aberta")
            return

        action = _first_visible(selectors.create_reel_actions(self.page), 4_000)
        if action is None:
            raise RuntimeError("Acao 'Criar reel' nao encontrada na pagina inicial.")

        self.logger.info("Abrindo Criar reel")
        action.click(timeout=15_000)
        try:
            self.page.wait_for_url(
                re.compile(r"/latest/reels_composer/", re.IGNORECASE),
                timeout=45_000,
                wait_until="domcontentloaded",
            )
        except PlaywrightTimeoutError:
            # Algumas variacoes atualizam o compositor sem uma navegacao completa.
            pass

        marker = _first_visible(selectors.reel_composer_markers(self.page), 8_000)
        if marker is None:
            raise RuntimeError(
                "O clique ocorreu, mas a tela 'Criar reel' nao foi confirmada."
            )
        self.logger.info("Criar reel confirmado | url=%s", self.page.url)

    def select_instagram_account(self, instagram_name: str) -> str:
        """Seleciona e confirma explicitamente o destino antes do upload."""
        expected_handle = instagram_name.strip().lstrip("@")
        if not expected_handle:
            raise ValueError("instagram_name vazio")

        control = _first_visible(
            selectors.publish_destination_controls(self.page), timeout_each=3_000
        )
        if control is None:
            raise RuntimeError("Controle associado a 'Postar em' nao encontrado.")

        selected_text = _visible_text(control)
        self.logger.info("Destino atual em 'Postar em': %s", selected_text or "(sem texto)")
        if _contains_handle(selected_text, expected_handle):
            self.logger.info("Instagram confirmado: @%s", expected_handle)
            return selected_text

        control.click(timeout=15_000)
        option = _first_visible(
            selectors.instagram_account_options(self.page, expected_handle),
            timeout_each=3_000,
        )
        if option is None:
            raise RuntimeError(
                f"Instagram '@{expected_handle}' nao apareceu nas opcoes de 'Postar em'."
            )

        option_text = _visible_text(option)
        self.logger.info("Selecionando destino: %s", option_text or f"@{expected_handle}")
        option.click(timeout=15_000)
        self.page.keyboard.press("Escape")

        # O menu pode recriar o controle apos a selecao; localize-o novamente.
        confirmed_control = _first_visible(
            selectors.publish_destination_controls(self.page), timeout_each=3_000
        )
        confirmed_text = _visible_text(confirmed_control) if confirmed_control else ""
        if not _contains_handle(confirmed_text, expected_handle):
            raise RuntimeError(
                f"A opcao foi clicada, mas '@{expected_handle}' nao foi confirmada "
                f"em 'Postar em'. Texto atual: {confirmed_text or '(vazio)'}"
            )

        self.logger.info("Instagram confirmado apos selecao: @%s", expected_handle)
        return confirmed_text

    def upload_video(self, video_path: Path) -> None:
        """Envia um video e espera o compositor libera-lo para avancar."""
        video_path = video_path.resolve()
        if not video_path.is_file():
            raise FileNotFoundError(f"Video nao encontrado: {video_path}")

        self.logger.info("Enviando video: %s", video_path)
        file_input = _first_attached(selectors.video_file_inputs(self.page))
        if file_input is not None:
            file_input.set_input_files(str(video_path), timeout=30_000)
        else:
            add_video = _first_visible(
                selectors.add_video_actions(self.page), timeout_each=4_000
            )
            if add_video is None:
                raise RuntimeError("Acao 'Adicionar video' nao encontrada.")
            try:
                with self.page.expect_file_chooser(timeout=15_000) as chooser_info:
                    add_video.click(timeout=15_000)
                chooser_info.value.set_files(str(video_path))
            except PlaywrightTimeoutError as exc:
                raise RuntimeError(
                    "O clique em 'Adicionar video' nao abriu o seletor de arquivo."
                ) from exc

        self.logger.info("Upload iniciado; aguardando processamento do video")
        next_action = _first_visible(selectors.next_actions(self.page), 10_000)
        if next_action is None:
            raise RuntimeError("Botao 'Avancar' nao encontrado apos o upload.")
        try:
            expect(next_action).to_be_enabled(timeout=300_000)
        except AssertionError as exc:
            raise RuntimeError(
                "O video nao terminou de processar em 5 minutos ou foi rejeitado."
            ) from exc
        self.logger.info("Upload e processamento concluidos; Avancar esta habilitado")

    def fill_caption(self, caption: str) -> None:
        """Preenche a legenda e confirma o valor efetivamente presente no campo."""
        caption_input = _first_visible(
            selectors.caption_inputs(self.page), timeout_each=4_000
        )
        if caption_input is None:
            raise RuntimeError("Campo de legenda 'Texto/Descricao' nao encontrado.")

        self.logger.info("Inserindo legenda | caracteres=%d", len(caption))
        caption_input.fill(caption, timeout=15_000)
        actual_value = caption_input.evaluate(
            """element => {
                if ('value' in element) return element.value;
                return element.innerText || element.textContent || '';
            }"""
        )
        if str(actual_value).replace("\r\n", "\n") != caption.replace("\r\n", "\n"):
            raise RuntimeError(
                "A legenda foi preenchida, mas o conteudo exibido nao confere com o CSV."
            )
        self.logger.info("Legenda confirmada no compositor")

    def wait_copyright_check(self) -> None:
        """Espera a confirmacao positiva exibida pela interface da Meta."""
        self.logger.info("Aguardando verificacao de direitos autorais")
        safe_marker = _first_visible(
            selectors.copyright_safe_markers(self.page), timeout_each=150_000
        )
        if safe_marker is None:
            raise RuntimeError(
                "A verificacao de direitos autorais nao terminou com confirmacao "
                "positiva em 5 minutos."
            )
        self.logger.info("Verificacao de direitos autorais concluida sem problemas")

    def click_next_once(self) -> None:
        """Sai da etapa Criar e para na proxima etapa, sem presumir seu conteudo."""
        create_marker = _first_visible(selectors.create_step_markers(self.page), 3_000)
        next_action = _first_visible(selectors.next_actions(self.page), 4_000)
        if next_action is None:
            raise RuntimeError("Botao 'Avancar' nao encontrado na etapa Criar.")
        try:
            expect(next_action).to_be_enabled(timeout=30_000)
        except AssertionError as exc:
            raise RuntimeError("Botao 'Avancar' permaneceu desabilitado.") from exc

        self.logger.info("Clicando em Avancar uma vez")
        next_action.click(timeout=15_000)
        if create_marker is not None:
            try:
                expect(create_marker).to_be_hidden(timeout=60_000)
            except AssertionError as exc:
                raise RuntimeError(
                    "O clique ocorreu, mas a etapa Criar continuou visivel."
                ) from exc
        edit_marker = _first_visible(selectors.edit_step_markers(self.page), 15_000)
        if edit_marker is None:
            raise RuntimeError(
                "A etapa Criar fechou, mas a tela Editar nao foi confirmada."
            )
        self.logger.info("Etapa Editar confirmada")

    def click_next_to_share(self) -> None:
        """Avanca de Editar para Compartilhar e confirma opcoes de programacao."""
        edit_marker = _first_visible(selectors.edit_step_markers(self.page), 4_000)
        if edit_marker is None:
            raise RuntimeError("A etapa Editar nao esta visivel.")
        next_action = _first_visible(selectors.next_actions(self.page), 4_000)
        if next_action is None:
            raise RuntimeError("Botao 'Avancar' nao encontrado na etapa Editar.")
        self.logger.info("Avancando de Editar para Compartilhar")
        next_action.click(timeout=15_000)
        share_marker = _first_visible(selectors.share_step_markers(self.page), 15_000)
        if share_marker is None:
            raise RuntimeError(
                "A tela Compartilhar/Opcoes de programacao nao foi confirmada."
            )
        self.logger.info("Tela Compartilhar confirmada | Opcoes de programacao visiveis")

    def select_schedule_mode(self) -> None:
        """Seleciona a aba Programar, sem tocar no botao final homonimo."""
        share_marker = _first_visible(selectors.share_step_markers(self.page), 4_000)
        if share_marker is None:
            raise RuntimeError("Opcoes de programacao nao estao visiveis.")
        schedule_mode = _first_visible(
            selectors.schedule_mode_actions(self.page), 4_000
        )
        if schedule_mode is None:
            raise RuntimeError("Aba 'Programar' nao encontrada.")
        self.logger.info("Selecionando modo Programar")
        schedule_mode.click(timeout=15_000)
        form_marker = _first_visible(selectors.schedule_form_markers(self.page), 8_000)
        if form_marker is None:
            raise RuntimeError(
                "A aba Programar foi clicada, mas o formulario de data/hora "
                "nao foi confirmado."
            )
        self.logger.info("Formulario de agendamento confirmado")

    def set_schedule_datetime(self, schedule_date: date, schedule_time: time) -> int:
        """Preenche e confirma a mesma data/hora em cada destino selecionado."""
        date_inputs = selectors.schedule_date_inputs(self.page)
        hour_inputs = selectors.schedule_hour_inputs(self.page)
        minute_inputs = selectors.schedule_minute_inputs(self.page)
        field_counts = (
            date_inputs.count(),
            hour_inputs.count(),
            minute_inputs.count(),
        )
        if min(field_counts) == 0 or len(set(field_counts)) != 1:
            raise RuntimeError(
                "Quantidade inesperada de campos de agendamento "
                f"(datas={field_counts[0]}, horas={field_counts[1]}, "
                f"minutos={field_counts[2]})."
            )

        date_text = schedule_date.strftime("%d/%m/%Y")
        hour_text = f"{schedule_time.hour:02d}"
        minute_text = f"{schedule_time.minute:02d}"
        self.logger.info(
            "Preenchendo agendamento | destinos=%d | data=%s | hora=%s:%s",
            field_counts[0],
            date_text,
            hour_text,
            minute_text,
        )
        for index in range(field_counts[0]):
            # Os controles da Meta sao componentes React que podem substituir o
            # proprio <input> a cada alteracao. ``fill`` seguido de ``press`` no
            # mesmo Locator pode, alem de deixa-lo obsoleto, desmontar o composer.
            # Quando a data padrao ja e a desejada, nao a alteramos. Nos demais
            # casos, imitamos digitacao humana e usamos o teclado da pagina para
            # tirar o foco. Cada campo e localizado novamente apos a atualizacao.
            date_input = selectors.schedule_date_inputs(self.page).nth(index)
            actual_date = date_input.input_value(timeout=5_000)
            if not _date_value_matches(actual_date, schedule_date):
                _type_field_value(self.page, date_input, date_text)

            hour_input = selectors.schedule_hour_inputs(self.page).nth(index)
            _type_field_value(self.page, hour_input, hour_text)

            minute_input = selectors.schedule_minute_inputs(self.page).nth(index)
            _type_field_value(self.page, minute_input, minute_text)

            date_input = selectors.schedule_date_inputs(self.page).nth(index)
            actual_date = date_input.input_value(timeout=5_000)
            if not _date_value_matches(actual_date, schedule_date):
                raise RuntimeError(
                    f"Data nao confirmada no destino {index + 1}: {actual_date!r}"
                )
            hour_input = selectors.schedule_hour_inputs(self.page).nth(index)
            minute_input = selectors.schedule_minute_inputs(self.page).nth(index)
            _expect_spin_value(hour_input, schedule_time.hour, "hora", index)
            _expect_spin_value(minute_input, schedule_time.minute, "minuto", index)

        self.logger.info("Data e hora confirmadas em todos os destinos")
        return field_counts[0]

    def click_final_schedule(self) -> None:
        """Envia o agendamento uma unica vez, sem inferir sucesso pelo clique."""
        if _first_visible(selectors.schedule_form_markers(self.page), 3_000) is None:
            raise RuntimeError("Formulario de agendamento nao esta visivel.")
        action = _first_visible(selectors.final_schedule_actions(self.page), 4_000)
        if action is None:
            raise RuntimeError("Botao final 'Programar' nao encontrado.")
        if not action.is_enabled():
            raise RuntimeError("Botao final 'Programar' esta desabilitado.")
        self.logger.info("Enviando agendamento com um unico clique em Programar")
        action.click(timeout=15_000)

    def verify_scheduled(self, timeout_ms: int = 60_000) -> str:
        """Exige uma mensagem positiva da Meta antes de declarar sucesso."""
        marker = _wait_for_any_visible(
            self.page, selectors.schedule_success_markers(self.page), timeout_ms
        )
        if marker is None:
            raise RuntimeError(
                "Clique final enviado, mas nenhuma confirmacao inequivoca da "
                "Meta foi detectada. Verifique o Planner antes de tentar novamente."
            )
        confirmation = _visible_text(marker)
        self.logger.info("Confirmacao da Meta detectada | %s", confirmation)
        return confirmation


def _first_visible(candidates: tuple[Locator, ...], timeout_each: int) -> Locator | None:
    for candidate in candidates:
        try:
            locator = candidate.first
            locator.wait_for(state="visible", timeout=timeout_each)
            return locator
        except PlaywrightTimeoutError:
            continue
    return None


def _any_visible(candidates: tuple[Locator, ...], timeout_each: int) -> bool:
    return _first_visible(candidates, timeout_each) is not None


def _wait_for_any_visible(
    page: Page, candidates: tuple[Locator, ...], timeout_ms: int
) -> Locator | None:
    deadline = monotonic() + timeout_ms / 1_000
    while monotonic() < deadline:
        for candidate in candidates:
            try:
                locator = candidate.first
                if locator.count() and locator.is_visible():
                    return locator
            except Exception:
                # Durante navegacoes a Meta pode invalidar momentaneamente o DOM.
                continue
        page.wait_for_timeout(250)
    return None


def _first_attached(candidates: tuple[Locator, ...]) -> Locator | None:
    for candidate in candidates:
        locator = candidate.first
        if locator.count():
            return locator
    return None


def _visible_text(locator: Locator | None) -> str:
    if locator is None:
        return ""
    try:
        return " ".join(locator.inner_text(timeout=5_000).split())
    except PlaywrightTimeoutError:
        return ""


def _contains_handle(text: str, expected_handle: str) -> bool:
    return expected_handle.casefold() in text.casefold().replace("@", "")


def _date_value_matches(actual: str, expected: date) -> bool:
    normalized = " ".join(actual.casefold().split())
    numeric = expected.strftime("%d/%m/%Y").casefold()
    months = (
        "janeiro",
        "fevereiro",
        "março",
        "abril",
        "maio",
        "junho",
        "julho",
        "agosto",
        "setembro",
        "outubro",
        "novembro",
        "dezembro",
    )
    long_date = f"{expected.day} de {months[expected.month - 1]} de {expected.year}"
    return normalized in {numeric, long_date.casefold()}


def _type_field_value(page: Page, locator: Locator, value: str) -> None:
    """Digita num controle React sem reutilizar o Locator apos a mutacao."""
    locator.click(timeout=15_000)
    page.keyboard.press("Control+A")
    page.keyboard.type(value, delay=60)
    page.keyboard.press("Tab")


def _expect_spin_value(
    locator: Locator, expected: int, field_name: str, destination_index: int
) -> None:
    try:
        expect(locator).to_have_attribute(
            "aria-valuenow", str(expected), timeout=8_000
        )
    except AssertionError as exc:
        actual = locator.get_attribute("aria-valuenow")
        raise RuntimeError(
            f"{field_name.capitalize()} nao confirmado no destino "
            f"{destination_index + 1}: {actual!r}"
        ) from exc
