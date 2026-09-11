from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Health(BaseModel):
    status: Literal["ok"]


class JobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: UUID
    document_ids: list[UUID] = []
    instructions: str | None = None
    period_start: date | None = None
    period_end: date | None = None
