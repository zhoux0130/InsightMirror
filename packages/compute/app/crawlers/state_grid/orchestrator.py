from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text

from app.crawlers.state_grid.blob_store import BlobStore
from app.crawlers.state_grid.client import StateGridClient
from app.crawlers.state_grid.repository import (
    create_or_update_crawl_task,
    get_crawl_tasks_by_status,
    increment_crawl_task_attempt,
    mark_crawl_task_status,
    upsert_crawler_watermark,
    upsert_notice_detail,
    upsert_notice_file,
    upsert_notice_raw,
    update_notice_file_status,
)
from app.db.connection import get_db
from scripts.common import (
    state_grid_detail_snapshot_key,
    state_grid_file_key,
    state_grid_html_key,
    state_grid_list_snapshot_key,
)

logger = logging.getLogger(__name__)
SOURCE = "state_grid"
DETAIL_APIS = ("getNoticeBid", "getChangeBid", "getNoticeWin")


class StateGridOrchestrator:
    def __init__(self, client: StateGridClient | None = None, blob_store: BlobStore | None = None) -> None:
        self.client = client or StateGridClient()
        self.blob_store = blob_store or BlobStore()
        self.source_run_id = str(uuid.uuid4())

    def sync_org_tree(self) -> list[dict[str, Any]]:
        payload = self.client.orgTreeNew()
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        self.blob_store.upload_json(state_grid_detail_snapshot_key("org-tree", "orgTreeNew", timestamp), payload)
        orgs = self._extract_orgs(payload)
        with get_db() as db:
            for org in orgs:
                org_id = str(org.get("id") or org.get("ID") or org.get("CODE") or org.get("orgId") or org.get("key") or "")
                if org_id:
                    upsert_crawler_watermark(db, SOURCE, "org", org_id, cursor_value="1")
        return orgs

    def fetch_notices_full(self, org_ids: list[str] | None = None, limit_pages: int | None = None) -> None:
        target_orgs = org_ids if org_ids is not None else [""]
        for org_id in target_orgs:
            page = 1
            while True:
                task = self._start_task("list", f"list:{org_id}:{page}", {"orgId": org_id, "page": page})
                try:
                    payload = self.client.noteList(org_id=org_id, page=page)
                    notices = self._extract_items(payload)
                    self.blob_store.upload_json(state_grid_list_snapshot_key("noteList", task["id"], page), payload)
                    is_suspect, suspect_reason = self._is_suspect_list_payload(payload, notices)
                    with get_db() as db:
                        for notice in notices:
                            notice_id = self._notice_id(notice)
                            if not notice_id:
                                continue
                            upsert_notice_raw(
                                db,
                                SOURCE,
                                notice_id,
                                notice_type=self._notice_type(notice),
                                org_id=str(notice.get("orgId") or notice.get("ORG_ID") or org_id or "") or None,
                                list_api="noteList",
                                list_batch_key=f"{org_id}:{page}",
                                published_at=self._parse_datetime(
                                    notice.get("publishTime") or notice.get("noticePublishTime") or notice.get("publishedAt") or notice.get("date") or notice.get("PUB_TIME")
                                ),
                                title=notice.get("title") or notice.get("TITLE") or notice.get("noticeTitle"),
                                raw_list_json=notice,
                                raw_meta_json={"orgId": org_id, "page": page, "sourceRunId": self.source_run_id},
                                status="detail_pending",
                                source_run_id=self.source_run_id,
                                is_suspect=is_suspect,
                                suspect_reason=suspect_reason,
                            )
                        upsert_crawler_watermark(db, SOURCE, "org", org_id, cursor_value=str(page), status="active")
                        mark_crawl_task_status(db, task["id"], "succeeded", finished_at=datetime.utcnow())
                    total_count = self._extract_total_count(payload)
                    if not notices or (limit_pages is not None and page >= limit_pages):
                        break
                    if total_count is not None and page * 20 >= total_count:
                        break
                    page += 1
                except Exception as exc:
                    self._fail_task(task["id"], exc)
                    logger.exception("state-grid list fetch failed org=%s page=%s", org_id, page)
                    break

    def fetch_notices_incremental(self) -> None:
        self.fetch_notices_full(org_ids=[""], limit_pages=1)

    def fetch_details_for_raws(self, limit: int = 50, notice_ids: list[str] | None = None) -> None:
        notices = self._load_notice_rows(["discovered", "detail_pending", "partial"], limit, notice_ids)
        for notice in notices:
            notice_id = str(notice["notice_id"])
            success = False
            for api_name in self._detail_apis_for_notice(notice):
                task = self._start_task("detail", f"detail:{notice_id}:{api_name}", {"noticeId": notice_id, "api": api_name})
                try:
                    payload = getattr(self.client, api_name)(notice_id)
                    raw_html = self._extract_detail_html(payload)
                    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
                    self.blob_store.upload_json(state_grid_detail_snapshot_key(notice_id, api_name, ts), payload)
                    if raw_html:
                        self.blob_store.upload_bytes(state_grid_html_key(notice_id, api_name, ts), raw_html.encode("utf-8"), "text/html")
                    is_suspect, suspect_reason = self._is_suspect_detail_payload(payload, raw_html)
                    with get_db() as db:
                        upsert_notice_detail(
                            db,
                            notice["id"],
                            SOURCE,
                            notice_id,
                            api_name,
                            raw_detail_json=payload,
                            raw_html=raw_html,
                            content_type="application/json" if not raw_html else "text/html",
                            fetch_status="succeeded",
                            source_run_id=self.source_run_id,
                            is_suspect=is_suspect,
                            suspect_reason=suspect_reason,
                        )
                        db.execute(
                            text("UPDATE state_grid_notice_raws SET status = 'detail_done', updated_at = NOW() WHERE id = :id"),
                            {"id": notice["id"]},
                        )
                        mark_crawl_task_status(db, task["id"], "succeeded", finished_at=datetime.utcnow())
                    success = True
                    break
                except Exception as exc:
                    self._fail_task(task["id"], exc)
                    with get_db() as db:
                        upsert_notice_detail(
                            db,
                            notice["id"],
                            SOURCE,
                            notice_id,
                            api_name,
                            org_id=notice.get("org_id"),
                            fetch_status="failed",
                            error_code=exc.__class__.__name__,
                            error_message=str(exc),
                            source_run_id=self.source_run_id,
                        )
            if not success:
                with get_db() as db:
                    db.execute(
                        text("UPDATE state_grid_notice_raws SET status = 'failed', updated_at = NOW() WHERE id = :id"),
                        {"id": notice["id"]},
                    )

    def fetch_files_for_raws(self, limit: int = 50, notice_ids: list[str] | None = None) -> None:
        notices = self._load_notice_rows(["detail_done", "file_pending"], limit, notice_ids)
        for notice in notices:
            notice_id = str(notice["notice_id"])
            file_candidates = self._extract_file_candidates(notice)
            if not file_candidates and notice.get("notice_type") not in (None, "", "100063007"):
                file_candidates = [{"sourceApi": "downLoadBid", "fileRole": "attachment", "sourceFileId": str(notice_id), "fileName": f"{notice_id}.zip"}]
            if not file_candidates:
                with get_db() as db:
                    db.execute(
                        text("UPDATE state_grid_notice_raws SET status = 'detail_done', updated_at = NOW() WHERE id = :id"),
                        {"id": notice["id"]},
                    )
                continue

            has_file_rows = False
            all_succeeded = True
            for candidate in file_candidates:
                has_file_rows = True
                if not self._fetch_single_file(notice, candidate):
                    all_succeeded = False
            with get_db() as db:
                db.execute(
                    text("UPDATE state_grid_notice_raws SET status = :status, updated_at = NOW() WHERE id = :id"),
                    {"id": notice["id"], "status": "file_done" if (has_file_rows and all_succeeded) else "partial"},
                )

    def replay_dead_tasks(self, task_type: str | None = None, limit: int = 100) -> None:
        with get_db() as db:
            tasks = get_crawl_tasks_by_status(db, SOURCE, "dead", task_type=task_type, limit=limit)
        for task in tasks:
            payload = task.get("payload") or {}
            current_task_type = task.get("task_type")
            if current_task_type == "list":
                self.fetch_notices_full(org_ids=[str(payload.get("orgId"))], limit_pages=1)
            elif current_task_type == "detail":
                notice_id = payload.get("noticeId")
                if notice_id:
                    self.fetch_details_for_raws(limit=1, notice_ids=[str(notice_id)])
            elif current_task_type == "file":
                notice_id = payload.get("noticeId")
                if notice_id:
                    self.fetch_files_for_raws(limit=1, notice_ids=[str(notice_id)])

    def run_full_pipeline(self, limit_pages: int | None = None) -> None:
        self.fetch_notices_full(limit_pages=limit_pages)
        self.fetch_details_for_raws()
        self.fetch_files_for_raws()

    def _load_notice_rows(self, statuses: list[str], limit: int, notice_ids: list[str] | None = None) -> list[dict[str, Any]]:
        clauses = ["source = :source", "status = ANY(:statuses)"]
        params: dict[str, Any] = {"source": SOURCE, "statuses": statuses, "limit": limit}
        if notice_ids:
            clauses.append("notice_id = ANY(:notice_ids)")
            params["notice_ids"] = notice_ids
        sql = f"SELECT * FROM state_grid_notice_raws WHERE {' AND '.join(clauses)} ORDER BY updated_at ASC LIMIT :limit"
        with get_db() as db:
            return [dict(row) for row in db.execute(text(sql), params).mappings().all()]

    def _fetch_single_file(self, notice: dict[str, Any], candidate: dict[str, Any]) -> bool:
        notice_id = str(notice["notice_id"])
        file_id = str(candidate.get("PURPRJ_NOTICE_ATTACH_ID") or candidate.get("sourceFileId") or candidate.get("fileId") or candidate.get("id") or candidate.get("name") or "default")
        api_name = str(candidate.get("sourceApi") or candidate.get("api") or "showPDF")
        file_name = str(candidate.get("FILE_NAME") or candidate.get("fileName") or candidate.get("name") or f"{file_id}.bin")
        task = self._start_task("file", f"file:{notice_id}:{api_name}:{file_id}", {"noticeId": notice_id, "fileId": file_id, "sourceApi": api_name})
        with get_db() as db:
            file_row = upsert_notice_file(
                db,
                notice["id"],
                SOURCE,
                notice_id,
                org_id=notice.get("org_id"),
                file_role="attachment",
                source_api=api_name,
                source_file_id=file_id,
                file_name=file_name,
                ext=self._ext(file_name),
                source_url=candidate.get("sourceUrl"),
                raw_file_meta_json=candidate,
                status="uploading",
                source_run_id=self.source_run_id,
            )
        try:
            if api_name == "downLoadBid":
                response = self.client.downLoadBid(notice_id, notice_det_id=candidate.get("noticeDetId"))
                content = response.content
                if not candidate.get("fileName"):
                    candidate["fileName"] = f"{notice_id}.zip"
            elif api_name == "getWinFile":
                response = self.client.getWinFile(notice_id)
                win_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                files = win_data.get("files", [])
                if files:
                    file_path = files[0].get("FILE_PATH")
                    if file_path:
                        response = self.client.showPDF(file_path)
                content = response.content
            elif api_name == "showPDF":
                file_path = candidate.get("FILE_PATH") or candidate.get("filePath") or file_id
                response = self.client.showPDF(file_path)
                content = response.content
            else:
                content = b""
            is_suspect, suspect_reason = self._is_suspect_file_payload(content)
            checksum = hashlib.sha256(content).hexdigest()
            mime_type = "application/octet-stream"
            key = state_grid_file_key(notice_id, checksum, file_name)
            stored_key = self.blob_store.upload_bytes(key, content, mime_type)
            with get_db() as db:
                update_notice_file_status(
                    db,
                    file_row["id"],
                    "succeeded",
                    oss_bucket=self.blob_store.bucket,
                    oss_key=stored_key,
                    size_bytes=len(content),
                    checksum_sha256=checksum,
                    uploaded_at=datetime.utcnow(),
                )
                if is_suspect:
                    db.execute(
                        text("UPDATE state_grid_notice_files SET is_suspect = TRUE, suspect_reason = :reason WHERE id = :id"),
                        {"id": file_row["id"], "reason": suspect_reason},
                    )
                mark_crawl_task_status(db, task["id"], "succeeded", finished_at=datetime.utcnow())
            return True
        except Exception as exc:
            self._fail_task(task["id"], exc)
            with get_db() as db:
                update_notice_file_status(
                    db,
                    file_row["id"],
                    "failed",
                    last_error_code=exc.__class__.__name__,
                    last_error_message=str(exc),
                )
            return False

    def _start_task(self, task_type: str, biz_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        payload = {**payload, "sourceRunId": self.source_run_id}
        with get_db() as db:
            return create_or_update_crawl_task(
                db,
                SOURCE,
                task_type,
                biz_key,
                payload=payload,
                status="running",
                source_run_id=self.source_run_id,
            )

    def _fail_task(self, task_id: str, exc: Exception) -> None:
        with get_db() as db:
            task = increment_crawl_task_attempt(
                db,
                task_id,
                error_code=exc.__class__.__name__,
                error_message=str(exc),
                next_retry_at=datetime.utcnow() + timedelta(minutes=1),
            )
            status = "dead" if int(task["attempt_count"]) >= int(task["max_attempts"]) else "failed"
            mark_crawl_task_status(db, task_id, status, finished_at=datetime.utcnow())

    def _extract_items(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if not isinstance(payload, dict):
            return []
        result_value = payload.get("resultValue")
        if isinstance(result_value, dict):
            note_list = result_value.get("noteList")
            if isinstance(note_list, list):
                return [item for item in note_list if isinstance(item, dict)]
            if isinstance(note_list, dict):
                items = note_list.get("items")
                if isinstance(items, list):
                    return [item for item in items if isinstance(item, dict)]
                return [note_list] if note_list else []
        return []

    def _extract_orgs(self, payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        result_value = payload.get("resultValue")
        if isinstance(result_value, dict):
            for key in ("items", "orgs"):
                value = result_value.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
            orglist = result_value.get("orglist")
            if isinstance(orglist, dict):
                items = orglist.get("items")
                if isinstance(items, list):
                    return [item for item in items if isinstance(item, dict)]
        return []

    def _extract_total_count(self, payload: Any, default_zero: bool = True) -> int | None:
        if not isinstance(payload, dict):
            return 0 if default_zero else None
        result_value = payload.get("resultValue")
        if isinstance(result_value, dict):
            count = result_value.get("count")
            if count is not None:
                try:
                    return int(count)
                except (TypeError, ValueError):
                    return 0 if default_zero else None
        return 0 if default_zero else None

    def _is_suspect_list_payload(self, payload: Any, notices: list[dict[str, Any]]) -> tuple[bool, str | None]:
        total_count = self._extract_total_count(payload, default_zero=False)
        if total_count not in (None, 0) and not notices:
            return True, "note_list_empty_with_positive_count"
        return False, None

    def _is_suspect_detail_payload(self, payload: Any, raw_html: str | None) -> tuple[bool, str | None]:
        if payload in (None, {}) and not raw_html:
            return True, "empty_detail_payload"
        return False, None

    def _is_suspect_file_payload(self, content: bytes) -> tuple[bool, str | None]:
        if not content:
            return True, "empty_file_payload"
        return False, None

    def _extract_detail_html(self, payload: Any) -> str | None:
        if not isinstance(payload, dict):
            return None
        for key in ("html", "HTML"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
        notice = payload.get("notice")
        if isinstance(notice, dict):
            for key in ("CONT", "content", "html"):
                value = notice.get(key)
                if isinstance(value, str) and value.strip():
                    return value
        chg_notice = payload.get("chgNotice")
        if isinstance(chg_notice, dict):
            value = chg_notice.get("CHG_NOTICE_CONT")
            if isinstance(value, str) and value.strip():
                return value
        return None

    def _extract_file_candidates(self, notice: dict[str, Any]) -> list[dict[str, Any]]:
        for json_key in ("raw_meta_json", "raw_list_json"):
            payload = notice.get(json_key)
            if isinstance(payload, dict):
                for key in ("files", "attachments", "fileList"):
                    value = payload.get(key)
                    if isinstance(value, list):
                        return [item for item in value if isinstance(item, dict)]
        return []

    def _notice_id(self, notice: dict[str, Any]) -> str | None:
        for key in ("noticeId", "id", "docid", "guid"):
            value = notice.get(key)
            if value:
                return str(value)
        return None

    def _notice_type(self, notice: dict[str, Any]) -> str | None:
        for key in ("noticeType", "type", "businessType", "docType"):
            value = notice.get(key)
            if value:
                return str(value)
        return None

    def _detail_apis_for_notice(self, notice: dict[str, Any]) -> list[str]:
        notice_type = str(notice.get("notice_type") or notice.get("noticeType") or "").lower()
        if "change" in notice_type:
            return ["getChangeBid"]
        if "win" in notice_type:
            return ["getNoticeWin"]
        if "bid" in notice_type:
            return ["getNoticeBid"]
        return list(DETAIL_APIS)

    def _parse_datetime(self, value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        text_value = str(value).strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"):
            try:
                return datetime.strptime(text_value, fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(text_value)
        except ValueError:
            return None

    def _ext(self, file_name: str) -> str | None:
        return file_name.rsplit(".", 1)[-1].lower() if "." in file_name else None
