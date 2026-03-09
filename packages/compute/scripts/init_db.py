"""Initialize pgvector extension and vector table helpers."""

from __future__ import annotations

import argparse

import psycopg2

from app.config import settings


CREATE_SEGMENT_FEATURE_SQL = """
    CREATE TABLE IF NOT EXISTS segment_feature (
        segment_id   BIGINT PRIMARY KEY REFERENCES segment_index(id),
        feature_vector vector(182) NOT NULL,
        norm         REAL,
        created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
"""

CREATE_HNSW_SQL = """
    CREATE INDEX IF NOT EXISTS idx_segment_feature_hnsw
        ON segment_feature
        USING hnsw (feature_vector vector_cosine_ops)
        WITH (m = 16, ef_construction = 200);
"""


def _connect():
    return psycopg2.connect(settings.database_url)


def ensure_pgvector_schema(build_hnsw: bool = True) -> None:
    conn = _connect()
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    cur.execute(CREATE_SEGMENT_FEATURE_SQL)
    if build_hnsw:
        cur.execute(CREATE_HNSW_SQL)

    cur.close()
    conn.close()


def build_hnsw_index() -> None:
    conn = _connect()
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    cur.execute(CREATE_SEGMENT_FEATURE_SQL)
    cur.execute(CREATE_HNSW_SQL)
    cur.close()
    conn.close()


def init_db(build_hnsw: bool = True) -> None:
    ensure_pgvector_schema(build_hnsw=build_hnsw)


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize pgvector schema")
    parser.add_argument("--skip-index", action="store_true", help="Create table without HNSW index")
    parser.add_argument("--build-hnsw-only", action="store_true", help="Only ensure table and build HNSW")
    args = parser.parse_args()

    if args.build_hnsw_only:
        build_hnsw_index()
        print("HNSW index created.")
        return

    init_db(build_hnsw=not args.skip_index)
    print("pgvector schema initialized.")


if __name__ == "__main__":
    main()
