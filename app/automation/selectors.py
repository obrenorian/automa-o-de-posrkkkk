"""Seletores semanticos observados na interface real do Meta Business Suite."""

from __future__ import annotations

import re

from playwright.sync_api import Locator, Page


def create_reel_actions(page: Page) -> tuple[Locator, ...]:
    """Candidatos, em ordem de preferencia, para a acao Criar reel."""
    name = re.compile(r"^\s*criar reel\s*$", re.IGNORECASE)
    return (
        page.get_by_role("button", name=name),
        page.get_by_role("link", name=name),
        page.get_by_text(name, exact=True),
    )


def reel_composer_markers(page: Page) -> tuple[Locator, ...]:
    """Marcadores inequivocos da tela inicial do compositor de Reel."""
    title = re.compile(r"^\s*criar reel\s*$", re.IGNORECASE)
    add_video = re.compile(r"^\s*adicionar video\s*$", re.IGNORECASE)
    return (
        page.get_by_role("heading", name=title),
        page.get_by_text(title, exact=True),
        page.get_by_role("button", name=add_video),
        page.get_by_text(add_video, exact=True),
    )


def authenticated_home_markers(page: Page) -> tuple[Locator, ...]:
    return (
        page.get_by_role(
            "heading", name=re.compile(r"^\s*p[aá]gina inicial\s*$", re.IGNORECASE)
        ),
        page.get_by_text(
            re.compile(r"^\s*p[aá]gina inicial\s*$", re.IGNORECASE), exact=True
        ),
        *create_reel_actions(page),
    )


def login_markers(page: Page) -> tuple[Locator, ...]:
    return (
        page.locator('input[type="password"]'),
        page.get_by_role(
            "button", name=re.compile(r"continuar com (o )?facebook", re.IGNORECASE)
        ),
        page.get_by_role(
            "button", name=re.compile(r"continuar com (o )?instagram", re.IGNORECASE)
        ),
    )


def publish_destination_controls(page: Page) -> tuple[Locator, ...]:
    """Controle imediatamente associado ao rotulo 'Postar em'."""
    label_pattern = re.compile(r"^\s*postar em\s*$", re.IGNORECASE)
    accessible_pattern = re.compile(r"postar em", re.IGNORECASE)
    label = page.get_by_text(label_pattern, exact=True).first
    return (
        page.get_by_role("combobox", name=accessible_pattern),
        page.get_by_label(accessible_pattern),
        label.locator("xpath=following::*[@role='combobox'][1]"),
        label.locator(
            "xpath=following::*[@aria-haspopup='listbox' or @aria-haspopup='menu'][1]"
        ),
        label.locator("xpath=following::*[self::button or @role='button'][1]"),
    )


def instagram_account_options(page: Page, instagram_name: str) -> tuple[Locator, ...]:
    handle = instagram_name.strip().lstrip("@")
    pattern = re.compile(re.escape(handle), re.IGNORECASE)
    return (
        page.get_by_role("option", name=pattern),
        page.get_by_role("menuitem", name=pattern),
        page.get_by_role("checkbox", name=pattern),
        page.get_by_role("button", name=pattern),
        page.get_by_text(pattern, exact=False),
    )


def add_video_actions(page: Page) -> tuple[Locator, ...]:
    pattern = re.compile(r"^\s*adicionar v[ií]deo\s*$", re.IGNORECASE)
    return (
        page.get_by_role("button", name=pattern),
        page.get_by_text(pattern, exact=True),
    )


def video_file_inputs(page: Page) -> tuple[Locator, ...]:
    return (
        page.locator('input[type="file"][accept*="video" i]'),
        page.locator('input[type="file"][accept*=".mp4" i]'),
    )


def next_actions(page: Page) -> tuple[Locator, ...]:
    pattern = re.compile(r"^\s*avan[cç]ar\s*$", re.IGNORECASE)
    return (
        # O seletor de miniatura tambem possui uma seta com nome acessivel
        # "Avancar". O botao principal do rodape vem por ultimo no DOM.
        page.get_by_role("button", name=pattern).last,
        page.get_by_text(pattern, exact=True).last,
    )


def caption_inputs(page: Page) -> tuple[Locator, ...]:
    placeholder = re.compile(
        r"informe os espectadores sobre o assunto do seu reel", re.IGNORECASE
    )
    accessible_name = re.compile(r"^(texto|descri[cç][aã]o)", re.IGNORECASE)
    meta_editor_name = re.compile(
        r"texto a ser adicionado ao post", re.IGNORECASE
    )
    return (
        page.get_by_role("textbox", name=meta_editor_name),
        page.get_by_placeholder(placeholder),
        page.get_by_role("textbox", name=accessible_name),
        page.get_by_label(accessible_name),
        page.locator(
            '[contenteditable="true"][aria-describedby^="placeholder-"]'
        ),
    )


