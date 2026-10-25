"""Strict, validated output schema."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class Bar(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bar_id: int = Field(ge=1, description="Stable left-to-right id within the slide")
    x_center: int
    x_left: int
    x_right: int
    body_top: int
    body_bottom: int
    direction: Literal["bull", "bear"]


class Slide(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slide: int = Field(ge=1)
    start_s: float
    end_s: float
    plot_area: tuple[int, int, int, int]
    bar_spacing_px: float
    bars: list[Bar]


class Reference(BaseModel):
    """One spoken reference resolved (or deliberately not resolved) to chart bars."""
    model_config = ConfigDict(extra="forbid")
    segment_index: int
    slide: int
    start_s: float
    end_s: float
    transcript: str
    phrase: str
    expected_count: Optional[int] = None
    decision: Literal["label", "abstain"]
    bar_ids: list[int] = []
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    pointer_on_chart_ratio: float = Field(ge=0.0, le=1.0)
    crop_path: Optional[str] = None


class Report(BaseModel):
    model_config = ConfigDict(extra="forbid")
    video: str
    transcript: str
    fps: float
    frames: int
    confidence_threshold: float
    slides: list[Slide]
    references: list[Reference]
