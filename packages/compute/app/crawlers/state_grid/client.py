from __future__ import annotations

from typing import Any

import httpx

from app.config import settings
from app.crawlers.state_grid.base import StateGridClientBase


class StateGridClient(StateGridClientBase):
    def __init__(
        self,
        base_url: str = settings.state_grid_base_url,
        timeout: float = settings.state_grid_api_timeout,
        max_retries: int = settings.state_grid_max_retries,
        retry_backoff_base: float = settings.state_grid_retry_backoff_base,
    ) -> None:
        super().__init__(
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            retry_backoff_base=retry_backoff_base,
        )

    def orgTreeNew(self, **kwargs: Any) -> dict[str, Any]:
        response = self._request("POST", "/orgTreeNew", json={"orgId": kwargs.get("orgId")})
        return response.json()

    def noteList(
        self,
        org_id: str = "",
        page: int = 1,
        page_size: int = 20,
        first_page_menu_id: str = "2018032900295987",
        **kwargs: Any,
    ) -> dict[str, Any]:
        payload = {
            "index": page,
            "size": page_size,
            "firstPageMenuId": first_page_menu_id,
            "purOrgStatus": "",
            "purOrgCode": "",
            "purType": "",
            "noticeType": "",
            "orgId": org_id or "",
            "key": "",
            "orgName": "",
            **kwargs,
        }
        response = self._request("POST", "/noteList", json=payload)
        return response.json()

    def getNoticeBid(self, notice_id: str, **kwargs: Any) -> dict[str, Any]:
        response = self._request("POST", "/getNoticeBid", data=str(notice_id), **kwargs)
        return response.json()

    def getChangeBid(self, notice_id: str, **kwargs: Any) -> dict[str, Any]:
        response = self._request("POST", "/getChangeBid", data=str(notice_id), **kwargs)
        return response.json()

    def getNoticeWin(self, notice_id: str, **kwargs: Any) -> dict[str, Any]:
        response = self._request("POST", "/getNoticeWin", data=str(notice_id), **kwargs)
        return response.json()

    def downLoadBid(self, notice_id: str, notice_det_id: str | None = None, **kwargs: Any) -> httpx.Response:
        params = {"noticeId": notice_id, "noticeDetId": notice_det_id or "null"}
        return self._request("GET", "/downLoadBid", params=params, **kwargs)

    def getWinFile(self, notice_id: str, **kwargs: Any) -> httpx.Response:
        response = self._request("POST", "/getWinFile", data=str(notice_id), **kwargs)
        return response

    def showPDF(self, file_path: str, **kwargs: Any) -> httpx.Response:
        params = {"filePath": file_path}
        return self._request("GET", "/showPDF", params=params, **kwargs)
