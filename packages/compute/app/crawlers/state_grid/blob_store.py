from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import oss2

from app.config import settings
from scripts.common import ensure_parent, ensure_state_grid_raw_dir


class BlobStore:
    def __init__(self) -> None:
        self.bucket_name = settings.state_grid_oss_bucket
        self.bucket = self.bucket_name
        endpoint = settings.state_grid_oss_endpoint or "https://oss-cn-hangzhou.aliyuncs.com"
        auth = oss2.Auth(
            settings.state_grid_oss_access_key_id,
            settings.state_grid_oss_secret_access_key,
        )
        self._bucket = oss2.Bucket(auth, endpoint, self.bucket_name)
        self._local_root = ensure_state_grid_raw_dir("mirror")

    def _mirror_to_local(self, key: str, data: bytes) -> Path:
        path = ensure_parent(self._local_root / key)
        path.write_bytes(data)
        return path

    def upload_json(self, key: str, data: dict[str, Any]) -> str:
        payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        return self.upload_bytes(key, payload, "application/json")

    def upload_bytes(self, key: str, data: bytes, content_type: str) -> str:
        self._mirror_to_local(key, data)
        self._bucket.put_object(key, data, headers={"Content-Type": content_type})
        return key

    def upload_file(self, key: str, local_path: Path, content_type: str) -> str:
        data = local_path.read_bytes()
        self._mirror_to_local(key, data)
        self._bucket.put_object(key, data, headers={"Content-Type": content_type})
        return key
