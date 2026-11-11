#!/usr/bin/env python3
"""Serve only the research console, bound to localhost, without the stock-data services."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("RESEARCH_ADMIN_LOCAL", "1")  # bound to 127.0.0.1 below, so no password needed

from app.api.research_admin import router  # noqa: E402

PORT = 8765

app = FastAPI(title="Research Console")
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
