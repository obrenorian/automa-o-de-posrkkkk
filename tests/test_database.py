from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

from app.database import Database
from app.models import Post


class DatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "scheduler.db"
        self.database = Database(self.database_path)
        self.database.initialize()
        future = datetime.now() + timedelta(days=2)
        self.post = Post(
            id="1",
            conta="conta01",
            video=Path(self.temp_dir.name) / "video.mp4",
            legenda="Legenda",
            data=future.date(),
            hora=future.time().replace(second=0, microsecond=0),
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_import_is_idempotent_and_preserves_scheduled_status(self) -> None:
        inserted, updated = self.database.import_posts([self.post])
        self.assertEqual((inserted, updated), (1, 0))

        with closing(sqlite3.connect(self.database_path)) as connection:
            with connection:
                connection.execute(
                    "UPDATE posts SET status='SCHEDULED', "
                    "timestamp_agendamento='agora' WHERE id='1'"
                )

        changed_post = Post(
            id="1",
            conta="outra-conta",
            video=self.post.video,
            legenda="Alterada",
            data=self.post.data,
            hora=self.post.hora,
        )
        inserted, updated = self.database.import_posts([changed_post])

        self.assertEqual((inserted, updated), (0, 0))
        self.assertEqual(self.database.summary()["SCHEDULED"], 1)
        with closing(sqlite3.connect(self.database_path)) as connection:
            account = connection.execute(
                "SELECT conta FROM posts WHERE id='1'"
            ).fetchone()[0]
        self.assertEqual(account, "conta01")

    def test_processing_item_is_recovered_as_pending(self) -> None:
        self.database.import_posts([self.post])
        with closing(sqlite3.connect(self.database_path)) as connection:
            with connection:
                connection.execute("UPDATE posts SET status='PROCESSING' WHERE id='1'")

        recovered = self.database.recover_interrupted()

        self.assertEqual(recovered, 1)
        self.assertEqual(self.database.summary()["PENDING"], 1)


if __name__ == "__main__":
    unittest.main()
