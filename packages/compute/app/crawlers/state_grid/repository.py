from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def upsert_crawler_watermark(
    db: Session,
    source: str,
    scope_type: str,
    scope_key: str,
    cursor_value: str | None = None,
    status: str = "active",
    error_message: str | None = None,
) -> None:
    db.execute(
        text(
            """
            INSERT INTO state_grid_crawler_watermarks
              (id, source, scope_type, scope_key, cursor_value, status, last_attempt_at, last_success_at, error_message, version, created_at, updated_at)
            VALUES
              (gen_random_uuid()::text, :source, :scope_type, :scope_key, :cursor_value, :status, NOW(), :last_success_at, :error_message, 0, NOW(), NOW())
            ON CONFLICT (source, scope_type, scope_key)
            DO UPDATE SET
              cursor_value = EXCLUDED.cursor_value,
              status = EXCLUDED.status,
              last_attempt_at = NOW(),
              last_success_at = EXCLUDED.last_success_at,
              error_message = EXCLUDED.error_message,
              version = state_grid_crawler_watermarks.version + 1,
              updated_at = NOW()
            """
        ),
        {
            "source": source,
            "scope_type": scope_type,
            "scope_key": scope_key,
            "cursor_value": cursor_value,
            "status": status,
            "last_success_at": datetime.utcnow() if status == "active" else None,
            "error_message": error_message,
        },
    )


def create_or_update_crawl_task(
    db: Session,
    source: str,
    task_type: str,
    biz_key: str,
    payload: dict[str, Any] | None = None,
    status: str = "pending",
    max_attempts: int = 5,
    parent_task_id: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    source_run_id: str | None = None,
) -> dict[str, Any]:
    row = db.execute(
        text(
            """
            INSERT INTO state_grid_crawl_tasks
              (id, source, source_run_id, task_type, biz_key, parent_task_id, payload, status, max_attempts, error_code, error_message, created_at, updated_at)
            VALUES
              (gen_random_uuid()::text, :source, :source_run_id, :task_type, :biz_key, :parent_task_id, CAST(:payload AS jsonb), :status, :max_attempts, :error_code, :error_message, NOW(), NOW())
            ON CONFLICT (source, task_type, biz_key)
            DO UPDATE SET
              source_run_id = COALESCE(EXCLUDED.source_run_id, state_grid_crawl_tasks.source_run_id),
              parent_task_id = EXCLUDED.parent_task_id,
              payload = COALESCE(EXCLUDED.payload, state_grid_crawl_tasks.payload),
              status = EXCLUDED.status,
              max_attempts = EXCLUDED.max_attempts,
              error_code = EXCLUDED.error_code,
              error_message = EXCLUDED.error_message,
              updated_at = NOW()
            RETURNING *
            """
        ),
        {
            "source": source,
            "source_run_id": source_run_id,
            "task_type": task_type,
            "biz_key": biz_key,
            "parent_task_id": parent_task_id,
            "payload": __import__("json").dumps(payload) if payload is not None else None,
            "status": status,
            "max_attempts": max_attempts,
            "error_code": error_code,
            "error_message": error_message,
        },
    ).mappings().one()
    return dict(row)


