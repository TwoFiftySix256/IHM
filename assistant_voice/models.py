from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class TaskStatus(str, Enum):
    PENDING = "en attente"
    DONE = "terminée"
    DELETED = "supprimée"


@dataclass
class Task:
    title: str
    due_at: datetime
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: str = TaskStatus.PENDING.value
    created_at: datetime = field(default_factory=datetime.now)

    # Double rappel
    early_reminded_at: Optional[datetime] = None
    main_reminded_at: Optional[datetime] = None

    # Ancien champ gardé pour compatibilité avec ton ancien code
    reminded_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "due_at": self.due_at.isoformat(),
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "early_reminded_at": self.early_reminded_at.isoformat() if self.early_reminded_at else None,
            "main_reminded_at": self.main_reminded_at.isoformat() if self.main_reminded_at else None,
            "reminded_at": self.reminded_at.isoformat() if self.reminded_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        def parse_dt(value: Any) -> Optional[datetime]:
            if not value:
                return None

            if isinstance(value, datetime):
                return value

            try:
                return datetime.fromisoformat(str(value))
            except Exception:
                return None

        due_at = parse_dt(data.get("due_at")) or datetime.now()
        created_at = parse_dt(data.get("created_at")) or datetime.now()

        early_reminded_at = parse_dt(data.get("early_reminded_at"))
        main_reminded_at = parse_dt(data.get("main_reminded_at"))
        old_reminded_at = parse_dt(data.get("reminded_at"))

        # Compatibilité avec les anciennes tâches :
        # si l’ancien système avait déjà rappelé, on considère que le rappel principal est fait.
        if old_reminded_at and not main_reminded_at:
            main_reminded_at = old_reminded_at

        return cls(
            task_id=str(data.get("task_id") or uuid.uuid4().hex),
            title=str(data.get("title") or "tâche sans titre"),
            due_at=due_at,
            status=str(data.get("status") or TaskStatus.PENDING.value),
            created_at=created_at,
            early_reminded_at=early_reminded_at,
            main_reminded_at=main_reminded_at,
            reminded_at=old_reminded_at,
        )


@dataclass
class ParsedCommand:
    intent: str = "unknown"
    speak: str = ""
    need_confirmation: bool = False
    task: dict[str, Any] = field(default_factory=dict)
    action: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ParsedCommand":
        return cls(
            intent=str(data.get("intent") or "unknown"),
            speak=str(data.get("speak") or ""),
            need_confirmation=bool(data.get("need_confirmation", False)),
            task=data.get("task") if isinstance(data.get("task"), dict) else {},
            action=data.get("action") if isinstance(data.get("action"), dict) else {},
        )