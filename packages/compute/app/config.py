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
    scheduler_hour: int = 10    # UTC 10:00 = Beijing 18:00
    scheduler_minute: int = 0

    model_config = {"env_prefix": "", "case_sensitive": False}


settings = Settings()