def copyright_safe_markers(page: Page) -> tuple[Locator, ...]:
    return (
        page.get_by_text(
            re.compile(r"seu v[ií]deo est[aá] seguro para ser publicado", re.IGNORECASE)
        ),
        page.get_by_text(
            re.compile(
                r"nenhum problema de direitos autorais foi encontrado", re.IGNORECASE
            )
        ),
    )


def create_step_markers(page: Page) -> tuple[Locator, ...]:
    return (
        page.get_by_role(
            "heading", name=re.compile(r"^\s*detalhes do reel\s*$", re.IGNORECASE)
        ),
        page.get_by_text(
            re.compile(r"^\s*detalhes do reel\s*$", re.IGNORECASE), exact=True
        ),
    )


def edit_step_markers(page: Page) -> tuple[Locator, ...]:
    return (
        page.get_by_role(
            "button", name=re.compile(r"^\s*otimiza[cç][oõ]es\s*$", re.IGNORECASE)
        ),
        page.get_by_text(
            re.compile(r"^\s*otimiza[cç][oõ]es\s*$", re.IGNORECASE), exact=True
        ),
        page.get_by_role(
            "button", name=re.compile(r"^\s*cortar\s*$", re.IGNORECASE)
        ),
    )


def share_step_markers(page: Page) -> tuple[Locator, ...]:
    options = re.compile(r"^\s*op[cç][oõ]es de programa[cç][aã]o\s*$", re.IGNORECASE)
    schedule = re.compile(r"^\s*programar\s*$", re.IGNORECASE)
    return (
        page.get_by_role("heading", name=options),
        page.get_by_text(options, exact=True),
        page.get_by_role("button", name=schedule),
        page.get_by_text(schedule, exact=True),
    )


def schedule_mode_actions(page: Page) -> tuple[Locator, ...]:
    pattern = re.compile(r"^\s*programar\s*$", re.IGNORECASE)
    return (
        # Antes de selecionar o modo, este e o botao da aba. Depois surge um
        # segundo "Programar" no rodape, que jamais deve ser usado aqui.
        page.get_by_role("button", name=pattern).first,
        page.get_by_text(pattern, exact=True).first,
    )


def schedule_form_markers(page: Page) -> tuple[Locator, ...]:
    instruction = re.compile(
        r"selecione uma data e hora no futuro para a publica[cç][aã]o do seu reel",
        re.IGNORECASE,
    )
    active_times = re.compile(r"^\s*hor[aá]rios ativos\s*$", re.IGNORECASE)
    return (
        page.get_by_text(instruction),
        page.get_by_role("button", name=active_times),
        page.get_by_text(active_times, exact=True),
    )


def schedule_date_inputs(page: Page) -> Locator:
    return page.locator('input[placeholder="dd/mm/aaaa" i]')


def schedule_hour_inputs(page: Page) -> Locator:
    return page.get_by_role(
        "spinbutton", name=re.compile(r"^\s*horas\s*$", re.IGNORECASE)
    )


def schedule_minute_inputs(page: Page) -> Locator:
    return page.get_by_role(
        "spinbutton", name=re.compile(r"^\s*minutos\s*$", re.IGNORECASE)
    )


def final_schedule_actions(page: Page) -> tuple[Locator, ...]:
    pattern = re.compile(r"^\s*programar\s*$", re.IGNORECASE)
    return (
        # Na tela final existem a aba e o botao de envio com o mesmo nome.
        # O botao de envio fica por ultimo no DOM.
        page.get_by_role("button", name=pattern).last,
        page.get_by_text(pattern, exact=True).last,
    )


def schedule_success_markers(page: Page) -> tuple[Locator, ...]:
    success = re.compile(
        r"(?:seu|o)?\s*reel\s+(?:foi\s+)?(?:programad[oa]|agendad[oa])"
        r"(?:\s+com\s+sucesso)?|"
        r"publica[cç][aã]o\s+(?:foi\s+)?(?:programada|agendada)"
        r"(?:\s+com\s+sucesso)?|"
        r"reel\s+(?:was\s+)?scheduled(?:\s+successfully)?",
        re.IGNORECASE,
    )
    return (
        page.get_by_role("status").filter(has_text=success),
        page.get_by_role("alert").filter(has_text=success),
        page.get_by_text(success),
    )
