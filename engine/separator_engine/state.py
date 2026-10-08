"""Crash-safe, additive application state. Audio never lives in this database."""

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any


class State:
    def __init__(self, root: Path):
        root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(root / "state.sqlite3", check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.executescript(
            "CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);"
            "CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, position INTEGER NOT NULL, "
            "payload TEXT NOT NULL);"
            "PRAGMA user_version=1;"
        )
        self.db.commit()

    def get(self, key: str, default: Any = None) -> Any:
        with self.lock:
            row = self.db.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
            return json.loads(row[0]) if row else default

    def put(self, key: str, value: Any) -> None:
        with self.lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO kv VALUES (?, ?)", (key, json.dumps(value)))

    def jobs(self) -> list[dict]:
        with self.lock:
            return [json.loads(r[0]) for r in self.db.execute("SELECT payload FROM jobs ORDER BY position")]

    def save_job(self, job: dict) -> None:
        with self.lock, self.db:
            existing = self.db.execute("SELECT position FROM jobs WHERE id=?", (job["id"],)).fetchone()
            position = (
                existing[0]
                if existing
                else self.db.execute("SELECT COALESCE(MAX(position), 0)+1 FROM jobs").fetchone()[0]
            )
            self.db.execute(
                "INSERT OR REPLACE INTO jobs VALUES (?, ?, ?)", (job["id"], position, json.dumps(job))
            )

    def remove_job(self, job_id: str) -> None:
        with self.lock, self.db:
            self.db.execute("DELETE FROM jobs WHERE id=?", (job_id,))

    def save_project_state(self, projects: list[dict], jobs: list[dict]) -> None:
        """Commit grouping changes together; audio and queue positions are untouched."""
        with self.lock, self.db:
            self.db.execute(
                "INSERT OR REPLACE INTO kv VALUES (?, ?)", ("projects", json.dumps(projects))
            )
            for job in jobs:
                cursor = self.db.execute(
                    "UPDATE jobs SET payload=? WHERE id=?", (json.dumps(job), job["id"])
                )
                if cursor.rowcount != 1:
                    raise ValueError("Job not found; project changes were not saved.")

    def reorder(self, ids: list[str]) -> None:
        with self.lock, self.db:
            current = {r[0] for r in self.db.execute("SELECT id FROM jobs")}
            if set(ids) != current or len(ids) != len(current):
                raise ValueError("Reordering must include each current job exactly once.")
            self.db.executemany("UPDATE jobs SET position=? WHERE id=?", enumerate(ids))

    def close(self) -> None:
        with self.lock:
            self.db.close()
