from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from app.models import Post, PostStatus


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS posts (
                    id TEXT PRIMARY KEY,
                    conta TEXT NOT NULL,
                    video TEXT NOT NULL,
                    legenda TEXT NOT NULL DEFAULT '',
                    data TEXT NOT NULL,
                    hora TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PENDING'
                        CHECK (status IN ('PENDING','PROCESSING','SCHEDULED','FAILED','SKIPPED')),
                    tentativas INTEGER NOT NULL DEFAULT 0 CHECK (tentativas >= 0),
                    erro TEXT,
                    timestamp_agendamento TEXT,
                    criado_em TEXT NOT NULL,
                    atualizado_em TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status)"
            )

    def recover_interrupted(self) -> int:
        """Devolve itens interrompidos para a fila ao iniciar a aplicacao."""
        now = _now_iso()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE posts
                SET status = ?, erro = ?, atualizado_em = ?
                WHERE status = ?
                """,
                (
                    PostStatus.PENDING,
                    "Execucao anterior interrompida durante o processamento",
                    now,
                    PostStatus.PROCESSING,
                ),
            )
            return cursor.rowcount

    def import_posts(self, posts: Iterable[Post]) -> tuple[int, int]:
        """Insere/atualiza o lote sem jamais reabrir um item SCHEDULED."""
        inserted = 0
        updated = 0
        now = _now_iso()
        with self.connect() as connection:
            for post in posts:
                current = connection.execute(
                    "SELECT status FROM posts WHERE id = ?", (post.id,)
                ).fetchone()
                values = (
                    post.conta,
                    str(post.video),
                    post.legenda,
                    post.data.isoformat(),
                    post.hora.strftime("%H:%M"),
                    now,
                    post.id,
                )
                if current is None:
                    connection.execute(
                        """
                        INSERT INTO posts (
                            id, conta, video, legenda, data, hora, status,
                            tentativas, erro, timestamp_agendamento, criado_em, atualizado_em
                        ) VALUES (?, ?, ?, ?, ?, ?, 'PENDING', 0, NULL, NULL, ?, ?)
                        """,
                        (
                            post.id,
                            post.conta,
                            str(post.video),
                            post.legenda,
                            post.data.isoformat(),
                            post.hora.strftime("%H:%M"),
                            now,
                            now,
                        ),
                    )
                    inserted += 1
                elif current["status"] != PostStatus.SCHEDULED:
                    connection.execute(
                        """
                        UPDATE posts
                        SET conta = ?, video = ?, legenda = ?, data = ?, hora = ?, atualizado_em = ?
                        WHERE id = ?
                        """,
                        values,
                    )
                    updated += 1
        return inserted, updated

    def summary(self) -> dict[str, int]:
        result = {status.value: 0 for status in PostStatus}
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT status, COUNT(*) AS total FROM posts GROUP BY status"
            ).fetchall()
        for row in rows:
            result[row["status"]] = row["total"]
        return result

    def reprocess_failures(self) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE posts
                SET status = 'PENDING', erro = NULL, atualizado_em = ?
                WHERE status = 'FAILED'
                """,
                (_now_iso(),),
            )
            return cursor.rowcount

    def pending(self, limit: int | None = None) -> list[sqlite3.Row]:
        sql = "SELECT * FROM posts WHERE status = 'PENDING' ORDER BY data, hora, id"
        parameters: tuple[int, ...] = ()
        if limit is not None:
            sql += " LIMIT ?"
            parameters = (limit,)
        with self.connect() as connection:
            return connection.execute(sql, parameters).fetchall()

    def status(self, post_id: str) -> str | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT status FROM posts WHERE id = ?", (post_id,)
            ).fetchone()
        return None if row is None else row["status"]

    def mark_processing(self, post_id: str) -> bool:
        now = _now_iso()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE posts
                SET status = 'PROCESSING', tentativas = tentativas + 1,
                    erro = NULL, atualizado_em = ?
                WHERE id = ? AND status IN ('PENDING', 'FAILED')
                """,
                (now, post_id),
            )
            return cursor.rowcount == 1

    def mark_scheduled(self, post_id: str) -> None:
        now = _now_iso()
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE posts
                SET status = 'SCHEDULED', erro = NULL,
                    timestamp_agendamento = ?, atualizado_em = ?
                WHERE id = ?
                """,
                (now, now, post_id),
            )

    def mark_failed(self, post_id: str, error: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE posts SET status = 'FAILED', erro = ?, atualizado_em = ?
                WHERE id = ?
                """,
                (error, _now_iso(), post_id),
            )

    def mark_skipped(self, post_id: str, reason: str) -> None:
        """Protege contra reenvio quando o clique ocorreu mas o retorno e incerto."""
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE posts SET status = 'SKIPPED', erro = ?, atualizado_em = ?
                WHERE id = ?
                """,
                (reason, _now_iso(), post_id),
            )


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
