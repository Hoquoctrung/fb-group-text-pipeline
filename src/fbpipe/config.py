"""Configuration loading and validation."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator


class ProjectConfig(BaseModel):
    """Project-level settings."""

    seed: int = 42
    data_dir: str = "data"


class GroupConfig(BaseModel):
    """Target group settings."""

    id: str
    url: str
    language_hint: str = "auto"


class ComplianceConfig(BaseModel):
    """Collection safety limits."""

    acknowledged: bool = False
    max_posts_per_session: int = 300
    max_session_minutes: int = 40
    delay_seconds: tuple[float, float] = (3.0, 8.0)
    collect_comments: bool = False
    max_comments_per_post: int = 0

    @field_validator("delay_seconds")
    @classmethod
    def validate_delay(cls, value: tuple[float, float]) -> tuple[float, float]:
        if value[0] < 0 or value[1] < value[0]:
            raise ValueError("delay_seconds must be an ordered non-negative range")
        return value


class PrivacyConfig(BaseModel):
    """Privacy controls."""

    hash_authors: bool = True
    scrub_pii_in_text: bool = True


class CollectConfig(BaseModel):
    """Collector configuration."""

    adapter: str = "playwright"
    headless: bool = False
    sort: str = "recent"
    stop_after_empty_scrolls: int = 6


class AppConfig(BaseModel):
    """Top-level application configuration."""

    project: ProjectConfig = Field(default_factory=ProjectConfig)
    group: GroupConfig
    compliance: ComplianceConfig = Field(default_factory=ComplianceConfig)
    privacy: PrivacyConfig = Field(default_factory=PrivacyConfig)
    collect: CollectConfig = Field(default_factory=CollectConfig)
    preprocess: dict[str, Any] = Field(default_factory=dict)


def load_config(path: str | Path) -> AppConfig:
    """Load and validate a YAML configuration file."""
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        raw: dict[str, Any] = yaml.safe_load(handle) or {}
    return AppConfig.model_validate(raw)