def get_crawl_tasks_by_status(
    db: Session,
    source: str,
    status: str,
    task_type: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM state_grid_crawl_tasks WHERE source = :source AND status = :status"
    params: dict[str, Any] = {"source": source, "status": status, "limit": limit}
    if task_type:
        sql += " AND task_type = :task_type"
        params["task_type"] = task_type
    sql += " ORDER BY updated_at ASC, id ASC LIMIT :limit"
    return [dict(r) for r in db.execute(text(sql), params).mappings().all()]


def increment_crawl_task_attempt(
    db: Session,
    task_id: str,
    error_code: str | None = None,
    error_message: str | None = None,
    next_retry_at: datetime | None = None,
) -> dict[str, Any]:
    row = db.execute(
        text(
            """
            UPDATE state_grid_crawl_tasks
            SET attempt_count = attempt_count + 1,
                error_code = :error_code,
                error_message = :error_message,
                next_retry_at = :next_retry_at,
                updated_at = NOW()
            WHERE id = :task_id
            RETURNING *
            """
        ),
        {
            "task_id": task_id,
            "error_code": error_code,
            "error_message": error_message,
            "next_retry_at": next_retry_at,
        },
    ).mappings().one()
    return dict(row)


def mark_crawl_task_status(
    db: Session,
    task_id: str,
    status: str,
    finished_at: datetime | None = None,
) -> dict[str, Any]:
    row = db.execute(
        text(
            """
            UPDATE state_grid_crawl_tasks
            SET status = :status,
                finished_at = COALESCE(:finished_at, finished_at),
                updated_at = NOW()
            WHERE id = :task_id
            RETURNING *
            """
        ),
        {"task_id": task_id, "status": status, "finished_at": finished_at},
    ).mappings().one()
    return dict(row)


def upsert_notice_raw(
    db: Session,
    source: str,
    notice_id: str,
    notice_type: str | None = None,
    org_id: str | None = None,
    list_api: str | None = None,
    list_batch_key: str | None = None,
    published_at: datetime | None = None,
    title: str | None = None,
    raw_list_json: dict[str, Any] | None = None,
    raw_meta_json: dict[str, Any] | None = None,
    status: str = "discovered",
    source_run_id: str | None = None,
    is_suspect: bool = False,
    suspect_reason: str | None = None,
) -> dict[str, Any]:
    row = db.execute(
        text(
            """
            INSERT INTO state_grid_notice_raws
              (id, source, source_run_id, notice_id, notice_type, org_id, list_api, list_batch_key, published_at, title, raw_list_json, raw_meta_json, is_suspect, suspect_reason, first_seen_at, last_seen_at, status, created_at, updated_at)
            VALUES
              (gen_random_uuid()::text, :source, :source_run_id, :notice_id, :notice_type, :org_id, :list_api, :list_batch_key, :published_at, :title, CAST(:raw_list_json AS jsonb), CAST(:raw_meta_json AS jsonb), :is_suspect, :suspect_reason, NOW(), NOW(), :status, NOW(), NOW())
            ON CONFLICT (source, notice_id)
            DO UPDATE SET
              source_run_id = COALESCE(EXCLUDED.source_run_id, state_grid_notice_raws.source_run_id),
              notice_type = COALESCE(EXCLUDED.notice_type, state_grid_notice_raws.notice_type),
              org_id = COALESCE(EXCLUDED.org_id, state_grid_notice_raws.org_id),
              list_api = COALESCE(EXCLUDED.list_api, state_grid_notice_raws.list_api),
              list_batch_key = COALESCE(EXCLUDED.list_batch_key, state_grid_notice_raws.list_batch_key),
              published_at = COALESCE(EXCLUDED.published_at, state_grid_notice_raws.published_at),
              title = COALESCE(EXCLUDED.title, state_grid_notice_raws.title),
              raw_list_json = COALESCE(EXCLUDED.raw_list_json, state_grid_notice_raws.raw_list_json),
              raw_meta_json = COALESCE(EXCLUDED.raw_meta_json, state_grid_notice_raws.raw_meta_json),
              is_suspect = EXCLUDED.is_suspect,
              suspect_reason = EXCLUDED.suspect_reason,
              status = EXCLUDED.status,
              last_seen_at = NOW(),
              updated_at = NOW()
            RETURNING *
            """
        ),
        {
            "source": source,
            "source_run_id": source_run_id,
            "notice_id": notice_id,
            "notice_type": notice_type,
            "org_id": org_id,
            "list_api": list_api,
            "list_batch_key": list_batch_key,
            "published_at": published_at,
            "title": title,
            "raw_list_json": __import__("json").dumps(raw_list_json) if raw_list_json is not None else None,
            "raw_meta_json": __import__("json").dumps(raw_meta_json) if raw_meta_json is not None else None,
            "is_suspect": is_suspect,
            "suspect_reason": suspect_reason,
            "status": status,
        },
    ).mappings().one()
    return dict(row)


def get_notice_raws_by_status(
    db: Session,
    source: str,
    status: str,
    limit: int = 100,
) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in db.execute(
            text(
                """
                SELECT * FROM state_grid_notice_raws
                WHERE source = :source AND status = :status
                ORDER BY updated_at ASC, id ASC
                LIMIT :limit
                """
            ),
            {"source": source, "status": status, "limit": limit},
        ).mappings().all()
    ]


