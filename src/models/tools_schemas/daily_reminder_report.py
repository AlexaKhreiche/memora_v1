from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field

#represents the reminder task -- e.g., take medication
class ReminderItem(BaseModel):
    id: str
    title: str
    due_iso: str = Field(description="ISO datetime string for when it is/was due.")
    priority: int = Field(default=2, ge=1, le=5)  # 1 highest
    instructions: Optional[str] = None

#represents th eoutput of the reminder tool
class ReminderReport(BaseModel):
    reminders_due: List[ReminderItem] = Field(default_factory=list)
    next_reminder_iso: Optional[str] = None
