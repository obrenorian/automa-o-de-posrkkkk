from __future__ import annotations

import argparse
import logging
from pathlib import Path

from app.config import AppConfig, PROJECT_ROOT
from app.database import Database
from app.logging_config import configure_logging
from app.services.input_loader import ValidationReport, load_and_validate


DEFAULT_BUSINESS_SUITE_URL = "https://business.facebook.com/latest/home"
DEFAULT_FACEBOOK_LOGIN_URL = "https://www.facebook.com/login/"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Agendador local de Reels pela interface do Meta Business Suite."
    )
    parser.add_argument("--csv", type=Path, default=PROJECT_ROOT / "posts.csv")
    parser.add_argument(
        "--accounts", type=Path, default=PROJECT_ROOT / "accounts.json"
    )
    parser.add_argument(
        "--database", type=Path, default=PROJECT_ROOT / "scheduler.db"
    )
    parser.add_argument(
        "--profile-dir", type=Path, default=PROJECT_ROOT / "browser_profile"
    )
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="abre o Meta Business Suite com o perfil persistente",
    )
    parser.add_argument(
        "--manual-login",
        action="store_true",
        help="abre Chrome normal, sem Playwright, para login e 2FA manuais",
    )
    parser.add_argument(
        "--test-session",
        action="store_true",
        help="confirma visualmente que a sessao persistente esta autenticada",
    )
    parser.add_argument(
        "--test-create-reel",
        action="store_true",
        help="abre e confirma Criar reel, sem upload ou publicacao",
    )
    parser.add_argument(
        "--test-account",
        metavar="CONTA",
        help="testa o destino Postar em para uma conta, sem upload/publicacao",
    )
    parser.add_argument(
        "--test-upload",
        metavar="ID",
        help="envia o video de um ID e espera processar, sem avancar/publicar",
    )
    parser.add_argument(
        "--test-caption",
        metavar="ID",
        help="envia o video e preenche a legenda, sem avancar/publicar",
    )
    parser.add_argument(
        "--test-next",
        metavar="ID",
        help="prepara o Reel e clica em Avancar uma vez, sem publicar",
    )
    parser.add_argument(
        "--test-schedule-screen",
        metavar="ID",
        help="chega ate Opcoes de programacao, sem selecionar/publicar",
    )
    parser.add_argument(
        "--test-schedule-form",
        metavar="ID",
        help="abre e registra o formulario Programar, sem preencher/confirmar",
    )
    parser.add_argument(
        "--test-schedule-values",
        metavar="ID",
        help="preenche data/hora em todos os destinos, sem confirmar",
    )
    parser.add_argument(
        "--schedule-post",
        metavar="ID",
        help="agenda um Reel real e exige confirmacao de sucesso da Meta",
    )
    parser.add_argument(
        "--browser-channel",
        choices=("chromium", "chrome", "msedge"),
        default="chromium",
        help="chromium usa o navegador instalado pelo Playwright",
    )
    parser.add_argument("--url", default=None)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="valida/importa e lista a fila, sem operar a interface do Meta",
    )
    parser.add_argument("--limit", type=positive_integer)
    parser.add_argument(
        "--manual-confirm",
        action="store_true",
        help="sera aplicado antes do clique final a partir da Fase 8",
    )
    parser.add_argument("--reprocess-failures", action="store_true")
    return parser