def upsert_notice_detail(
    db: Session,
    notice_raw_id: str,
    source: str,
    notice_id: str,
    detail_api: str,
    org_id: str | None = None,
    raw_detail_json: dict[str, Any] | None = None,
    raw_html: str | None = None,
    content_type: str | None = None,
    fetch_status: str = "pending",
    error_code: str | None = None,
    error_message: str | None = None,
    source_run_id: str | None = None,
    is_suspect: bool = False,
    suspect_reason: str | None = None,
) -> dict[str, Any]:
    row = db.execute(
        text(
            """
            INSERT INTO state_grid_notice_details
              (id, notice_raw_id, source, source_run_id, notice_id, org_id, detail_api, raw_detail_json, raw_html, content_type, is_suspect, suspect_reason, fetch_status, error_code, error_message, fetched_at, created_at, updated_at)
            VALUES
              (gen_random_uuid()::text, :notice_raw_id, :source, :source_run_id, :notice_id, :org_id, :detail_api, CAST(:raw_detail_json AS jsonb), :raw_html, :content_type, :is_suspect, :suspect_reason, :fetch_status, :error_code, :error_message,
               CASE WHEN :fetch_status = 'succeeded' THEN NOW() ELSE NULL END, NOW(), NOW())
            ON CONFLICT (source, notice_id, detail_api)
            DO UPDATE SET
              source_run_id = COALESCE(EXCLUDED.source_run_id, state_grid_notice_details.source_run_id),
              org_id = COALESCE(EXCLUDED.org_id, state_grid_notice_details.org_id),
              raw_detail_json = COALESCE(EXCLUDED.raw_detail_json, state_grid_notice_details.raw_detail_json),
              raw_html = COALESCE(EXCLUDED.raw_html, state_grid_notice_details.raw_html),
              content_type = COALESCE(EXCLUDED.content_type, state_grid_notice_details.content_type),
              is_suspect = EXCLUDED.is_suspect,
              suspect_reason = EXCLUDED.suspect_reason,
              fetch_status = EXCLUDED.fetch_status,
              error_code = EXCLUDED.error_code,
              error_message = EXCLUDED.error_message,
              fetched_at = CASE WHEN EXCLUDED.fetch_status = 'succeeded' THEN NOW() ELSE state_grid_notice_details.fetched_at END,
              updated_at = NOW()
            RETURNING *
            """
        ),
        {
            "notice_raw_id": notice_raw_id,
            "source": source,
            "source_run_id": source_run_id,
            "notice_id": notice_id,
            "org_id": org_id,
            "detail_api": detail_api,
            "raw_detail_json": __import__("json").dumps(raw_detail_json) if raw_detail_json is not None else None,
            "raw_html": raw_html,
            "content_type": content_type,
            "is_suspect": is_suspect,
            "suspect_reason": suspect_reason,
            "fetch_status": fetch_status,
            "error_code": error_code,
            "error_message": error_message,
        },
    ).mappings().one()
    return dict(row)


