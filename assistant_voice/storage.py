from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Iterable

from .models import Task


class JsonTaskStorage:
    """Persistance JSON simple, atomique et lisible."""

    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path).expanduser().resolve()
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> list[Task]:
        if not self.file_path.exists():
            return []
        try:
            with self.file_path.open("r", encoding="utf-8") as stream:
                data = json.load(stream)
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(data, list):
            return []
        tasks: list[Task] = []
        for item in data:
            if isinstance(item, dict):
                try:
                    tasks.append(Task.from_dict(item))
                except Exception:
                    continue
        return tasks

    def save(self, tasks: Iterable[Task]) -> None:
        payload = [task.to_dict() for task in tasks]
        with NamedTemporaryFile("w", encoding="utf-8", dir=self.file_path.parent, delete=False) as tmp:
            json.dump(payload, tmp, ensure_ascii=False, indent=2)
            tmp_path = Path(tmp.name)
        os.replace(tmp_path, self.file_path)
