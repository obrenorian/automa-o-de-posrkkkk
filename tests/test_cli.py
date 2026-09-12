from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from app.database import Database
from app.main import main


class CliTests(unittest.TestCase):
    def test_dry_run_imports_valid_csv_as_pending(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "video.mp4"
            video.write_bytes(b"fake-video-for-validation")
            accounts = root / "accounts.json"
            accounts.write_text(
                json.dumps({"conta01": {"instagram_name": "@conta01"}}),
                encoding="utf-8",
            )
            future = datetime.now().astimezone() + timedelta(days=2)
            csv_path = root / "posts.csv"
            csv_path.write_text(
                "id,conta,video,legenda,data,hora\n"
                f"1,conta01,video.mp4,Teste,{future:%d/%m/%Y},{future:%H:%M}\n",
                encoding="utf-8",
            )
            database_path = root / "scheduler.db"

            exit_code = main(
                [
                    "--csv",
                    str(csv_path),
                    "--accounts",
                    str(accounts),
                    "--database",
                    str(database_path),
                    "--dry-run",
                    "--limit",
                    "1",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(Database(database_path).summary()["PENDING"], 1)

    @patch("app.main._open_persistent_browser", return_value=0)
    def test_browser_only_does_not_require_csv(
        self, open_browser_mock
    ) -> None:
        exit_code = main(["--open-browser", "--csv", "arquivo-inexistente.csv"])

        self.assertEqual(exit_code, 0)
        open_browser_mock.assert_called_once()

    @patch("app.main._open_manual_login", return_value=0)
    def test_manual_login_does_not_require_csv(self, manual_login_mock) -> None:
        exit_code = main(["--manual-login", "--csv", "arquivo-inexistente.csv"])

        self.assertEqual(exit_code, 0)
        manual_login_mock.assert_called_once()

    @patch("app.main._run_meta_test", return_value=0)
    def test_create_reel_test_does_not_require_csv(self, meta_test_mock) -> None:
        exit_code = main(
            ["--test-create-reel", "--csv", "arquivo-inexistente.csv"]
        )

        self.assertEqual(exit_code, 0)
        meta_test_mock.assert_called_once()

    @patch("app.main._run_account_test", return_value=0)
    def test_account_test_does_not_require_csv(self, account_test_mock) -> None:
        exit_code = main(
            ["--test-account", "achadinhos01", "--csv", "arquivo-inexistente.csv"]
        )

        self.assertEqual(exit_code, 0)
        account_test_mock.assert_called_once()

    @patch("app.main._run_upload_test", return_value=0)
    def test_upload_routes_to_isolated_phase5(self, upload_test_mock) -> None:
        exit_code = main(["--test-upload", "1"])

        self.assertEqual(exit_code, 0)
        upload_test_mock.assert_called_once()

    @patch("app.main._run_caption_test", return_value=0)
    def test_caption_routes_to_isolated_phase6(self, caption_test_mock) -> None:
        exit_code = main(["--test-caption", "1"])

        self.assertEqual(exit_code, 0)
        caption_test_mock.assert_called_once()

    @patch("app.main._run_next_test", return_value=0)
    def test_next_routes_to_isolated_phase7a(self, next_test_mock) -> None:
        exit_code = main(["--test-next", "1"])

        self.assertEqual(exit_code, 0)
        next_test_mock.assert_called_once()

    @patch("app.main._run_next_test", return_value=0)
    def test_schedule_screen_routes_to_phase7b(self, next_test_mock) -> None:
        exit_code = main(["--test-schedule-screen", "1"])

        self.assertEqual(exit_code, 0)
        next_test_mock.assert_called_once()

    @patch("app.main._run_next_test", return_value=0)
    def test_schedule_form_routes_to_phase8a(self, next_test_mock) -> None:
        exit_code = main(["--test-schedule-form", "1"])

        self.assertEqual(exit_code, 0)
        next_test_mock.assert_called_once()

    @patch("app.main._run_next_test", return_value=0)
    def test_schedule_values_routes_to_phase8b(self, next_test_mock) -> None:
        exit_code = main(["--test-schedule-values", "1"])

        self.assertEqual(exit_code, 0)
        next_test_mock.assert_called_once()

    @patch("app.main._run_next_test", return_value=0)
    def test_schedule_post_routes_to_final_phase(self, next_test_mock) -> None:
        exit_code = main(["--schedule-post", "1"])

        self.assertEqual(exit_code, 0)
        next_test_mock.assert_called_once()

    @patch("app.main._run_schedule_batch", return_value=0)
    def test_schedule_batch_routes_to_queue_runner(self, batch_mock) -> None:
        exit_code = main(
            [
                "--schedule-batch",
                "--limit",
                "10",
                "--cooldown-every",
                "20",
                "--cooldown-seconds",
                "900",
            ]
        )

        self.assertEqual(exit_code, 0)
        batch_mock.assert_called_once()
        self.assertEqual(batch_mock.call_args.kwargs["cooldown_every"], 20)
        self.assertEqual(batch_mock.call_args.kwargs["cooldown_seconds"], 900)


if __name__ == "__main__":
    unittest.main()