def upsert_notice_file(
    db: Session,
    notice_raw_id: str,
    source: str,
    notice_id: str,
    file_role: str,
    source_api: str,
    source_file_id: str,
    org_id: str | None = None,
    file_name: str | None = None,
    ext: str | None = None,
    mime_type: str | None = None,
    size_bytes: int | None = None,
    checksum_sha256: str | None = None,
    oss_bucket: str | None = None,
    oss_key: str | None = None,
    source_url: str | None = None,
    raw_file_meta_json: dict[str, Any] | None = None,
    status: str = "pending",
    source_run_id: str | None = None,
) -> dict[str, Any]:
    row = db.execute(
        text(
            """
            INSERT INTO state_grid_notice_files
              (id, notice_raw_id, source, source_run_id, notice_id, org_id, file_role, source_api, source_file_id, file_name, ext, mime_type, size_bytes, checksum_sha256, oss_bucket, oss_key, source_url, raw_file_meta_json, status, created_at, updated_at)
            VALUES
              (gen_random_uuid()::text, :notice_raw_id, :source, :source_run_id, :notice_id, :org_id, :file_role, :source_api, :source_file_id, :file_name, :ext, :mime_type, :size_bytes, :checksum_sha256, :oss_bucket, :oss_key, :source_url, CAST(:raw_file_meta_json AS jsonb), :status, NOW(), NOW())
            ON CONFLICT (source, notice_id, source_api, source_file_id)
            DO UPDATE SET
              source_run_id = COALESCE(EXCLUDED.source_run_id, state_grid_notice_files.source_run_id),
              org_id = COALESCE(EXCLUDED.org_id, state_grid_notice_files.org_id),
              file_name = COALESCE(EXCLUDED.file_name, state_grid_notice_files.file_name),
              ext = COALESCE(EXCLUDED.ext, state_grid_notice_files.ext),
              mime_type = COALESCE(EXCLUDED.mime_type, state_grid_notice_files.mime_type),
              size_bytes = COALESCE(EXCLUDED.size_bytes, state_grid_notice_files.size_bytes),
              checksum_sha256 = COALESCE(EXCLUDED.checksum_sha256, state_grid_notice_files.checksum_sha256),
              oss_bucket = COALESCE(EXCLUDED.oss_bucket, state_grid_notice_files.oss_bucket),
              oss_key = COALESCE(EXCLUDED.oss_key, state_grid_notice_files.oss_key),
              source_url = COALESCE(EXCLUDED.source_url, state_grid_notice_files.source_url),
              raw_file_meta_json = COALESCE(EXCLUDED.raw_file_meta_json, state_grid_notice_files.raw_file_meta_json),
              status = EXCLUDED.status,
              updated_at = NOW()
            RETURNING *
            """
        ),
        {
            "notice_raw_id": notice_raw_id,
            "source": source,
            "source_run_id": source_run_id,
            "notice_id": notice_id,
            "org_id": org_id,
            "file_role": file_role,
            "source_api": source_api,
            "source_file_id": source_file_id,
            "file_name": file_name,
            "ext": ext,
            "mime_type": mime_type,
            "size_bytes": size_bytes,
            "checksum_sha256": checksum_sha256,
            "oss_bucket": oss_bucket,
            "oss_key": oss_key,
            "source_url": source_url,
            "raw_file_meta_json": __import__("json").dumps(raw_file_meta_json) if raw_file_meta_json is not None else None,
            "status": status,
        },
    ).mappings().one()
    return dict(row)


def update_notice_file_status(
    db: Session,
    file_id: str,
    status: str,
    oss_bucket: str | None = None,
    oss_key: str | None = None,
    size_bytes: int | None = None,
    checksum_sha256: str | None = None,
    last_error_code: str | None = None,
    last_error_message: str | None = None,
    uploaded_at: datetime | None = None,
) -> dict[str, Any]:
    row = db.execute(
        text(
            """
            UPDATE state_grid_notice_files
            SET status = :status,
                oss_bucket = COALESCE(:oss_bucket, oss_bucket),
                oss_key = COALESCE(:oss_key, oss_key),
                size_bytes = COALESCE(:size_bytes, size_bytes),
                checksum_sha256 = COALESCE(:checksum_sha256, checksum_sha256),
                last_error_code = :last_error_code,
                last_error_message = :last_error_message,
                uploaded_at = COALESCE(:uploaded_at, uploaded_at),
                downloaded_at = CASE WHEN :status = 'succeeded' THEN COALESCE(downloaded_at, NOW()) ELSE downloaded_at END,
                updated_at = NOW()
            WHERE id = :file_id
            RETURNING *
            """
        ),
        {
            "file_id": file_id,
            "status": status,
            "oss_bucket": oss_bucket,
            "oss_key": oss_key,
            "size_bytes": size_bytes,
            "checksum_sha256": checksum_sha256,
            "last_error_code": last_error_code,
            "last_error_message": last_error_message,
            "uploaded_at": uploaded_at,
        },
    ).mappings().one()
    return dict(row)


__all__ = [
    "create_or_update_crawl_task",
    "get_crawl_tasks_by_status",
    "get_notice_raws_by_status",
    "increment_crawl_task_attempt",
    "mark_crawl_task_status",
    "upsert_crawler_watermark",
    "upsert_notice_detail",
    "upsert_notice_file",
    "upsert_notice_raw",
    "update_notice_file_status",
]