def positive_integer(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("o valor deve ser maior que zero")
    return parsed


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = AppConfig(
        csv_path=args.csv.resolve(),
        accounts_path=args.accounts.resolve(),
        database_path=args.database.resolve(),
        browser_profile_path=args.profile_dir.resolve(),
        business_suite_url=args.url or DEFAULT_BUSINESS_SUITE_URL,
        browser_channel=None if args.browser_channel == "chromium" else args.browser_channel,
    )
    config.ensure_directories()
    logger = configure_logging(config.logs_path)

    if args.manual_login:
        login_url = args.url or DEFAULT_FACEBOOK_LOGIN_URL
        return _open_manual_login(config, logger, login_url)

    if args.test_session or args.test_create_reel:
        return _run_meta_test(
            config,
            logger,
            create_reel=args.test_create_reel,
        )

    if args.test_account:
        return _run_account_test(config, logger, args.test_account)

    if args.test_upload:
        return _run_upload_test(config, logger, args.test_upload)

    if args.test_caption:
        return _run_caption_test(config, logger, args.test_caption)

    if args.test_next:
        return _run_next_test(config, logger, args.test_next, reach_share=False)

    if args.test_schedule_screen:
        return _run_next_test(
            config, logger, args.test_schedule_screen, reach_share=True
        )

    if args.test_schedule_form:
        return _run_next_test(
            config,
            logger,
            args.test_schedule_form,
            reach_share=True,
            open_schedule_form=True,
        )

    if args.test_schedule_values:
        return _run_next_test(
            config,
            logger,
            args.test_schedule_values,
            reach_share=True,
            open_schedule_form=True,
            set_schedule_values=True,
        )

    if args.schedule_post:
        return _run_next_test(
            config,
            logger,
            args.schedule_post,
            reach_share=True,
            open_schedule_form=True,
            set_schedule_values=True,
            confirm_schedule=True,
            manual_confirm=args.manual_confirm,
        )

    browser_only = args.open_browser and not (
        args.validate_only or args.dry_run or args.reprocess_failures
    )
    if browser_only:
        return _open_persistent_browser(config, logger)

    report = load_and_validate(config.csv_path, config.accounts_path)
    _print_report(report, logger)
    if not report.is_valid:
        logger.error("Validacao interrompida: corrija os erros antes de continuar.")
        return 2

    logger.info(
        "Validacao concluida | posts=%d | contas=%s",
        len(report.posts),
        ", ".join(sorted({post.conta for post in report.posts})),
    )

    if args.validate_only:
        return 0

    database = Database(config.database_path)
    database.initialize()
    recovered = database.recover_interrupted()
    if recovered:
        logger.warning("Itens PROCESSING recuperados para PENDING: %d", recovered)
    inserted, updated = database.import_posts(report.posts)
    logger.info("CSV importado | novos=%d | atualizados=%d", inserted, updated)

    if args.reprocess_failures:
        count = database.reprocess_failures()
        logger.info("Falhas devolvidas para PENDING: %d", count)

    _print_summary(database, logger)

    if args.dry_run:
        pending = database.pending(args.limit)
        logger.info("DRY-RUN | itens selecionados=%d", len(pending))
        for item in pending:
            logger.info(
                "DRY-RUN | ID=%s | conta=%s | video=%s | agendamento=%s %s",
                item["id"],
                item["conta"],
                item["video"],
                item["data"],
                item["hora"],
            )
        if args.manual_confirm:
            logger.info("--manual-confirm reconhecido; clique final nao existe na Fase 1.")

    if args.open_browser:
        return _open_persistent_browser(config, logger)

    return 0


def _open_manual_login(config: AppConfig, logger: logging.Logger, url: str) -> int:
    from app.automation.manual_browser import launch_normal_chrome

    logger.info(
        "Abrindo Chrome normal para login manual | perfil=%s", config.browser_profile_path
    )
    try:
        process = launch_normal_chrome(config.browser_profile_path, url)
        logger.info(
            "Conclua login, CAPTCHA e 2FA manualmente. "
            "Feche todas as janelas deste perfil ao terminar."
        )
        process.wait()
    except KeyboardInterrupt:
        logger.info("Espera interrompida; feche o Chrome antes de iniciar o robo.")
    except (OSError, FileNotFoundError) as exc:
        logger.error("Nao foi possivel abrir o Chrome normal: %s", exc)
        return 5
    return 0


def _run_meta_test(
    config: AppConfig, logger: logging.Logger, *, create_reel: bool
) -> int:
    from app.automation import PersistentBrowser
    from app.automation.meta_business import ManualActionRequired, MetaBusinessSuite

    browser = PersistentBrowser(
        config.browser_profile_path,
        headless=False,
        channel=config.browser_channel,
    )
    try:
        page = browser.open(config.business_suite_url)
        suite = MetaBusinessSuite(page, logger)
        suite.test_session()
        if create_reel:
            suite.create_reel()
        logger.info(
            "Teste concluido sem upload/publicacao. Pressione ENTER para fechar."
        )
        input()
    except ManualActionRequired as exc:
        logger.warning("Acao manual necessaria: %s", exc)
        logger.warning("Resolva na janela aberta e execute o teste novamente.")
        try:
            input("Pressione ENTER para fechar o navegador...")
        except (EOFError, KeyboardInterrupt):
            pass
        return 6
    except (EOFError, KeyboardInterrupt):
        logger.info("Fechamento solicitado pelo usuario.")
    except Exception as exc:
        logger.exception("Teste do Meta Business Suite falhou: %s", exc)
        return 7
    finally:
        browser.close()
    return 0


def _run_account_test(
    config: AppConfig, logger: logging.Logger, account_name: str
) -> int:
    from app.automation import PersistentBrowser
    from app.automation.account_urls import build_reels_composer_url
    from app.automation.meta_business import ManualActionRequired, MetaBusinessSuite
    from app.services.input_loader import load_accounts_only

    report = load_accounts_only(config.accounts_path)
    _print_report(report, logger)
    if not report.is_valid:
        return 2
    account = report.accounts.get(account_name)
    if account is None:
        logger.error(
            "Conta '%s' nao encontrada. Disponiveis: %s",
            account_name,
            ", ".join(sorted(report.accounts)),
        )
        return 2
    try:
        composer_url = build_reels_composer_url(account)
    except ValueError as exc:
        logger.error("Configuracao incompleta de '%s': %s", account_name, exc)
        return 2

    browser = PersistentBrowser(
        config.browser_profile_path,
        headless=False,
        channel=config.browser_channel,
    )
    page = None
    try:
        logger.info("Testando conta=%s | url=%s", account_name, composer_url)
        page = browser.open(composer_url)
        suite = MetaBusinessSuite(page, logger)
        suite.test_session()
        suite.create_reel()
        selected = suite.select_instagram_account(account["instagram_name"])
        logger.info(
            "FASE 4 OK | conta=%s | instagram=%s | destino=%s",
            account_name,
            account["instagram_name"],
            selected,
        )
        input("Teste concluido sem upload. Pressione ENTER para fechar...")
    except ManualActionRequired as exc:
        logger.warning("Acao manual necessaria: %s", exc)
        return 6
    except (EOFError, KeyboardInterrupt):
        logger.info("Fechamento solicitado pelo usuario.")
    except Exception as exc:
        logger.exception("Teste da conta '%s' falhou: %s", account_name, exc)
        if page is not None:
            _save_phase4_diagnostics(config, page, account_name, logger)
        return 8
    finally:
        browser.close()
    return 0


def _save_phase4_diagnostics(
    config: AppConfig, page, account_name: str, logger: logging.Logger
) -> None:
    safe_name = "".join(
        character if character.isalnum() or character in "-_" else "_"
        for character in account_name
    )
    screenshot_path = config.screenshots_path / f"phase4_{safe_name}.png"
    html_path = config.logs_path / f"phase4_{safe_name}.html"
    try:
        page.screenshot(path=str(screenshot_path), full_page=True)
        html_path.write_text(page.content(), encoding="utf-8")
        logger.error(
            "Diagnosticos salvos | screenshot=%s | html=%s",
            screenshot_path,
            html_path,
        )
    except Exception as exc:
        logger.error("Nao foi possivel salvar diagnosticos da Fase 4: %s", exc)


def _run_upload_test(config: AppConfig, logger: logging.Logger, post_id: str) -> int:
    from app.automation import PersistentBrowser
    from app.automation.account_urls import build_reels_composer_url
    from app.automation.meta_business import ManualActionRequired, MetaBusinessSuite

    report = load_and_validate(
        config.csv_path,
        config.accounts_path,
        require_future_schedule=False,
    )
    _print_report(report, logger)
    if not report.is_valid:
        return 2
    post = next((candidate for candidate in report.posts if candidate.id == post_id), None)
    if post is None:
        logger.error("Post ID '%s' nao encontrado no CSV.", post_id)
        return 2
    account = report.accounts[post.conta]
    try:
        composer_url = build_reels_composer_url(account)
    except ValueError as exc:
        logger.error("Configuracao incompleta de '%s': %s", post.conta, exc)
        return 2

    browser = PersistentBrowser(
        config.browser_profile_path,
        headless=False,
        channel=config.browser_channel,
    )
    page = None
    try:
        logger.info(
            "FASE 5 | ID=%s | conta=%s | video=%s",
            post.id,
            post.conta,
            post.video,
        )
        page = browser.open(composer_url)
        suite = MetaBusinessSuite(page, logger)
        suite.test_session()
        suite.create_reel()
        suite.select_instagram_account(account["instagram_name"])
        suite.upload_video(post.video)
        logger.info(
            "FASE 5 OK | ID=%s | upload processado | nenhum clique em Avancar",
            post.id,
        )
        input("Confira o video na tela. Pressione ENTER para fechar sem avancar...")
    except ManualActionRequired as exc:
        logger.warning("Acao manual necessaria: %s", exc)
        return 6
    except (EOFError, KeyboardInterrupt):
        logger.info("Fechamento solicitado pelo usuario.")
    except Exception as exc:
        logger.exception("Teste de upload do ID '%s' falhou: %s", post.id, exc)
        if page is not None:
            _save_phase_diagnostics(config, page, f"phase5_{post.id}", logger)
        return 9
    finally:
        browser.close()
    return 0


def _run_caption_test(config: AppConfig, logger: logging.Logger, post_id: str) -> int:
    from app.automation import PersistentBrowser
    from app.automation.account_urls import build_reels_composer_url
    from app.automation.meta_business import ManualActionRequired, MetaBusinessSuite

    report = load_and_validate(
        config.csv_path,
        config.accounts_path,
        require_future_schedule=False,
    )
    _print_report(report, logger)
    if not report.is_valid:
        return 2
    post = next((candidate for candidate in report.posts if candidate.id == post_id), None)
    if post is None:
        logger.error("Post ID '%s' nao encontrado no CSV.", post_id)
        return 2
    account = report.accounts[post.conta]
    try:
        composer_url = build_reels_composer_url(account)
    except ValueError as exc:
        logger.error("Configuracao incompleta de '%s': %s", post.conta, exc)
        return 2

    browser = PersistentBrowser(
        config.browser_profile_path,
        headless=False,
        channel=config.browser_channel,
    )
    page = None
    try:
        logger.info(
            "FASE 6 | ID=%s | conta=%s | video=%s",
            post.id,
            post.conta,
            post.video,
        )
        page = browser.open(composer_url)
        suite = MetaBusinessSuite(page, logger)
        suite.test_session()
        suite.create_reel()
        suite.select_instagram_account(account["instagram_name"])
        suite.upload_video(post.video)
        suite.fill_caption(post.legenda)
        logger.info(
            "FASE 6 OK | ID=%s | upload e legenda confirmados | sem Avancar",
            post.id,
        )
        input("Confira video e legenda. Pressione ENTER para fechar sem avancar...")
    except ManualActionRequired as exc:
        logger.warning("Acao manual necessaria: %s", exc)
        return 6
    except (EOFError, KeyboardInterrupt):
        logger.info("Fechamento solicitado pelo usuario.")
    except Exception as exc:
        logger.exception("Teste de legenda do ID '%s' falhou: %s", post.id, exc)
        if page is not None:
            _save_phase_diagnostics(config, page, f"phase6_{post.id}", logger)
        return 10
    finally:
        browser.close()
    return 0


def _run_next_test(
    config: AppConfig,
    logger: logging.Logger,
    post_id: str,
    *,
    reach_share: bool = False,
    open_schedule_form: bool = False,
    set_schedule_values: bool = False,
    confirm_schedule: bool = False,
    manual_confirm: bool = False,
) -> int:
    from app.automation import PersistentBrowser
    from app.automation.account_urls import build_reels_composer_url
    from app.automation.meta_business import ManualActionRequired, MetaBusinessSuite

    report = load_and_validate(
        config.csv_path,
        config.accounts_path,
        require_future_schedule=set_schedule_values,
    )
    _print_report(report, logger)
    if not report.is_valid:
        return 2
    post = next((candidate for candidate in report.posts if candidate.id == post_id), None)
    if post is None:
        logger.error("Post ID '%s' nao encontrado no CSV.", post_id)
        return 2
    account = report.accounts[post.conta]
    try:
        composer_url = build_reels_composer_url(account)
    except ValueError as exc:
        logger.error("Configuracao incompleta de '%s': %s", post.conta, exc)
        return 2

    database = None
    if confirm_schedule:
        database = Database(config.database_path)
        database.initialize()
        database.import_posts(report.posts)
        current_status = database.status(post.id)
        if current_status == "SCHEDULED":
            logger.warning(
                "ID=%s ja esta SCHEDULED; nenhum novo agendamento sera enviado.",
                post.id,
            )
            return 0
        if not database.mark_processing(post.id):
            logger.error(
                "ID=%s esta com status %s e foi bloqueado contra reenvio.",
                post.id,
                current_status,
            )
            return 12

    browser = PersistentBrowser(
        config.browser_profile_path,
        headless=False,
        channel=config.browser_channel,
    )
    page = None
    submitted = False
    try:
        phase = (
            "9"
            if confirm_schedule
            else (
                "8B"
                if set_schedule_values
                else ("8A" if open_schedule_form else ("7B" if reach_share else "7A"))
            )
        )
        logger.info("FASE %s | ID=%s | preparando etapa Criar", phase, post.id)
        page = browser.open(composer_url)
        suite = MetaBusinessSuite(page, logger)
        suite.test_session()
        suite.create_reel()
        suite.select_instagram_account(account["instagram_name"])
        suite.upload_video(post.video)
        suite.fill_caption(post.legenda)
        suite.wait_copyright_check()
        suite.click_next_once()
        if reach_share:
            suite.click_next_to_share()
            if open_schedule_form:
                suite.select_schedule_mode()
                if set_schedule_values:
                    destinations = suite.set_schedule_datetime(post.data, post.hora)
                    if confirm_schedule:
                        if manual_confirm:
                            answer = input(
                                "\nPost:\n"
                                f"{post.conta}\n{post.video.name}\n"
                                f"{post.formatted_schedule}\n\n"
                                "Confirmar agendamento? [S/N] "
                            ).strip().casefold()
                            if answer not in {"s", "sim"}:
                                database.mark_skipped(
                                    post.id, "Agendamento recusado no modo assistido"
                                )
                                logger.warning("ID=%s nao confirmado pelo usuario.", post.id)
                                return 0
                        submitted = True
                        suite.click_final_schedule()
                        confirmation = suite.verify_scheduled()
                        database.mark_scheduled(post.id)
                        _save_phase_snapshot(
                            config, page, f"phase9_scheduled_{post.id}", logger
                        )
                        logger.info(
                            "FASE 9 OK | ID=%s | destinos=%d | SCHEDULED | %s",
                            post.id,
                            destinations,
                            confirmation,
                        )
                    else:
                        _save_phase_snapshot(
                            config, page, f"phase8_values_{post.id}", logger
                        )
                        logger.info(
                            "FASE 8B OK | ID=%s | destinos=%d | data/hora confirmadas",
                            post.id,
                            destinations,
                        )
                        input(
                            "Confira os horarios. "
                            "Pressione ENTER para fechar sem programar..."
                        )
                else:
                    _save_phase_snapshot(
                        config, page, f"phase8_form_{post.id}", logger
                    )
                    logger.info(
                        "FASE 8A OK | ID=%s | formulario Programar aberto", post.id
                    )
                    input(
                        "Formulario registrado. "
                        "Pressione ENTER para fechar sem preencher ou programar..."
                    )
            else:
                logger.info(
                    "FASE 7B OK | ID=%s | Opcoes de programacao abertas", post.id
                )
                input(
                    "Confira Opcoes de programacao. "
                    "Pressione ENTER para fechar sem programar..."
                )
        else:
            logger.info("FASE 7A OK | ID=%s | tela Editar aberta", post.id)
            input("Confira Editar. Pressione ENTER para fechar sem continuar...")
    except ManualActionRequired as exc:
        logger.warning("Acao manual necessaria: %s", exc)
        if database is not None:
            database.mark_failed(post.id, str(exc))
        return 6
    except (EOFError, KeyboardInterrupt):
        logger.info("Fechamento solicitado pelo usuario.")
    except Exception as exc:
        logger.exception("Teste de Avancar do ID '%s' falhou: %s", post.id, exc)
        if database is not None:
            if submitted:
                database.mark_skipped(post.id, str(exc))
            else:
                database.mark_failed(post.id, str(exc))
        if page is not None:
            artifact_phase = (
                "phase9_schedule"
                if confirm_schedule
                else (
                    "phase8_values"
                    if set_schedule_values
                    else (
                        "phase8_form"
                        if open_schedule_form
                        else ("phase7b" if reach_share else "phase7a")
                    )
                )
            )
            _save_phase_diagnostics(config, page, f"{artifact_phase}_{post.id}", logger)
        return 11
    finally:
        browser.close()
    return 0


def _save_phase_diagnostics(
    config: AppConfig, page, artifact_name: str, logger: logging.Logger
) -> None:
    safe_name = "".join(
        character if character.isalnum() or character in "-_" else "_"
        for character in artifact_name
    )
    screenshot_path = config.screenshots_path / f"{safe_name}.png"
    html_path = config.logs_path / f"{safe_name}.html"
    try:
        page.screenshot(path=str(screenshot_path), full_page=True)
        html_path.write_text(page.content(), encoding="utf-8")
        logger.error(
            "Diagnosticos salvos | screenshot=%s | html=%s",
            screenshot_path,
            html_path,
        )
    except Exception as exc:
        logger.error("Nao foi possivel salvar diagnosticos: %s", exc)


def _save_phase_snapshot(
    config: AppConfig, page, artifact_name: str, logger: logging.Logger
) -> None:
    safe_name = "".join(
        character if character.isalnum() or character in "-_" else "_"
        for character in artifact_name
    )
    screenshot_path = config.screenshots_path / f"{safe_name}.png"
    html_path = config.logs_path / f"{safe_name}.html"
    page.screenshot(path=str(screenshot_path), full_page=True)
    html_path.write_text(page.content(), encoding="utf-8")
    logger.info(
        "Snapshot salvo | screenshot=%s | html=%s", screenshot_path, html_path
    )


def _open_persistent_browser(config: AppConfig, logger: logging.Logger) -> int:
    try:
        from app.automation import PersistentBrowser
    except ModuleNotFoundError as exc:
        if exc.name == "playwright":
            logger.error(
                "Playwright nao instalado. Execute: "
                "python -m pip install -r requirements.txt"
            )
            return 4
        raise
    logger.info("Abrindo navegador com perfil persistente: %s", config.browser_profile_path)
    browser = PersistentBrowser(
        config.browser_profile_path,
        headless=False,
        channel=config.browser_channel,
    )
    try:
        browser.open(config.business_suite_url)
        logger.info(
            "Navegador aberto. Faca login/2FA manualmente. "
            "Pressione ENTER neste terminal para fechar."
        )
        input()
    except (KeyboardInterrupt, EOFError):
        logger.info("Fechamento solicitado pelo usuario.")
    except Exception as exc:
        logger.exception("Falha ao abrir o navegador persistente: %s", exc)
        return 3
    finally:
        browser.close()
    return 0


def _print_report(report: ValidationReport, logger: logging.Logger) -> None:
    for issue in report.issues:
        if issue.severity == "WARNING":
            logger.warning("%s", issue)
        else:
            logger.error("%s", issue)


def _print_summary(database: Database, logger: logging.Logger) -> None:
    counts = database.summary()
    logger.info(
        "Status | pendentes=%d | processando=%d | agendados=%d | "
        "falharam=%d | ignorados=%d",
        counts["PENDING"],
        counts["PROCESSING"],
        counts["SCHEDULED"],
        counts["FAILED"],
        counts["SKIPPED"],
    )


if __name__ == "__main__":
    raise SystemExit(main())
