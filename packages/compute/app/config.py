from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://user:password@localhost:5432/database"
    data_source: str = "akshare"
    raw_data_dir: str = "data/raw"
    history_start_date: str = "2016-01-01"
    history_end_date: str = "2026-03-06"
    history_adjust: str = ""
    tushare_token: str = ""

    # Feature defaults
    default_window_size: int = 60
    default_feature_version: str = "v1"

    # Search defaults
    ann_top_k: int = 200
    final_top_k: int = 50
    min_gap_ratio: float = 0.5  # min_gap = window_size * ratio
    leakage_gap_multiplier: int = 2  # gap = multiplier * future_days

    # Pipeline
    pipeline_workers: int = 4

    # Scheduler
    scheduler_enabled: bool = True
    scheduler_hour: int = 1     # UTC 01:00 = Beijing 09:00
    scheduler_minute: int = 0

    # State Grid crawling
    state_grid_base_url: str = "https://ecp.sgcc.com.cn/ecp2.0/ecpwcmcore//index"
    state_grid_api_timeout: int = 30
    state_grid_max_retries: int = 5
    state_grid_retry_backoff_base: int = 60
    state_grid_list_concurrency: int = 3
    state_grid_detail_concurrency: int = 5
    state_grid_file_concurrency: int = 3
    state_grid_schedule_enable: bool = False
    state_grid_schedule_cron: str = "0 2 * * *"
    state_grid_oss_prefix: str = "state-grid/raw"
    state_grid_oss_bucket: str = ""
    state_grid_oss_endpoint: str = ""
    state_grid_oss_access_key_id: str = ""
    state_grid_oss_secret_access_key: str = ""
    state_grid_oss_region: str = ""
    state_grid_cookie: str = ""
    state_grid_referer: str = "https://ecp.sgcc.com.cn/ecp2.0/portal/"
    state_grid_origin: str = "https://ecp.sgcc.com.cn"

    model_config = {"env_prefix": "", "case_sensitive": False, "env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
