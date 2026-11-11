"""Per-machine record of model calls and runs. Kept in SQLite beside the run artifacts."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from app.research.llm import ModelCallError, Provider, T, Usage

MODELS_PATH = Path(__file__).with_name("models.json")
TOKENS_PER_PRICE_UNIT = 1_000_000

SCHEMA = """
CREATE TABLE IF NOT EXISTS llm_call (
    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, created_at REAL NOT NULL, model_id TEXT NOT NULL,
    stage TEXT NOT NULL, status TEXT NOT NULL, input_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL,
    cache_read_tokens INTEGER NOT NULL, cache_write_tokens INTEGER NOT NULL, latency_ms INTEGER NOT NULL,
    estimated_cost REAL NOT NULL, currency TEXT NOT NULL, error TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_llm_call_run ON llm_call(run_id);
CREATE TABLE IF NOT EXISTS run (
    run_id TEXT PRIMARY KEY, started_at REAL NOT NULL, finished_at REAL, doc_id TEXT NOT NULL, model_id TEXT NOT NULL,
    model TEXT NOT NULL, prompt_version TEXT NOT NULL, status TEXT NOT NULL, partial INTEGER NOT NULL,
    result_path TEXT NOT NULL, metrics_json TEXT NOT NULL, error TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS claim_feedback (
    doc_id TEXT NOT NULL, model_id TEXT NOT NULL, claim_id TEXT NOT NULL, quote TEXT NOT NULL,
    verdict TEXT NOT NULL, wrong_fields TEXT NOT NULL, note TEXT NOT NULL, updated_at REAL NOT NULL,
    PRIMARY KEY (doc_id, model_id, claim_id)
);
"""
VERDICTS = ("correct", "partial", "wrong")


@dataclass(frozen=True)
class Price:
    currency: str
    input: float
    output: float
    cache_read: float
    cache_write: float

    def cost(self, usage: Usage) -> float:
        return (
            usage.input_tokens * self.input
            + usage.output_tokens * self.output
            + usage.cache_read_tokens * self.cache_read
            + usage.cache_write_tokens * self.cache_write
        ) / TOKENS_PER_PRICE_UNIT


@dataclass(frozen=True)
class ModelConfig:
    id: str
    kind: str
    model: str
    key_env: str
    base_url: str
    price: Price
    price_note: str
    stage_options: dict[str, dict[str, Any]] = field(default_factory=dict)


def load_models(path: Path = MODELS_PATH) -> dict[str, ModelConfig]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    return {r["id"]: ModelConfig(**{**r, "price": Price(**r["price"])}) for r in rows}


class Ledger:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._connect() as db:
            db.executescript(SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def record_call(self, *, run_id: str, config: ModelConfig, stage: str, status: str, usage: Usage,
                    latency_ms: int, error: str = "") -> None:
        with self._lock, self._connect() as db:
            db.execute(
                "INSERT INTO llm_call (run_id, created_at, model_id, stage, status, input_tokens, output_tokens,"
                " cache_read_tokens, cache_write_tokens, latency_ms, estimated_cost, currency, error)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (run_id, time.time(), config.id, stage, status, usage.input_tokens, usage.output_tokens,
                 usage.cache_read_tokens, usage.cache_write_tokens, latency_ms, config.price.cost(usage),
                 config.price.currency, error[:500]),
            )

    def start_run(self, *, run_id: str, doc_id: str, config: ModelConfig, prompt_version: str, partial: bool) -> None:
        with self._lock, self._connect() as db:
            db.execute(
                "INSERT INTO run (run_id, started_at, doc_id, model_id, model, prompt_version, status, partial,"
                " result_path, metrics_json, error) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (run_id, time.time(), doc_id, config.id, config.model, prompt_version, "running", int(partial), "", "{}", ""),
            )

    def finish_run(self, run_id: str, *, status: str, result_path: str = "",
                   metrics: dict[str, Any] | None = None, error: str = "") -> None:
        with self._lock, self._connect() as db:
            db.execute(
                "UPDATE run SET finished_at=?, status=?, result_path=?, metrics_json=?, error=? WHERE run_id=?",
                (time.time(), status, result_path, json.dumps(metrics or {}, ensure_ascii=False), error[:500], run_id),
            )

    def usage_by_model(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT model_id, currency, COUNT(*) calls, SUM(status != 'ok') failed_calls,"
                " SUM(input_tokens) input_tokens, SUM(output_tokens) output_tokens,"
                " SUM(cache_read_tokens) cache_read_tokens, SUM(cache_write_tokens) cache_write_tokens,"
                " SUM(estimated_cost) estimated_cost, CAST(AVG(latency_ms) AS INTEGER) avg_latency_ms"
                " FROM llm_call GROUP BY model_id, currency ORDER BY model_id"
            ).fetchall()
        return [dict(r) for r in rows]

    def runs(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT r.*, COALESCE(SUM(c.estimated_cost), 0) estimated_cost, COALESCE(MAX(c.currency), '') currency,"
                " COUNT(c.id) calls FROM run r LEFT JOIN llm_call c ON c.run_id = r.run_id"
                " GROUP BY r.run_id ORDER BY r.started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [{**dict(r), "metrics": json.loads(r["metrics_json"])} for r in rows]

    def latest_results(self, doc_id: str) -> dict[str, str]:
        """Newest complete, non-partial result per model for one document."""
        with self._connect() as db:
            rows = db.execute(
                "SELECT model_id, result_path FROM run WHERE doc_id=? AND status='ok' AND partial=0 ORDER BY started_at",
                (doc_id,),
            ).fetchall()
        return {r["model_id"]: str(self._resolve(r["result_path"])) for r in rows}

    def _resolve(self, stored: str) -> Path:
        """New rows are relative to the ledger's folder. Older rows hold a path from wherever the run started,
        so fall back to the part after the last "research" folder."""
        path = Path(stored)
        candidate = path if path.is_absolute() else self.path.parent / path
        if candidate.exists() or "research" not in path.parts:
            return candidate
        tail = path.parts[len(path.parts) - path.parts[::-1].index("research"):]
        return self.path.parent.joinpath(*tail)

    def save_feedback(self, *, doc_id: str, model_id: str, claim_id: str, quote: str, verdict: str,
                      wrong_fields: list[str], note: str) -> None:
        """An empty verdict with no note clears the row. The quote pins feedback to the claim it judged."""
        with self._lock, self._connect() as db:
            if not verdict and not note:
                db.execute("DELETE FROM claim_feedback WHERE doc_id=? AND model_id=? AND claim_id=?",
                           (doc_id, model_id, claim_id))
                return
            db.execute(
                "INSERT OR REPLACE INTO claim_feedback VALUES (?,?,?,?,?,?,?,?)",
                (doc_id, model_id, claim_id, quote, verdict, json.dumps(wrong_fields, ensure_ascii=False),
                 note[:2000], time.time()),
            )

    def feedback(self, doc_id: str) -> dict[tuple[str, str], dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM claim_feedback WHERE doc_id=?", (doc_id,)).fetchall()
        return {
            (r["model_id"], r["claim_id"]): {
                "quote": r["quote"], "verdict": r["verdict"], "wrong_fields": json.loads(r["wrong_fields"]),
                "note": r["note"], "updated_at": r["updated_at"],
            }
            for r in rows
        }

    def documents(self) -> list[str]:
        with self._connect() as db:
            return [r["doc_id"] for r in db.execute("SELECT DISTINCT doc_id FROM run ORDER BY doc_id DESC")]


class MeteredClient:
    """Adapts a Provider to the pipeline and records every attempt, including failures."""

    def __init__(self, provider: Provider, config: ModelConfig, ledger: Ledger, run_id: str):
        self.provider, self.config, self.ledger, self.run_id = provider, config, ledger, run_id
        self.model = provider.model

    def complete(self, *, system: list[dict[str, Any]], user: str, output: type[T]) -> T:
        started = time.monotonic()
        common = dict(run_id=self.run_id, config=self.config, stage=output.__name__)

        def elapsed() -> int:
            return int((time.monotonic() - started) * 1000)

        try:
            parsed, usage = self.provider.call(system=system, user=user, output=output)
        except ModelCallError as error:
            self.ledger.record_call(**common, status="error", usage=error.usage, latency_ms=elapsed(), error=str(error))
            raise
        except Exception as error:
            self.ledger.record_call(**common, status="error", usage=Usage(), latency_ms=elapsed(), error=type(error).__name__)
            raise
        self.ledger.record_call(**common, status="ok", usage=usage, latency_ms=elapsed())
        return parsed
