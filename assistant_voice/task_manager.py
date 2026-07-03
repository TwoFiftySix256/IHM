from __future__ import annotations

import difflib
import re
from datetime import datetime, timedelta
from threading import RLock

from .models import Task, TaskStatus
from .storage import JsonTaskStorage


def _normalize(text: str) -> str:
    text = (text or "").lower().strip()
    text = re.sub(r"[^\w\sàâäéèêëîïôöùûüç-]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


class TaskManager:
    def __init__(self, storage: JsonTaskStorage):
        self.storage = storage
        self._lock = RLock()
        self._tasks = self.storage.load()

    def list_tasks(self, include_deleted: bool = False) -> list[Task]:
        with self._lock:
            tasks = list(self._tasks)

        if not include_deleted:
            tasks = [t for t in tasks if t.status != TaskStatus.DELETED.value]

        return sorted(tasks, key=lambda task: task.due_at)

    def pending_tasks(self) -> list[Task]:
        with self._lock:
            tasks = [
                task for task in self._tasks
                if task.status == TaskStatus.PENDING.value
            ]

        return sorted(tasks, key=lambda task: task.due_at)

    def add_task(self, title: str, due_at: datetime) -> Task:
        task = Task(title=title.strip(), due_at=due_at)

        if not task.title:
            raise ValueError("Le titre de la tâche ne peut pas être vide.")

        with self._lock:
            self._tasks.append(task)
            self.storage.save(self._tasks)

        return task

    def mark_done(self, task_id_or_title: str) -> Task:
        return self._update_status(task_id_or_title, TaskStatus.DONE.value)

    def delete_task(self, task_id_or_title: str) -> Task:
        return self._update_status(task_id_or_title, TaskStatus.DELETED.value)

    def delete_all_tasks(self) -> int:
        count = 0

        with self._lock:
            for task in self._tasks:
                if task.status != TaskStatus.DELETED.value:
                    task.status = TaskStatus.DELETED.value
                    count += 1

            self.storage.save(self._tasks)

        return count

    def get_by_position(self, position: int) -> Task:
        tasks = self.list_tasks()

        if position < 1 or position > len(tasks):
            raise LookupError("Numéro de tâche invalide.")

        return tasks[position - 1]

    def due_alerts(
        self,
        now: datetime | None = None,
        early_minutes: int = 5,
    ) -> list[tuple[str, Task]]:
        """
        Retourne les rappels à annoncer.

        alert_type :
        - "early" : rappel anticipé
        - "main"  : rappel principal à l'heure exacte
        """
        now = now or datetime.now()
        early_delta = timedelta(minutes=max(1, early_minutes))

        alerts: list[tuple[str, Task]] = []

        with self._lock:
            for task in self._tasks:
                if task.status != TaskStatus.PENDING.value:
                    continue

                early_time = task.due_at - early_delta

                # Rappel anticipé :
                # il se déclenche entre early_time et l'heure exacte.
                if (
                    task.early_reminded_at is None
                    and early_time <= now < task.due_at
                ):
                    alerts.append(("early", task))
                    continue

                # Rappel principal :
                # il se déclenche à l'heure exacte ou juste après si le PC était occupé.
                if (
                    task.main_reminded_at is None
                    and now >= task.due_at
                ):
                    alerts.append(("main", task))

        return alerts

    def mark_alert_sent(self, task_id: str, alert_type: str) -> None:
        with self._lock:
            task = self._find(task_id)
            now = datetime.now()

            if alert_type == "early":
                task.early_reminded_at = now
            elif alert_type == "main":
                task.main_reminded_at = now
                task.reminded_at = now

            self.storage.save(self._tasks)

    # Ancienne méthode gardée pour compatibilité
    def mark_reminded(self, task_id: str) -> None:
        self.mark_alert_sent(task_id, "main")

    def _update_status(self, task_id_or_title: str, status: str) -> Task:
        with self._lock:
            task = self._find(task_id_or_title)
            task.status = status
            self.storage.save(self._tasks)
            return task

    def _find(self, task_id_or_title: str) -> Task:
        needle_raw = (task_id_or_title or "").strip()

        if not needle_raw:
            active_tasks = [
                t for t in self._tasks
                if t.status != TaskStatus.DELETED.value
            ]

            if len(active_tasks) == 1:
                return active_tasks[0]

            raise LookupError("Précisez la tâche à modifier.")

        active_tasks = [
            t for t in self._tasks
            if t.status != TaskStatus.DELETED.value
        ]

        for task in active_tasks:
            if task.task_id == needle_raw:
                return task

        needle = _normalize(needle_raw)

        for task in active_tasks:
            title = _normalize(task.title)

            if needle in title or title in needle:
                return task

        titles = [_normalize(task.title) for task in active_tasks]
        matches = difflib.get_close_matches(needle, titles, n=1, cutoff=0.45)

        if matches:
            matched_title = matches[0]

            for task in active_tasks:
                if _normalize(task.title) == matched_title:
                    return task

        raise LookupError(f"Tâche introuvable : {task_id_or_title}")