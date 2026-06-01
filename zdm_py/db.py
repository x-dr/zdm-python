from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Collection, Iterator

from .models import Zdm

DB_PATH = Path("database.db")


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        init_db(conn)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ZDM (
            article_id TEXT PRIMARY KEY,
            article_title TEXT,
            article_url TEXT,
            article_pic_url TEXT,
            article_price TEXT,
            voted TEXT,
            article_comment TEXT,
            article_mall TEXT,
            article_time TEXT,
            pushed INTEGER DEFAULT 0
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_zdm_pushed ON ZDM(pushed)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_zdm_article_time ON ZDM(article_time)")


def save_or_update_batch(items: Collection[Zdm]) -> None:
    if not items:
        return
    with connect() as conn:
        conn.executemany(
            """
            INSERT INTO ZDM (
                article_id, article_title, article_url, article_pic_url,
                article_price, voted, article_comment, article_mall,
                article_time, pushed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(article_id) DO UPDATE SET
                article_title=excluded.article_title,
                article_url=excluded.article_url,
                article_pic_url=excluded.article_pic_url,
                article_price=excluded.article_price,
                voted=excluded.voted,
                article_comment=excluded.article_comment,
                article_mall=excluded.article_mall,
                article_time=excluded.article_time,
                pushed=excluded.pushed
            """,
            [
                (
                    item.article_id,
                    item.title,
                    item.url,
                    item.pic_url,
                    item.price,
                    item.voted,
                    item.comments,
                    item.article_mall,
                    item.article_time,
                    1 if item.pushed else 0,
                )
                for item in items
                if item.article_id
            ],
        )


def unpush() -> list[Zdm]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM ZDM WHERE pushed = 0").fetchall()
    return [Zdm.from_db_row(row) for row in rows]


def pushed_ids() -> set[str]:
    min_time = (datetime.now() - timedelta(days=31)).isoformat(timespec="seconds")
    with connect() as conn:
        rows = conn.execute(
            "SELECT article_id FROM ZDM WHERE pushed = 1 AND article_time > ?",
            (min_time,),
        ).fetchall()
    return {row["article_id"] for row in rows}
