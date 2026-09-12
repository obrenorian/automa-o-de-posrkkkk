from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from app.services.input_loader import load_and_validate


class InputLoaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.accounts = self.root / "accounts.json"
        self.accounts.write_text(
            json.dumps({"conta01": {"instagram_name": "@conta01"}}),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_valid_csv_resolves_relative_video_path(self) -> None:
        video = self.root / "video.mp4"
        video.write_bytes(b"fake-video-for-validation")
        future = datetime.now().astimezone() + timedelta(days=2)
        csv_path = self.root / "posts.csv"
        csv_path.write_text(
            "id,conta,video,legenda,data,hora\n"
            f'1,conta01,video.mp4,"Legenda, com virgula",'
            f"{future:%d/%m/%Y},{future:%H:%M}\n",
            encoding="utf-8",
        )

        report = load_and_validate(csv_path, self.accounts)

        self.assertTrue(report.is_valid, [str(issue) for issue in report.issues])
        self.assertEqual(len(report.posts), 1)
        self.assertEqual(report.posts[0].video, video.resolve())
        self.assertEqual(report.posts[0].legenda, "Legenda, com virgula")

    def test_duplicate_id_video_and_unknown_account_are_rejected(self) -> None:
        video = self.root / "video.mp4"
        video.write_bytes(b"fake-video-for-validation")
        future = datetime.now().astimezone() + timedelta(days=2)
        csv_path = self.root / "posts.csv"
        csv_path.write_text(
            "id,conta,video,legenda,data,hora\n"
            f"1,conta01,video.mp4,Primeiro,{future:%d/%m/%Y},{future:%H:%M}\n"
            f"1,inexistente,video.mp4,Segundo,{future:%d/%m/%Y},{future:%H:%M}\n",
            encoding="utf-8",
        )

        report = load_and_validate(csv_path, self.accounts)
        messages = "\n".join(str(issue) for issue in report.errors)

        self.assertFalse(report.is_valid)
        self.assertIn("ID duplicado", messages)
        self.assertIn("video duplicado", messages)
        self.assertIn("nao existe em accounts.json", messages)

    def test_past_schedule_is_rejected(self) -> None:
        video = self.root / "video.mp4"
        video.write_bytes(b"fake-video-for-validation")
        past = datetime.now().astimezone() - timedelta(days=1)
        csv_path = self.root / "posts.csv"
        csv_path.write_text(
            "id,conta,video,legenda,data,hora\n"
            f"1,conta01,video.mp4,Passado,{past:%d/%m/%Y},{past:%H:%M}\n",
            encoding="utf-8",
        )

        report = load_and_validate(csv_path, self.accounts)

        self.assertFalse(report.is_valid)
        self.assertTrue(
            any("no passado" in issue.message for issue in report.errors),
            [str(issue) for issue in report.errors],
        )


if __name__ == "__main__":
    unittest.main()

